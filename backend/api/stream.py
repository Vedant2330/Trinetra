"""TRINETRA live streams API (M5 §16, M6 C1 async).

GET /api/stream/events — SSE: one JSON frame per committed event,
auto-reconnect built into the EventSource protocol (§16 frozen: SSE over
WebSocket — control is REST; polling fallback = /api/events).

M6 C1: the endpoint is an ASYNC generator (poll-and-drain —
await asyncio.sleep(0.05) + get_nowait(); to_thread(q.get) is BANNED:
each waiting client would pin a threadpool thread). The hub's sync
thread-safe fan-out is untouched (M5 hub unit tests stay green).
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
async def stream_events() -> StreamingResponse:
    hub = get_hub()

    async def gen():
        async for event in hub.stream_async():
            if event.get("keepalive"):
                yield ": keepalive\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        gen(), media_type="text/event-stream", headers=_SSE_HEADERS)
