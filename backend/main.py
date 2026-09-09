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

_STARTED = time.time()

_BOUNDARY = "frame"
_MJPEG_HEADERS = {
    "Cache-Control": "no-cache, private",
    "Pragma": "no-cache",
}


class StartRequest(BaseModel):
    type: str                      # "webcam" | "file"
    index: int = 0                  # webcam only
    path: str = ""                 # file only


def _model_status() -> dict:
    target = cfg.MODELS_DIR / cfg.VISION.model
    return {
        "detector": {
            "file": cfg.VISION.model,
            "present": target.exists(),
            "size_mb": round(target.stat().st_size / 1e6, 1)
            if target.exists() else None,
        }
    }


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
    detector = _model_status()["detector"]
    writer = get_writer()
    return {
        "ok": bool(detector["present"]),   # model missing => RED
        "app": "TRINETRA",
        "phase": "M6",
        "uptime_s": round(time.time() - _STARTED, 1),
        "device_policy": DEVICE.policy,
        "models": {"detector": detector},
        "db": db,
        "writer": writer.health() if writer is not None
        else {"writer": "stopped"},
        "active_session": session.source_id if session is not None else None,
    }


@app.post("/api/session/start")
def session_start(req: StartRequest) -> dict:
    """F1: the REST product path hands the session the FULL app stack
    (SQLite zones, DAO, writer, hub) — sessions see real zones, events
    persist, SSE publishes, sessions/tracks rows are written.
    C7: model missing => 503 with an actionable message (server stays
    up; restoring the weights recovers the NEXT start — no restart)."""
    from backend.core.errors import get_zone_store, get_dao, get_hub
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
