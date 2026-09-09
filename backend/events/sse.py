"""TRINETRA SSE hub — live event delivery (M5, §16, frozen).

Engine publishes ONE json dict per committed event; every connected
client gets a COPY via its OWN bounded drop-oldest queue. A slow reader
lags (events dropped for it), never grows memory, never backpressures
the engine. The hub prunes a consumer when its generator exits
(asynccontextmanager closing) — no leak (§20 row: "SSE client drop ->
hub prunes consumer").
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Iterator

log = logging.getLogger("trinetra.events.sse")

_QUEUE_MAX = 100          # per-client bound (drop-oldest)


class _Client:
    __slots__ = ("q", "dropped")

    def __init__(self) -> None:
        self.q: "queue.Queue[dict]" = queue.Queue(maxsize=_QUEUE_MAX)
        self.dropped = 0            # honest per-client drop counter


class SseHub:
    """Thread-safe fan-out. publish() is called from the session thread
    (via the engine); streams run on the event loop's thread pool."""

    def __init__(self) -> None:
        self._clients: dict[int, _Client] = {}
        self._next_id = 1
        self._lock = threading.Lock()

    def publish(self, event: dict) -> None:
        """Non-blocking fan-out to every client; overflow drops the OLDEST
        (never blocks the engine — the engine is the session thread)."""
        with self._lock:
            clients = list(self._clients.values())
        for c in clients:
            try:
                c.q.put_nowait(event)
            except queue.Full:
                try:
                    c.q.get_nowait()      # drop oldest
                    c.dropped += 1
                    c.q.put_nowait(event)
                except queue.Empty:      # pragma: no cover — cannot happen
                    pass

    # ---- stream subscription ----

    def subscribe(self) -> tuple[int, _Client]:
        with self._lock:
            cid = self._next_id
            self._next_id += 1
            client = _Client()
            self._clients[cid] = client
            return cid, client

    def unsubscribe(self, cid: int) -> None:
        with self._lock:
            self._clients.pop(cid, None)

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def stream(self) -> Iterator[dict]:
        """Generator for a StreamingResponse body. Sends a keepalive
        comment every ~5s of silence so proxies/clients don't cut the
        line (and so live-path tests observe traffic quickly)."""
        import time
        cid, client = self.subscribe()
        try:
            while True:
                try:
                    yield client.q.get(timeout=5.0)
                except queue.Empty:
                    yield {"keepalive": True, "ts": time.time()}
        finally:
            self.unsubscribe(cid)
            if client.dropped:
                log.info("sse client %x dropped %d events (slow reader)",
                         cid, client.dropped)
