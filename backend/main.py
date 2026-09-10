"""TRINETRA — FastAPI application (M5).

ONE application, ONE port, workers=1 (in-process session state, §17).
M3 paths/payloads/409 behavior are preserved VERBATIM (regression
green required). M5 adds: db lifespan (migrations + retention sweep +
writer start/stop), routers (zones/events/evidence/stream), health
gains db:{ok} + active_session.

Run:  ./venv/bin/uvicorn backend.main:app --port 8000
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.api import events as events_api
from backend.api import evidence as evidence_api
from backend.api import hermes as hermes_api
from backend.api import map as map_api
from backend.api import sources as sources_api
from backend.api import stream as stream_api
from backend.api import zones as zones_api
from backend.core import config as cfg
from backend.core.config import DEVICE, PATHS, STREAM
from backend.core.errors import install as api_install
from backend.db import DAO, Database
from backend.db.migrations import MIGRATIONS
from backend.db.writer import EventWriter
from backend.events.sse import SseHub
from backend.services import (
    SessionError,
    get_active_session,
    make_source,
    start_session,
    stop_active_session,
)
from backend.services.session import get_writer, set_writer
from backend.vision import DetectorError

log = logging.getLogger("trinetra.main")

app = FastAPI(title="TRINETRA", version="0.7.0-m7")
app.include_router(zones_api.router)
app.include_router(events_api.router)
app.include_router(evidence_api.router)
app.include_router(stream_api.router)
app.include_router(map_api.router)
app.include_router(sources_api.router)
app.include_router(sources_api.sessions_router)
app.include_router(hermes_api.router)

_STARTED = time.time()

_BOUNDARY = "frame"
_MJPEG_HEADERS = {
    "Cache-Control": "no-cache, private",
    "Pragma": "no-cache",
}


class StartRequest(BaseModel):
    type: str                      # "webcam" | "file" | "rtsp"
    index: int = 0                  # webcam only
    path: str = ""                 # file only
    uri: str = ""                  # rtsp only


def _model_status() -> dict:
    target = cfg.MODELS_DIR / cfg.VISION.model
    reid_onnx = cfg.MODELS_DIR / cfg.REID.onnx_path
    face_onnx = cfg.MODELS_DIR / "yunet.onnx"
    pose_model = cfg.MODELS_DIR / "yolov8n-pose.pt"
    anpr_model = cfg.MODELS_DIR / "yolov8n_plate.pt"
    out = {
        "detector": {
            "file": cfg.VISION.model,
            "present": target.exists(),
            "size_mb": round(target.stat().st_size / 1e6, 1)
            if target.exists() else None,
        },
        # Phase 2: the fast-reid ONNX presence gate (honest — a missing
        # file means the Re-ID capability reports absent and sessions
        # run without it; nothing is fabricated).
        "reid": {
            "file": cfg.REID.onnx_path,
            "present": reid_onnx.exists(),
            "size_mb": round(reid_onnx.stat().st_size / 1e6, 1)
            if reid_onnx.exists() else None,
        },
        # Phase 3: YuNet face detection presence gate (honest — missing
        # model file disables face detection cleanly without error).
        "face": {
            "file": "yunet.onnx",
            "present": face_onnx.exists(),
            "size_mb": round(face_onnx.stat().st_size / 1e6, 1)
            if face_onnx.exists() else None,
        },
        # Phase 8: YOLOv8 pose estimation presence gate (honest — missing
        # model file disables pose keypoint detection cleanly without error).
        "pose": {
            "file": "yolov8n-pose.pt",
            "present": pose_model.exists(),
            "size_mb": round(pose_model.stat().st_size / 1e6, 1)
            if pose_model.exists() else None,
        },
        # Phase 6: ANPR plate detection presence gate (honest — missing
        # weights triggers heuristic fallback mode with zero cloud calls).
        "anpr": {
            "file": "yolov8n_plate.pt",
            "present": anpr_model.exists(),
            "size_mb": round(anpr_model.stat().st_size / 1e6, 1)
            if anpr_model.exists() else None,
            "mode": "model" if anpr_model.exists() else "heuristic_fallback",
        },
    }
    return out


@app.get("/api/health")
def health() -> dict:
    """C7 model-missing shape: ok:False + detector.present:False when the
    weights file is absent; sessions are blocked with a clear message
    (503) but the SERVER stays up — restoring the file recovers the NEXT
    session start WITHOUT a restart (per-session load is the design)."""
    dao = None
    try:
        from backend.core.errors import get_dao
        dao = get_dao()
        db = dao.health()
    except Exception:
        db = {"ok": False}
    session = get_active_session()
    models = _model_status()
    detector = models["detector"]
    reid = models["reid"]
    face = models["face"]
    pose = models["pose"]
    anpr = models["anpr"]
    writer = get_writer()
    return {
        "ok": bool(detector["present"]),   # model missing => RED
        "app": "TRINETRA",
        "phase": "M6",
        "uptime_s": round(time.time() - _STARTED, 1),
        "device_policy": DEVICE.policy,
        "models": {"detector": detector, "reid": reid, "face": face, "pose": pose, "anpr": anpr},
        "db": db,
        "writer": writer.health() if writer is not None
        else {"writer": "stopped"},
        "active_session": session.source_id if session is not None else None,
        "reid_enabled": cfg.REID.enabled and reid["present"],
        "face_enabled": face["present"],
        "pose_enabled": pose["present"],
        "anpr_mode": anpr["mode"],
    }


@app.post("/api/session/start")
def session_start(req: StartRequest) -> dict:
    """F1: the REST product path hands the session the FULL app stack
    (SQLite zones, DAO, writer, hub) — sessions see real zones, events
    persist, SSE publishes, sessions/tracks rows are written.
    C7: model missing => 503 with an actionable message (server stays
    up; restoring the weights recovers the NEXT start — no restart)."""
    from backend.core.errors import get_zone_store, get_dao, get_hub, get_reid_service
    if not (cfg.MODELS_DIR / cfg.VISION.model).exists():
        raise HTTPException(
            status_code=503,
            detail=f"detector model missing: "
                   f"{cfg.MODELS_DIR / cfg.VISION.model} "
                   f"— restore the file (health is RED); no server restart "
                   f"is needed, the next session start will load it")
    try:
        source = make_source(req.model_dump())
        session = start_session(
            source,
            zones=get_zone_store(),
            dao=get_dao(),
            writer=get_writer(),
            hub=get_hub(),
            reid_service=get_reid_service(),
        )
    except SessionError as e:
        if "one active session" in str(e):
            raise HTTPException(status_code=409, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
    except DetectorError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except HTTPException:
        # §20 DB-closed row: errors.py get_dao()/get_zone_store() raise
        # a CLEAN 503 (lifespan never ran / DB unavailable) — re-raise
        # verbatim, never re-wrapped as 400 by the generic handler.
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "ok", "session": session.status_payload()}


@app.post("/api/session/stop")
def session_stop() -> dict:
    session = stop_active_session()
    if session is None:
        return {"status": "ok", "stopped": None}
    return {"status": "ok", "stopped": session.status_payload()}


@app.get("/api/session/status")
def session_status() -> dict:
    session = get_active_session()
    if session is None:
        return {"active": False, "session": None}
    return {"active": True, "session": session.status_payload()}


@app.post("/api/session/pause")
def session_pause() -> dict:
    session = get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="no active session")
    session.pause()
    return {"status": "ok", "paused": True, "session": session.status_payload()}


@app.post("/api/session/resume")
def session_resume() -> dict:
    session = get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="no active session")
    session.resume()
    return {"status": "ok", "paused": False, "session": session.status_payload()}


@app.post("/api/session/speed")
def session_speed(req: dict) -> dict:
    session = get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="no active session")
    speed = req.get("speed")
    if speed is None:
        raise HTTPException(status_code=400, detail="missing 'speed' parameter")
    try:
        new_speed = session.set_speed(float(speed))
    except (ValueError, TypeError, SessionError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"status": "ok", "speed": new_speed, "session": session.status_payload()}


@app.post("/api/session/step")
def session_step() -> dict:
    session = get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="no active session")
    session.step()
    return {"status": "ok", "stepped": True}


class SeekRequest(BaseModel):
    timestamp: Optional[float] = None
    video_ts: Optional[float] = None


@app.post("/api/session/seek")
def session_seek(req: SeekRequest) -> dict:
    session = get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="no active session")
    target_ts = req.video_ts if req.video_ts is not None else req.timestamp
    if target_ts is None:
        raise HTTPException(status_code=400, detail="timestamp or video_ts is required")
    ok = session.seek(float(target_ts))
    if not ok:
        raise HTTPException(status_code=400, detail="seek failed (source does not support seek or invalid timestamp)")
    return {"status": "ok", "timestamp": target_ts}


# ---- V3 render layers (C7: inline in the session region — no new
# router, no include/lifespan/_DIST edits). Contract pinned in the
# architecture handoff §3: partial merge, UNKNOWN key → 400 (a typo'd
# toggle silently ignored would be a dead control), 404 when no
# active session. ----

@app.get("/api/session/layers")
def session_layers_get() -> dict:
    session = get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="no active session")
    return {"layers": session.get_layers()}


@app.post("/api/session/layers")
def session_layers_post(updates: dict) -> dict:
    session = get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="no active session")
    try:
        layers = session.update_layers(updates)
    except SessionError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"layers": layers}


# ---- Phase 2: Re-ID investigation surface (INLINE per C7-override in
# the full handoff §4-Phase2 — no new router file, no include-block
# edit). GET /api/reid/persons (all_persons) + GET /api/reid/persons/
# {pid} (person_summary). Honest empty when no identities / no
# service; 404-clean for unknown pids. ----

@app.get("/api/reid/persons")
def reid_persons() -> dict:
    from backend.core.errors import get_reid_service
    svc = get_reid_service()
    if svc is None:
        return {"persons": [], "count": 0,
                "note": "re-id not initialized (capability disabled or "
                        "model absent) — no identities exist"}
    persons = svc.all_persons()
    return {"persons": persons, "count": len(persons)}


@app.get("/api/reid/persons/{pid}")
def reid_person_detail(pid: str) -> dict:
    from backend.core.errors import get_reid_service
    svc = get_reid_service()
    if svc is None:
        raise HTTPException(
            404, f"person {pid} not found — re-id not initialized")
    summary = svc.person_summary(pid)
    if summary is None:
        raise HTTPException(404, f"person {pid} not found")
    return summary


@app.get("/api/frame.jpg")
def latest_frame() -> Response:
    session = get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="no active session")
    data = session.slot.peek()
    if data is None:
        raise HTTPException(status_code=404, detail="no frame published yet")
    return Response(content=data, media_type="image/jpeg",
                    headers=_MJPEG_HEADERS)


def _mjpeg_generator(session):
    while True:
        if session.status not in ("running", "starting"):
            break
        data = session.slot.wait_new(timeout=2.0)
        if data is None:
            continue
        yield (
            f"--{_BOUNDARY}\r\n"
            f"Content-Type: image/jpeg\r\n"
            f"Content-Length: {len(data)}\r\n\r\n"
        ).encode() + data + b"\r\n"


@app.get("/api/stream.mjpg")
def stream_mjpeg() -> StreamingResponse:
    session = get_active_session()
    if session is None:
        raise HTTPException(
            status_code=404, detail="no active session — start one first")
    return StreamingResponse(
        _mjpeg_generator(session),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
        headers=_MJPEG_HEADERS,
    )


# ---- lifespan: db migrations + retention sweep + writer + api state (C1) ----

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from backend.core.config import DB_PATH
    from backend.core.errors import _state
    from backend.analytics import ZoneStore
    if _state.dao is not None:
        # a test (or embedder) pre-installed its own DAO/hub — honor it
        # and only ensure migrations + writer exist on that instance.
        database = _state.dao.db
        dao = _state.dao
        hub = _state.hub or SseHub()
    else:
        database = Database(DB_PATH)
        database.migrate(MIGRATIONS)
        dao = DAO(database)
        hub = SseHub()
    database.migrate(MIGRATIONS)           # idempotent (user_version)
    writer = EventWriter(dao)
    writer.start()
    # F1: the app-scoped SQLite-backed ZoneStore — created HERE (it was
    # built nowhere; sessions started via REST would have seen an empty
    # in-memory store). install() stores it in ApiState.zone_store.
    api_install(dao, hub, zone_store=ZoneStore(dao=dao))
    set_writer(writer)
    # Phase 2: the app-scoped MultiCameraReIdService — created when the
    # capability is config-enabled (honest: absent model => the
    # embedder's availability gate makes every process_tick a NO-OP;
    # nothing is fabricated). The ONNX net itself loads LAZILY on the
    # first embed (§44 — never at boot). Sessions register their
    # source_id as the camera id (single-session MVP).
    if cfg.REID.enabled:
        try:
            from backend.reid import MultiCameraReIdService
            _state.reid_service = MultiCameraReIdService()
            log.info("re-id service installed (embedder=%s onnx=%s)",
                     cfg.REID.embedder,
                     (cfg.MODELS_DIR / cfg.REID.onnx_path).exists())
        except Exception as e:  # noqa: BLE001 — capability must never kill boot
            log.warning("re-id service init failed (capability off): %s", e)
    # one-shot retention sweep (C11) — startup, not the writer loop
    try:
        removed = dao.prune_evidence(PATHS.retention_days)
        if removed:
            log.info("retention sweep removed %d evidence files", removed)
    except Exception as e:  # noqa: BLE001 — sweep must never block boot
        log.warning("retention sweep failed: %s", e)
    log.info("TRINETRA M5 up — db=%s writer=started", DB_PATH)
    try:
        yield
    finally:
        w = get_writer()
        if w is not None:
            w.stop()
        log.info("TRINETRA M5 shutdown — writer drained & stopped")


app.router.lifespan_context = lifespan


# ---- M7: serve the built Command Center bundle (non-critical) ----
# If frontend/dist exists (npm run build), the operator UI is served at
# /. If it does not, the API works exactly as before — the UI is NEVER a
# boot dependency. Map/tile failures degrade only the map panel.

from fastapi.staticfiles import StaticFiles  # noqa: E402 — after app

_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True),
              name="command-center")
    log.info("command center bundle served from %s", _DIST)
else:
    log.info("no command center bundle (frontend/dist absent) — API-only")
