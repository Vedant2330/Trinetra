"""TRINETRA — FastAPI application (M3).

ONE application: health (M0), session control + MJPEG streaming (M3).
SSE arrives in M5. The session registry enforces ONE active session.

Run:  ./venv/bin/uvicorn backend.main:app --port 8000
"""

from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.core.config import DEVICE, MODELS_DIR, STREAM, VISION
from backend.services import (
    SessionError,
    get_active_session,
    make_source,
    start_session,
    stop_active_session,
)

app = FastAPI(title="TRINETRA", version="0.3.0-m3")
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
    target = MODELS_DIR / VISION.model
    return {
        "detector": {
            "file": VISION.model,
            "present": target.exists(),
            "size_mb": round(target.stat().st_size / 1e6, 1) if target.exists() else None,
        }
    }


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "app": "TRINETRA",
        "phase": "M3",
        "uptime_s": round(time.time() - _STARTED, 1),
        "device_policy": DEVICE.policy,
        "models": _model_status(),
    }


@app.post("/api/session/start")
def session_start(req: StartRequest) -> dict:
    try:
        source = make_source(req.model_dump())
        session = start_session(source)
    except SessionError as e:
        # lifecycle/spec errors -> 409 conflict is wrong for bad specs;
        # one-active-session conflicts are 409, invalid requests 400
        if "one active session" in str(e):
            raise HTTPException(status_code=409, detail=str(e)) from e
        raise HTTPException(status_code=400, detail=str(e)) from e
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
    """Latest ANNOTATED JPEG (non-consuming peek). 404 before first frame."""
    session = get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="no active session")
    data = session.slot.peek()
    if data is None:
        raise HTTPException(status_code=404, detail="no frame published yet")
    return Response(content=data, media_type="image/jpeg", headers=_MJPEG_HEADERS)


def _mjpeg_generator(session):
    """Yield multipart frames from the ONE processing loop's latest slot.

    No per-client inference: this generator only consumes shared JPEGs.
    Ends when the session leaves running state (stop/EOF/error) and the
    slot goes quiet.
    """
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
        raise HTTPException(status_code=404, detail="no active session — start one first")
    return StreamingResponse(
        _mjpeg_generator(session),
        media_type=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
        headers=_MJPEG_HEADERS,
    )
