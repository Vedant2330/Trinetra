"""TRINETRA events — the committed-event layer (M5, §13).

EventEngine.commit() is pipeline step 8 (§3): drafts in -> committed
events out -> (writer queue, SSE hub, evidence files).

SSE hub (§16): per-client bounded drop-oldest queues — a slow client
lags, never grows memory; hub prunes dead consumers on generator exit.
"""

from backend.events.engine import CommittedEvent, EventEngine
from backend.events.sse import SseHub

__all__ = ["CommittedEvent", "EventEngine", "SseHub"]
