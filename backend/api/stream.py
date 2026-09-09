"""TRINETRA live streams API (M5, §16).

GET /api/stream/events — SSE: one JSON frame per committed event,
auto-reconnect built into the EventSource protocol (§16 frozen: SSE over
WebSocket — control is REST; polling fallback = /api/events).
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.core.errors import get_hub

log = logging.getLogger("trinetra.api.stream")
router = APIRouter(prefix="/api/stream", tags=["stream"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",       # nginx: don't buffer SSE
}


@router.get("/events")
def stream_events() -> StreamingResponse:
    hub = get_hub()

    def gen():
        for event in hub.stream():
            if event.get("keepalive"):
                yield ": keepalive\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers=_SSE_HEADERS)
