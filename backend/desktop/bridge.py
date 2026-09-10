"""TRINETRA Native Desktop Bridge (P-DESKTOP).

Thread-safe Qt/QML bridge exposing:
  - Live video session control (webcam, file, RTSP) and in-memory frame signaling
  - Layer toggles (bounding boxes, trajectories, zones, faces, kinematics, landmarks, ANPR)
  - Zone management with real-time SQLite persistence & Polygon/Line drawing
  - Forensic Event log with 7-W deterministic audit summaries
  - Multi-Camera Person Re-ID gallery & identity investigation
  - Grounded LLM reasoning assistant (P-HERMES) with honest error propagation
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import (
    Property,
    QObject,
    QRunnable,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtWidgets import QFileDialog

from backend.analytics.zones import ZoneStore
from backend.core import config as cfg
from backend.core.config import MODELS_DIR, PATHS, ROOT
from backend.core.errors import get_dao, get_hub, get_reid_service, get_zone_store
from backend.db.dao import DAO
from backend.events.sse import SseHub
from backend.services.hermes import (
    HermesService,
    HermesUnavailableError,
    build_hermes_context,
)
from backend.services.session import (
    SessionError,
    get_active_session,
    get_writer,
    make_source,
    start_session,
    stop_active_session,
)
from backend.services.summary import (
    generate_event_summary,
    generate_session_summary,
)
from backend.vision import DetectorError

log = logging.getLogger("trinetra.desktop.bridge")


class HermesWorker(QRunnable):
    """Executes LLM reasoning off the Qt GUI thread."""

    def __init__(
        self,
        hermes_svc: HermesService,
        dao: DAO,
        question: str,
        event_id: Optional[str],
        session_id: Optional[str],
        model: Optional[str],
        on_success,
        on_error,
    ) -> None:
        super().__init__()
        self.hermes_svc = hermes_svc
        self.dao = dao
        self.question = question
        self.event_id = event_id
        self.session_id = session_id
        self.model = model
        self.on_success = on_success
        self.on_error = on_error

    def run(self) -> None:
        try:
            res = self.hermes_svc.ask(
                dao=self.dao,
                question=self.question,
                event_id=self.event_id,
                session_id=self.session_id,
                model_override=self.model,
            )
            self.on_success(res)
        except HermesUnavailableError as e:
            self.on_error(e.as_dict())
        except Exception as e:
            self.on_error({"error": "hermes_unexpected", "reason": "unexpected_error", "message": str(e)})


class TrinetraBridge(QObject):
    """Central Qt Quick Bridge for the TRINETRA Command Center."""

    # --- Signals ---
    frameUpdated = Signal()
    sessionStateChanged = Signal(dict)
    eventReceived = Signal(dict)
    eventsListUpdated = Signal(list)
    zonesUpdated = Signal(list)
    sourcesUpdated = Signal(list)
    layersUpdated = Signal(dict)
    hermesStatusUpdated = Signal(dict)
    hermesAnswerReceived = Signal(dict)
    hermesErrorOccurred = Signal(dict)
    hermesThinkingChanged = Signal(bool)
    reidPersonsUpdated = Signal(list)
    reidDetailUpdated = Signal(dict)
    auditSummaryUpdated = Signal(dict)
    statusMessage = Signal(str, str)  # message, level: info|warning|error|success

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._thread_pool = QThreadPool.globalInstance()
        self._hermes_svc = HermesService()

        # Cached state
        self._active: bool = False
        self._status: str = "stopped"
        self._source_id: str = ""
        self._fps: float = 0.0
        self._frames_processed: int = 0
        self._active_tracks: int = 0
        self._people_detected: int = 0
        self._vehicles_detected: int = 0
        self._events_committed: int = 0
        self._error: str = ""
        self._is_hermes_thinking: bool = False

        self._events_cache: list[dict[str, Any]] = []
        self._zones_cache: list[dict[str, Any]] = []
        self._reid_cache: list[dict[str, Any]] = []
        self._sources_cache: list[dict[str, Any]] = []

        self._layers: dict[str, bool] = {
            "boxes": True,
            "labels": True,
            "fps": True,
            "trajectories": False,
            "zones": True,
            "faces": False,
        }

        # Frame polling timer (~30 FPS)
        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(33)
        self._frame_timer.timeout.connect(self._on_frame_tick)
        self._frame_timer.start()

        # Status polling timer (500ms)
        self._status_timer = QTimer(self)
        self._status_timer.setInterval(500)
        self._status_timer.timeout.connect(self._on_status_tick)
        self._status_timer.start()

        # SSE listener thread
        self._sse_running = True
        self._sse_thread: Optional[threading.Thread] = None
        self._start_sse_listener()

    def shutdown(self) -> None:
        """Clean shutdown hook for timers and background threads."""
        self._frame_timer.stop()
        self._status_timer.stop()
        self._sse_running = False
        stop_active_session()

    def set_hermes_service(self, svc: HermesService) -> None:
        """Inject custom HermesService instance for testing or reconfiguration."""
        self._hermes_svc = svc

    # --- Property Getters ---

    @Property(bool, notify=sessionStateChanged)
    def active(self) -> bool:
        return self._active

    @Property(str, notify=sessionStateChanged)
    def status(self) -> str:
        return self._status

    @Property(str, notify=sessionStateChanged)
    def sourceId(self) -> str:
        return self._source_id

    @Property(float, notify=sessionStateChanged)
    def fps(self) -> float:
        return self._fps

    @Property(int, notify=sessionStateChanged)
    def framesProcessed(self) -> int:
        return self._frames_processed

    @Property(int, notify=sessionStateChanged)
    def activeTracks(self) -> int:
        return self._active_tracks

    @Property(int, notify=sessionStateChanged)
    def peopleDetected(self) -> int:
        return self._people_detected

    @Property(int, notify=sessionStateChanged)
    def vehiclesDetected(self) -> int:
        return self._vehicles_detected

    @Property(int, notify=sessionStateChanged)
    def eventsCommitted(self) -> int:
        return self._events_committed

    @Property(str, notify=sessionStateChanged)
    def sessionError(self) -> str:
        return self._error

    @Property(str, notify=sessionStateChanged)
    def sessionStatus(self) -> str:
        return self._status

    @Property(str, notify=sessionStateChanged)
    def activeSourceId(self) -> str:
        return self._source_id

    @Property(float, notify=sessionStateChanged)
    def currentFps(self) -> float:
        return self._fps

    @Property(int, notify=sessionStateChanged)
    def activeTracksCount(self) -> int:
        return self._active_tracks

    @Property("QVariantList", notify=eventsListUpdated)
    def eventsList(self) -> list[dict[str, Any]]:
        return self._events_cache

    @Property("QVariantList", notify=zonesUpdated)
    def zonesList(self) -> list[dict[str, Any]]:
        return self._zones_cache

    @Property("QVariantList", notify=reidPersonsUpdated)
    def reidIdentities(self) -> list[dict[str, Any]]:
        return self._reid_cache

    @Property("QVariantList", notify=sourcesUpdated)
    def sourcesList(self) -> list[dict[str, Any]]:
        return self._sources_cache

    @Property(bool, notify=hermesThinkingChanged)
    def isHermesThinking(self) -> bool:
        return self._is_hermes_thinking

    @Property(bool, constant=True)
    def hermesEnabled(self) -> bool:
        return cfg.HERMES.enabled

    @Property(bool, constant=True)
    def reidEnabled(self) -> bool:
        reid_onnx = MODELS_DIR / cfg.REID.onnx_path
        return cfg.REID.enabled and reid_onnx.exists()

    @Property(bool, constant=True)
    def faceEnabled(self) -> bool:
        return (MODELS_DIR / "yunet.onnx").exists()

    @Property(str, constant=True)
    def anprMode(self) -> str:
        return "model" if (MODELS_DIR / "yolov8n_plate.pt").exists() else "heuristic_fallback"

    # --- Tick Handlers ---

    def _on_frame_tick(self) -> None:
        session = get_active_session()
        if session is not None and session.status in ("running", "starting"):
            self.frameUpdated.emit()

    def _on_status_tick(self) -> None:
        session = get_active_session()
        if session is not None:
            st = session.status_payload()
            self._active = True
            self._status = st["status"]
            self._source_id = st["source_id"]
            self._fps = st["pipeline_fps"]
            self._frames_processed = st["frames_processed"]
            self._active_tracks = st["active_tracks"]
            self._people_detected = st["people_detected"]
            self._vehicles_detected = st["vehicles_detected"]
            self._events_committed = st["events_committed"]
            self._error = st["error"] or ""
            self._layers = session.get_layers()
            self.sessionStateChanged.emit(st)
        else:
            if self._active:
                self._active = False
                self._status = "stopped"
                self._fps = 0.0
                self.sessionStateChanged.emit({"active": False, "status": "stopped"})

    def _start_sse_listener(self) -> None:
        def _worker():
            try:
                hub = get_hub()
            except Exception:
                return

            cid, client = hub.subscribe()
            while self._sse_running:
                try:
                    item = client.q.get(timeout=0.5)
                    if item:
                        lines = item.strip().split("\n")
                        for line in lines:
                            if line.startswith("data:"):
                                data_str = line[5:].strip()
                                if data_str:
                                    try:
                                        ev_data = json.loads(data_str)
                                        self.eventReceived.emit(ev_data)
                                        self._events_cache.insert(0, ev_data)
                                        if len(self._events_cache) > 500:
                                            self._events_cache.pop()
                                        self.eventsListUpdated.emit(self._events_cache)
                                    except Exception:
                                        pass
                except queue.Empty:
                    continue
                except Exception as e:
                    log.debug("SSE listener error: %s", e)
                    time.sleep(0.5)

            try:
                hub.unsubscribe(cid)
            except Exception:
                pass

        self._sse_thread = threading.Thread(target=_worker, daemon=True, name="desktop-sse")
        self._sse_thread.start()

    # --- Q_INVOKABLE / Slots: Session Control ---

    @Slot(int, result=bool)
    def startWebcam(self, index: int = 0) -> bool:
        """Start a live webcam session."""
        try:
            source = make_source({"type": "webcam", "index": index})
            session = start_session(
                source,
                zones=get_zone_store(),
                dao=get_dao(),
                writer=get_writer(),
                hub=get_hub(),
                reid_service=get_reid_service(),
            )
            self.statusMessage.emit(f"Webcam session started on index {index}", "success")
            self._on_status_tick()
            return True
        except SessionError as e:
            self.statusMessage.emit(f"Session Error: {e}", "warning")
            return False
        except DetectorError as e:
            self.statusMessage.emit(f"Detector Error: {e}", "error")
            return False
        except Exception as e:
            self.statusMessage.emit(f"Failed to start webcam: {e}", "error")
            return False

    @Slot(str, result=bool)
    def startFile(self, path: str) -> bool:
        """Start a video file playback session."""
        if not path:
            self.statusMessage.emit("No video file selected", "warning")
            return False
        try:
            source = make_source({"type": "file", "path": path})
            session = start_session(
                source,
                zones=get_zone_store(),
                dao=get_dao(),
                writer=get_writer(),
                hub=get_hub(),
                reid_service=get_reid_service(),
            )
            self.statusMessage.emit(f"File session started: {Path(path).name}", "success")
            self._on_status_tick()
            return True
        except SessionError as e:
            self.statusMessage.emit(f"Session Error: {e}", "warning")
            return False
        except DetectorError as e:
            self.statusMessage.emit(f"Detector Error: {e}", "error")
            return False
        except Exception as e:
            self.statusMessage.emit(f"Failed to start file session: {e}", "error")
            return False

    @Slot(str, result=bool)
    def startRtsp(self, uri: str) -> bool:
        """Start an RTSP network stream session."""
        if not uri:
            self.statusMessage.emit("RTSP URI cannot be empty", "warning")
            return False
        try:
            source = make_source({"type": "rtsp", "uri": uri})
            session = start_session(
                source,
                zones=get_zone_store(),
                dao=get_dao(),
                writer=get_writer(),
                hub=get_hub(),
                reid_service=get_reid_service(),
            )
            self.statusMessage.emit(f"RTSP session started: {uri}", "success")
            self._on_status_tick()
            return True
        except SessionError as e:
            self.statusMessage.emit(f"Session Error: {e}", "warning")
            return False
        except DetectorError as e:
            self.statusMessage.emit(f"Detector Error: {e}", "error")
            return False
        except Exception as e:
            self.statusMessage.emit(f"Failed to start RTSP session: {e}", "error")
            return False

    @Slot(result=bool)
    def stopSession(self) -> bool:
        """Stop the currently active surveillance session."""
        session = stop_active_session()
        if session:
            self.statusMessage.emit(f"Session '{session.source_id}' stopped", "info")
            self._on_status_tick()
            return True
        return False

    # --- Q_INVOKABLE / Slots: Render Layers ---

    @Slot(str, bool, result=bool)
    def setLayer(self, name: str, enabled: bool) -> bool:
        """Toggle a single visual annotation layer."""
        session = get_active_session()
        if session is None:
            self._layers[name] = enabled
            self.layersUpdated.emit(self._layers)
            return True
        try:
            layers = session.update_layers({name: enabled})
            self._layers = layers
            self.layersUpdated.emit(layers)
            return True
        except Exception as e:
            self.statusMessage.emit(f"Layer update error: {e}", "error")
            return False

    @Slot(str, result=bool)
    def toggleLayer(self, name: str) -> bool:
        curr = self._layers.get(name, False)
        return self.setLayer(name, not curr)

    @Slot(result="QVariantMap")
    def getLayers(self) -> dict[str, bool]:
        session = get_active_session()
        if session is not None:
            self._layers = session.get_layers()
        return dict(self._layers)

    # --- Q_INVOKABLE / Slots: Zone Management ---

    @Slot(str, result="QVariantList")
    def loadZones(self, source_id: str = "") -> list[dict[str, Any]]:
        """Retrieve configured zones from the SQLite ZoneStore."""
        try:
            dao = get_dao()
            zones = dao.zones_rows(source_id=source_id if source_id else None, active_only=False)
            out = []
            for z in zones:
                coords = []
                try:
                    coords = json.loads(z["geometry"])
                except Exception:
                    pass
                out.append({
                    "id": z["id"],
                    "source_id": z["source_id"],
                    "name": z["name"],
                    "kind": z["kind"],
                    "zone_type": z["zone_type"],
                    "coords": coords,
                    "coords_raw": z["geometry"],
                    "active": bool(z["active"]),
                })
            self._zones_cache = out
            self.zonesUpdated.emit(out)
            return out
        except Exception as e:
            self.statusMessage.emit(f"Failed to load zones: {e}", "error")
            return []

    @Slot(str, result="QVariantList")
    def getZones(self, source_id: str = "") -> list[dict[str, Any]]:
        return self.loadZones(source_id)

    @Slot(str, str, str, str, str, bool, result=bool)
    def savePolygonZone(
        self,
        zone_id: str,
        source_id: str,
        name: str,
        zone_type: str,
        coords_json: str,
        active: bool = True,
    ) -> bool:
        """Create or update a polygon restricted fence zone."""
        try:
            coords = json.loads(coords_json)
            if not isinstance(coords, list) or len(coords) < 3:
                self.statusMessage.emit("Polygon zone requires at least 3 vertices", "warning")
                return False

            dao = get_dao()
            if dao.get_zone(zone_id):
                dao.update_zone(
                    zone_id=zone_id,
                    name=name,
                    zone_type=zone_type,
                    geometry_json=json.dumps(coords),
                    active=active,
                )
            else:
                dao.insert_zone(
                    zone_id=zone_id,
                    source_id=source_id,
                    name=name,
                    kind="polygon",
                    zone_type=zone_type,
                    geometry_json=json.dumps(coords),
                    active=active,
                )
            # Sync to in-memory store if active session
            try:
                store = get_zone_store()
                store.reload()
            except Exception:
                pass
            self.statusMessage.emit(f"Polygon zone '{name}' saved successfully", "success")
            self.loadZones(source_id)
            return True
        except Exception as e:
            self.statusMessage.emit(f"Failed to save zone: {e}", "error")
            return False

    @Slot(str, str, str, str, str, bool, result=bool)
    def saveLineZone(
        self,
        zone_id: str,
        source_id: str,
        name: str,
        zone_type: str,
        coords_json: str,
        active: bool = True,
    ) -> bool:
        """Create or update a virtual tripwire line zone."""
        try:
            coords = json.loads(coords_json)
            if not isinstance(coords, list) or len(coords) < 2:
                self.statusMessage.emit("Line zone requires 2 endpoints", "warning")
                return False

            dao = get_dao()
            if dao.get_zone(zone_id):
                dao.update_zone(
                    zone_id=zone_id,
                    name=name,
                    zone_type=zone_type,
                    geometry_json=json.dumps(coords),
                    active=active,
                )
            else:
                dao.insert_zone(
                    zone_id=zone_id,
                    source_id=source_id,
                    name=name,
                    kind="line",
                    zone_type=zone_type,
                    geometry_json=json.dumps(coords),
                    active=active,
                )
            try:
                store = get_zone_store()
                store.reload()
            except Exception:
                pass
            self.statusMessage.emit(f"Tripwire line '{name}' saved successfully", "success")
            self.loadZones(source_id)
            return True
        except Exception as e:
            self.statusMessage.emit(f"Failed to save line zone: {e}", "error")
            return False

    @Slot(str, result=bool)
    def deleteZone(self, zone_id: str) -> bool:
        try:
            dao = get_dao()
            dao.delete_zone(zone_id)
            try:
                store = get_zone_store()
                store.reload()
            except Exception:
                pass
            self.statusMessage.emit(f"Zone {zone_id} deleted", "info")
            self.loadZones()
            return True
        except Exception as e:
            self.statusMessage.emit(f"Failed to delete zone: {e}", "error")
            return False

    @Slot(str, bool, result=bool)
    def toggleZoneActive(self, zone_id: str, active: bool) -> bool:
        try:
            dao = get_dao()
            dao.update_zone(zone_id=zone_id, active=active)
            try:
                store = get_zone_store()
                store.reload()
            except Exception:
                pass
            self.loadZones()
            return True
        except Exception as e:
            self.statusMessage.emit(f"Failed to toggle zone: {e}", "error")
            return False

    # --- Q_INVOKABLE / Slots: Events & 7-W Forensic Summaries ---

    @Slot(int, int, str, str, str, result="QVariantList")
    def loadEvents(
        self,
        limit: int = 50,
        offset: int = 0,
        severity: str = "",
        event_type: str = "",
        source_id: str = "",
    ) -> list[dict[str, Any]]:
        """Query historical surveillance events with metadata."""
        try:
            dao = get_dao()
            events = dao.query_events(
                limit=limit,
                severity=severity if severity else "",
                type_=event_type if event_type else "",
            )
            out = []
            for ev in events:
                if source_id and ev["source_id"] != source_id:
                    continue
                meta = {}
                if ev["metadata"]:
                    try:
                        meta = json.loads(ev["metadata"])
                    except Exception:
                        pass
                track_ids = []
                if ev["track_ids"]:
                    try:
                        track_ids = json.loads(ev["track_ids"])
                    except Exception:
                        pass
                out.append({
                    "id": ev["id"],
                    "session_id": ev["session_id"],
                    "source_id": ev["source_id"],
                    "ts": ev["ts"],
                    "video_ts": ev["video_ts"],
                    "type": ev["type"],
                    "severity": ev["severity"],
                    "confidence": ev["confidence"],
                    "track_ids": track_ids,
                    "zone_id": ev["zone_id"],
                    "direction": ev["direction"],
                    "is_night": bool(ev["is_night"]),
                    "snapshot_path": ev["snapshot_path"],
                    "status": ev["status"],
                    "metadata": meta,
                })
            self._events_cache = out
            self.eventsListUpdated.emit(out)
            return out
        except Exception as e:
            self.statusMessage.emit(f"Failed to load events: {e}", "error")
            return []

    @Slot(int, int, str, str, str, result="QVariantList")
    def getEvents(
        self,
        limit: int = 50,
        offset: int = 0,
        severity: str = "",
        event_type: str = "",
        source_id: str = "",
    ) -> list[dict[str, Any]]:
        return self.loadEvents(limit, offset, severity, event_type, source_id)

    @Slot(str, result="QVariantMap")
    def getEventDetail(self, event_id: str) -> dict[str, Any]:
        """Fetch complete row data for an event."""
        try:
            dao = get_dao()
            ev = dao.get_event(event_id)
            if not ev:
                return {}
            meta = {}
            if ev["metadata"]:
                try:
                    meta = json.loads(ev["metadata"])
                except Exception:
                    pass
            return {
                "id": ev["id"],
                "session_id": ev["session_id"],
                "source_id": ev["source_id"],
                "ts": ev["ts"],
                "video_ts": ev["video_ts"],
                "type": ev["type"],
                "severity": ev["severity"],
                "confidence": ev["confidence"],
                "track_ids": json.loads(ev["track_ids"]) if ev["track_ids"] else [],
                "zone_id": ev["zone_id"],
                "direction": ev["direction"],
                "is_night": bool(ev["is_night"]),
                "snapshot_path": ev["snapshot_path"],
                "status": ev["status"],
                "metadata": meta,
            }
        except Exception as e:
            self.statusMessage.emit(f"Failed to load event detail: {e}", "error")
            return {}

    @Slot(str, result="QVariantMap")
    def generate7WSummary(self, event_id: str) -> dict[str, Any]:
        """Generate deterministic machine-verified 7-W forensic audit breakdown."""
        try:
            dao = get_dao()
            summary = generate_event_summary(dao, event_id)
            if summary:
                self.auditSummaryUpdated.emit(summary)
                return summary
            return {}
        except Exception as e:
            self.statusMessage.emit(f"Audit summary failed: {e}", "error")
            return {}

    @Slot(str, result="QVariantMap")
    def generateSessionAudit(self, session_id: str) -> dict[str, Any]:
        """Generate deterministic session-level forensic audit summary."""
        try:
            dao = get_dao()
            summary = generate_session_summary(dao, session_id)
            return summary or {}
        except Exception as e:
            self.statusMessage.emit(f"Session audit failed: {e}", "error")
            return {}

    @Slot(str, str, result=bool)
    def updateEventStatus(self, event_id: str, status: str) -> bool:
        """Acknowledge or update review status of an alert."""
        try:
            dao = get_dao()
            dao.conn.execute("UPDATE events SET status=? WHERE id=?", (status, event_id))
            dao.conn.commit()
            self.statusMessage.emit(f"Event {event_id} marked as {status}", "info")
            return True
        except Exception as e:
            self.statusMessage.emit(f"Failed to update event: {e}", "error")
            return False

    # --- Q_INVOKABLE / Slots: Multi-Camera Person Re-ID ---

    @Slot(result="QVariantList")
    def loadReidPersons(self) -> list[dict[str, Any]]:
        """Retrieve all clustered cross-camera person identities."""
        svc = get_reid_service()
        if svc is None:
            return []
        try:
            persons = svc.all_persons()
            self._reid_cache = persons
            self.reidPersonsUpdated.emit(persons)
            return persons
        except Exception as e:
            self.statusMessage.emit(f"Re-ID query error: {e}", "error")
            return []

    @Slot(result="QVariantList")
    def getReidIdentities(self) -> list[dict[str, Any]]:
        return self.loadReidPersons()

    @Slot(str, result="QVariantMap")
    def loadReidPersonDetail(self, pid: str) -> dict[str, Any]:
        """Retrieve sightings, timeline, and camera sightings for a person ID."""
        svc = get_reid_service()
        if svc is None:
            return {}
        try:
            summary = svc.person_summary(pid)
            if summary:
                self.reidDetailUpdated.emit(summary)
                return summary
            return {}
        except Exception as e:
            self.statusMessage.emit(f"Re-ID detail error: {e}", "error")
            return {}

    # --- Q_INVOKABLE / Slots: Grounded LLM Reasoning (P-HERMES) ---

    @Slot(str, str, str, str)
    def askHermes(
        self,
        question: str,
        event_id: str = "",
        session_id: str = "",
        model: str = "",
    ) -> None:
        """Query the Hermes reasoning layer asynchronously."""
        if not question or not question.strip():
            self.statusMessage.emit("Question cannot be empty", "warning")
            return

        self._is_hermes_thinking = True
        self.hermesThinkingChanged.emit(True)

        def _on_success(result: dict[str, Any]) -> None:
            self._is_hermes_thinking = False
            self.hermesThinkingChanged.emit(False)
            self.hermesAnswerReceived.emit(result)

        def _on_error(err_obj: dict[str, Any]) -> None:
            self._is_hermes_thinking = False
            self.hermesThinkingChanged.emit(False)
            self.hermesErrorOccurred.emit(err_obj)
            self.statusMessage.emit(f"Hermes ({err_obj.get('reason')}): {err_obj.get('message')}", "warning")

        worker = HermesWorker(
            hermes_svc=self._hermes_svc,
            dao=get_dao(),
            question=question.strip(),
            event_id=event_id if event_id else None,
            session_id=session_id if session_id else None,
            model=model if model else None,
            on_success=_on_success,
            on_error=_on_error,
        )
        self._thread_pool.start(worker)

    @Slot(bool, result="QVariantMap")
    def checkHermesStatus(self, force_refresh: bool = False) -> dict[str, Any]:
        """Probe gateway health status."""
        st = self._hermes_svc.check_status(force_refresh=force_refresh)
        self.hermesStatusUpdated.emit(st)
        return st

    @Slot(str, str, result="QVariantMap")
    def getHermesContext(self, event_id: str = "", session_id: str = "") -> dict[str, Any]:
        """Inspect deterministic machine-verified structured context."""
        try:
            dao = get_dao()
            return build_hermes_context(
                dao,
                question="Context Inspection",
                event_id=event_id if event_id else None,
                session_id=session_id if session_id else None,
            )
        except Exception as e:
            self.statusMessage.emit(f"Context error: {e}", "error")
            return {}

    # --- Q_INVOKABLE / Slots: Sources & Filesystem Helpers ---

    @Slot(result=str)
    def selectVideoFile(self) -> str:
        """Native file picker for surveillance recordings."""
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Select Surveillance Video Recording",
            str(ROOT / "data"),
            "Video Files (*.mp4 *.avi *.mkv *.mov *.webm);;All Files (*)",
        )
        return file_path

    @Slot(result="QVariantList")
    def loadSources(self) -> list[dict[str, Any]]:
        try:
            dao = get_dao()
            sources = dao.sources_rows()
            out = []
            for s in sources:
                out.append({
                    "id": s["id"],
                    "name": s["name"] if "name" in s.keys() else s["id"],
                    "type": s["type"] if "type" in s.keys() else "unknown",
                    "latitude": float(s["latitude"]) if ("latitude" in s.keys() and s["latitude"] is not None) else None,
                    "longitude": float(s["longitude"]) if ("longitude" in s.keys() and s["longitude"] is not None) else None,
                    "label": s["label"] if "label" in s.keys() else "",
                })
            self._sources_cache = out
            self.sourcesUpdated.emit(out)
            return out
        except Exception as e:
            self.statusMessage.emit(f"Sources query error: {e}", "error")
            return []

    @Slot(result="QVariantList")
    def getSources(self) -> list[dict[str, Any]]:
        return self.loadSources()

    @Slot(str, str, float, float, result=bool)
    def saveSourceGeo(self, source_id: str, label: str, lat: float, lng: float) -> bool:
        try:
            dao = get_dao()
            dao.set_source_geo(source_id, latitude=lat, longitude=lng, label=label)
            self.statusMessage.emit(f"Geo coordinates saved for camera {source_id}", "success")
            self.loadSources()
            return True
        except Exception as e:
            self.statusMessage.emit(f"Failed to set source geo: {e}", "error")
            return False

    @Slot(result="QVariantMap")
    def getSystemHealth(self) -> dict[str, Any]:
        """Aggregate detector, Re-ID, face, ANPR, and database health."""
        target = MODELS_DIR / cfg.VISION.model
        reid_onnx = MODELS_DIR / cfg.REID.onnx_path
        face_onnx = MODELS_DIR / "yunet.onnx"
        anpr_model = MODELS_DIR / "yolov8n_plate.pt"

        dao_ok = True
        try:
            dao = get_dao()
            dao_ok = dao.health().get("ok", False)
        except Exception:
            dao_ok = False

        return {
            "ok": target.exists() and dao_ok,
            "detector_present": target.exists(),
            "reid_present": reid_onnx.exists(),
            "face_present": face_onnx.exists(),
            "anpr_mode": "model" if anpr_model.exists() else "heuristic_fallback",
            "db_ok": dao_ok,
            "device_policy": cfg.DEVICE.policy,
        }
