"""TRINETRA processing session — the one and only processing loop (M5).

Ownership (frozen architecture, one active session):
    ProcessingSession owns: VideoSource, DetectorTracker, TrackStore,
    one processing thread, one LatestFrameSlot. Nothing else does inference.

    M5: the session RECEIVES the app-scoped ZoneStore (SQLite-backed,
    C1), the EventWriter, the SseHub, and the DAO (for the sessions row
    lifecycle C4). The EventEngine (per-session, C8) is created here.

Execution model: a single daemon thread runs the synchronous loop (§3):

    read -> detect+track -> state -> FrameContext -> analytics chain
        -> annotate(copy) -> JPEG -> engine.commit(drafts, SAME jpeg)
        -> slot.publish

    §3 ordering: annotate BEFORE commit — event snapshots are the SAME
    annotated JPEG the operator sees (A1: one render, no re-encode).
    PERSON/VEHICLE_DETECTED drafts come from take_newly_confirmed()
    (structural once-per-track, A2) — NOT the cooldown map.

Source lifecycle (A5): SOURCE_CONNECTED draft after open + FIRST
successful read (emitted in-loop, not at start()); SOURCE_LOST draft
on read-fail abort, BEFORE status=error. System events: jpeg=None (A1).

EOF finalize (A6, pinned order):
    flush tracks -> DB  ->  SESSION_COMPLETED commit  ->  writer drain
    ->  status=completed   (drain MUST precede the status flip)
    Stop path: same finalize in `finally` for completed/stopped/error
    (error = best-effort flush, honest partial). Writer is catch-all
    (A6): a DB error kills neither the writer thread nor the session.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from backend.analytics import FenceAnalytic, FrameContext, ZoneStore
from backend.analytics.base import EventDraft
from backend.core.config import STREAM, TRACKING, VISION
from backend.events import EventEngine, SseHub
from backend.db.dao import DAO
from backend.db.writer import EventWriter
from backend.services.frame_slot import LatestFrameSlot
from backend.sources import FileSource, SourceError, SourceState, VideoSource, WebcamSource
from backend.state import TrackStore
from backend.vision import DetectorError, DetectorTracker
from backend.vision.annotation import annotate

log = logging.getLogger("trinetra.session")

_FPS_WINDOW = 30          # rolling window for pipeline FPS (documented metric)
_MAX_CONSECUTIVE_READ_FAILS = 60   # ~3s at 20fps -> abort (webcam gone)
_IS_NIGHT_LUMA = 40.0     # §3 step 3: is_night = mean-gray < 40 (named constant)

_VEHICLE_CLASSES = frozenset(
    {"bicycle", "car", "motorcycle", "bus", "truck"})


class SessionError(Exception):
    """Invalid session request or lifecycle misuse."""


def _sys_draft(type_: str) -> EventDraft:
    """System draft (§13): SOURCE_*/SESSION_COMPLETED — INFO severity,
    no tracks, no zone, no snapshot (A1: jpeg=None)."""
    return EventDraft(
        type=type_, track_ids=[], zone_id=None, direction=None,
        confidence=1.0, metadata={"is_night": False, "system": True})


class ProcessingSession:
    """One active processing session. Create via start(); stop() to end."""

    def __init__(self, source: VideoSource,
                 zones: Optional[ZoneStore] = None,
                 dao: Optional[DAO] = None,
                 writer: Optional[EventWriter] = None,
                 hub: Optional[SseHub] = None) -> None:
        self._source = source
        self._detector = DetectorTracker()          # policy from config (auto)
        self._store = TrackStore()
        self._slot = LatestFrameSlot()
        # C1: app-scoped SQLite-backed store RECEIVED from the app; the
        # M4 in-memory fallback only when no app context (unit tests).
        self._zones = zones if zones is not None else ZoneStore()
        self._dao = dao
        self._writer = writer
        self._hub = hub
        self._analytics = [FenceAnalytic(self._zones)]   # MVP chain (§11)
        self._analytics[0].reset(source.source_id)
        # C4/C8: session row id + per-session engine state
        self._session_row_id: Optional[str] = None
        self._engine: Optional[EventEngine] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._started_at = time.time()
        # metrics (guarded by GIL-safe simple writes; read via status())
        self.frames_processed = 0
        self.pipeline_fps: float = 0.0
        self.error: str = ""
        self.status: str = "starting"               # starting|running|completed|error|stopped
        self._durations: list[float] = []
        self._connected_emitted = False
        self._finalized = False

    # ---- properties ----

    @property
    def source_id(self) -> str:
        return self._source.source_id

    @property
    def device(self) -> str:
        return self._detector.actual_device

    @property
    def slot(self) -> LatestFrameSlot:
        return self._slot

    @property
    def zones(self) -> ZoneStore:
        """Zone CRUD surface (C1: works with no active session too)."""
        return self._zones

    @property
    def engine(self) -> Optional[EventEngine]:
        return self._engine

    @property
    def events_committed(self) -> int:
        return self._engine.committed if self._engine else 0

    # ---- lifecycle ----

    def start(self) -> None:
        if self._thread is not None:
            raise SessionError("session already started")
        try:
            self._source.open()
        except SourceError as e:
            self.status = "error"
            self.error = str(e)
            raise
        try:
            self._detector.load()
        except DetectorError as e:
            self._source.release()
            self.status = "error"
            self.error = str(e)
            raise
        # C4: sessions row INSERT + sources row UPSERT (FK targets)
        if self._dao is not None:
            src_type = "webcam" if "webcam" in self.source_id else "file"
            self._dao.upsert_source(self.source_id, src_type)
            self._session_row_id = self._dao.insert_session(self.source_id)
        # C8: per-session engine (cooldown map + counter cleared)
        self._engine = EventEngine(
            self.source_id,
            self._session_row_id or f"nosession:{id(self)}",
            writer=self._writer, hub=self._hub, dao=self._dao)
        self._warmup()
        self._thread = threading.Thread(target=self._run, name="trinetra-session", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._source.release()
        if self.status in ("running", "starting"):
            self.status = "stopped"
        self._finalize()        # A6: stop path finalize

    # ---- internals ----

    def _warmup(self) -> None:
        """One predict() call on internal noise — warms the inference graph.
        Does NOT touch ByteTrack (predict bypasses tracking; verified by
        test_warmup_does_not_contaminate_tracking)."""
        noise = np.zeros((480, 640, 3), dtype=np.uint8)
        try:
            self._detector.warmup(noise)
        except DetectorError:
            log.warning("warm-up inference failed; continuing cold")

    def _annotate(self, frame: np.ndarray, objects: list) -> np.ndarray:
        """§3 step 7: annotate a COPY with tracks + metrics. Zone overlay
        is drawn by the hub-bound client (M7 UI canvas) — the MVP
        annotated frame carries bboxes + HUD only (frozen M3 annotator
        surface; zone overlay on the stream is M7 polish)."""
        return annotate(
            frame, objects,
            pipeline_fps=self.pipeline_fps if self.pipeline_fps > 0 else None,
            device=self._detector.actual_device,
        )

    def _commit(self, drafts: list[EventDraft], jpeg: Optional[bytes],
               ctx: FrameContext) -> None:
        if self._engine is not None:
            self._engine.commit(drafts, jpeg, ctx)

    def _run(self) -> None:
        self.status = "running"
        tick = 0
        read_fails = 0
        try:
            while not self._stop.is_set():
                t0 = time.perf_counter()
                pkt = self._source.read()
                if pkt is None:
                    if self._source.state.value == "EOF":
                        self.status = "completed"
                        break
                    read_fails += 1
                    if read_fails >= _MAX_CONSECUTIVE_READ_FAILS:
                        # A5: SOURCE_LOST before the status flip
                        raise RuntimeError(
                            "source read failed repeatedly (device gone?)")
                    continue
                read_fails = 0

                # A5: SOURCE_CONNECTED after open + FIRST successful read
                if not self._connected_emitted:
                    self._connected_emitted = True
                    sys_ctx = FrameContext(
                        tick=tick, wall_ts=pkt.wall_ts,
                        video_ts=pkt.video_ts, luminance=128.0,
                        is_night=False, shape=(1, 1))
                    self._commit([_sys_draft("SOURCE_CONNECTED")], None,
                                sys_ctx)

                objects = self._detector.process(pkt.frame)
                self._store.update(objects, tick=tick, wall_ts=pkt.wall_ts)

                # FrameContext (§3 step 3): luminance = mean gray via cv2,
                # is_night = luminance < _IS_NIGHT_LUMA (named constant).
                h, w = pkt.frame.shape[:2]
                gray = cv2.cvtColor(pkt.frame, cv2.COLOR_BGR2GRAY)
                luminance = float(gray.mean())
                ctx = FrameContext(
                    tick=tick, wall_ts=pkt.wall_ts, video_ts=pkt.video_ts,
                    luminance=luminance, is_night=luminance < _IS_NIGHT_LUMA,
                    shape=(w, h))

                # analytics chain (§3 step 6) + confirm-edge drafts (A2)
                view = self._store.view()
                drafts: list[EventDraft] = []
                for t in self._store.take_newly_confirmed():
                    dtype = "VEHICLE_DETECTED" \
                        if t.class_name in _VEHICLE_CLASSES \
                        else "PERSON_DETECTED"
                    drafts.append(EventDraft(
                        type=dtype, track_ids=[t.track_id], zone_id=None,
                        direction=None, confidence=t.max_conf,
                        metadata={"is_night": ctx.is_night,
                                  "track_class": t.class_name,
                                  "video_ts": ctx.video_ts,
                                  "tick": ctx.tick}))
                for module in self._analytics:
                    drafts += module.process(ctx, view)

                # §3 step 7: annotate BEFORE commit (A1: same JPEG)
                annotated = self._annotate(pkt.frame, objects)
                ok, buf = cv2.imencode(
                    ".jpg", annotated,
                    [int(cv2.IMWRITE_JPEG_QUALITY), STREAM.mjpeg_quality],
                )
                if not ok:
                    raise RuntimeError("JPEG encoding failed")
                jpeg = bytes(buf)

                # §3 step 8: commit with the SAME buffer the slot gets
                self._commit(drafts, jpeg, ctx)

                # §3 step 9: publish
                self._slot.publish(jpeg)

                dt = time.perf_counter() - t0
                self._durations.append(dt)
                if len(self._durations) > _FPS_WINDOW:
                    self._durations.pop(0)
                self.pipeline_fps = 1.0 / (sum(self._durations) / len(self._durations))
                self.frames_processed += 1
                tick += 1
        except Exception as e:  # noqa: BLE001 — session must die cleanly, server must not
            self.status = "error"
            self.error = f"{type(e).__name__}: {e}"
            log.exception("processing loop failed")
            # A5: SOURCE_LOST on read-fail abort (before status=error set
            # above is already done — but the draft is emitted HERE)
            if "read failed repeatedly" in str(e):
                try:
                    sys_ctx = FrameContext(
                        tick=tick, wall_ts=time.time(), video_ts=None,
                        luminance=128.0, is_night=False, shape=(1, 1))
                    self._commit([_sys_draft("SOURCE_LOST")], None, sys_ctx)
                except Exception:  # noqa: BLE001 — best effort on error path
                    log.warning("SOURCE_LOST draft emission failed")
        finally:
            self._source.release()
            self._finalize()

    # ---- A6 finalize (pinned order) ----

    def _finalize(self) -> None:
        """flush tracks -> DB -> SESSION_COMPLETED -> writer drain ->
        status flip. Runs exactly once (idempotent guard); error path =
        best-effort flush (honest partial)."""
        if self._finalized:
            return
        self._finalized = True
        try:
            if self._dao is not None and self._session_row_id is not None:
                # 1. flush tracks -> DB (§14 aggregates)
                rows = []
                for t in self._store.tracks.values():
                    rows.append((
                        t.track_id, t.class_name,
                        _iso(t.first_seen), _iso(t.last_seen),
                        t.frames_seen, t.max_conf))
                if rows:
                    self._dao.flush_tracks(self._session_row_id, rows)
                # 2. SESSION_COMPLETED commit (EOF path only — stopped/
                #    error paths update the row without the system event)
                if self.status == "completed":
                    sys_ctx = FrameContext(
                        tick=self.frames_processed, wall_ts=time.time(),
                        video_ts=None, luminance=128.0, is_night=False,
                        shape=(1, 1))
                    self._commit([_sys_draft("SESSION_COMPLETED")], None,
                                 sys_ctx)
                # 3. writer drain MUST precede the status row update
                if self._writer is not None:
                    self._writer.drain(timeout=5.0)
                self._dao.update_session(
                    self._session_row_id, self.status,
                    stats=self._stats_payload())
            elif self._writer is not None:
                self._writer.drain(timeout=5.0)
        except Exception as e:  # noqa: BLE001 — finalize is best-effort
            log.error("session finalize failed (best-effort partial): %s", e)

    def _stats_payload(self) -> dict:
        fence = self._analytics[0] if self._analytics else None
        return {
            "frames_processed": self.frames_processed,
            "pipeline_fps": round(self.pipeline_fps, 1),
            "events_committed": self.events_committed,
            "tracks_total": len(self._store.tracks),
            "zone_person_counts": fence.zone_person_counts() if fence else {},
        }

    # ---- status ----

    def status_payload(self) -> dict:
        fence = self._analytics[0] if self._analytics else None
        return {
            "source_id": self.source_id,
            "status": self.status,
            "device": self.device,
            "frames_processed": self.frames_processed,
            "pipeline_fps": round(self.pipeline_fps, 1),
            "active_tracks": self._store.count_active(),
            "total_tracks": len(self._store.tracks),
            "events_committed": self.events_committed,   # C9 rename
            "zone_person_counts": fence.zone_person_counts() if fence else {},
            "error": self.error or None,
            "uptime_s": round(time.time() - self._started_at, 1),
        }


# ---- app-scoped writer holder (installed by main lifespan) ----

_module_writer: Optional[EventWriter] = None


def set_writer(writer: Optional[EventWriter]) -> None:
    global _module_writer
    _module_writer = writer


def get_writer() -> Optional[EventWriter]:
    return _module_writer


# ---- one-active-session registry (module-level, minimal) ----

_active: Optional[ProcessingSession] = None
_lock = threading.Lock()


def get_active_session() -> Optional[ProcessingSession]:
    with _lock:
        return _active


def start_session(source: VideoSource,
                  zones: Optional[ZoneStore] = None,
                  dao: Optional[DAO] = None,
                  writer: Optional[EventWriter] = None,
                  hub: Optional[SseHub] = None) -> ProcessingSession:
    global _active
    with _lock:
        if _active is not None and _active.status in ("running", "starting"):
            raise SessionError(
                f"one active session rule: session '{_active.source_id}' is "
                f"{_active.status} — stop it first"
            )
        session = ProcessingSession(source, zones=zones, dao=dao,
                                    writer=writer, hub=hub)
        session.start()
        _active = session
        return session


def stop_active_session() -> Optional[ProcessingSession]:
    global _active
    with _lock:
        session = _active
        if session is not None:
            session.stop()
            _active = None
        return session


def make_source(spec: dict) -> VideoSource:
    """Minimal source factory for the dev-level control endpoints.

    type=webcam -> WebcamSource(index)
    type=file   -> FileSource(path)   (validated by FileSource at open)
    """
    stype = spec.get("type")
    if stype == "webcam":
        return WebcamSource(int(spec.get("index", 0)))
    if stype == "file":
        path = spec.get("path", "")
        if not path:
            raise SessionError("file session requires 'path'")
        return FileSource(path)
    raise SessionError(f"unknown source type: {stype!r} (use 'webcam' or 'file')")


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(
        timespec="milliseconds")
