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

    def stream(self) -> "Iterator[dict]":
        """SYNC generator (M5 surface — hub unit tests pin this).
        Sends a keepalive comment every ~5s of silence. The ASYNC
        endpoint path uses stream_async() (C1); this stays for tests
        and any sync consumer."""
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

    async def stream_async(self):
        """ASYNC generator for the FastAPI endpoint (M6 C1): poll-and-
        drain — await asyncio.sleep(0.05) + get_nowait() loop. BANNED:
        await asyncio.to_thread(q.get, timeout=...) — it re-imports the
        threadpool cap problem (every waiting client pins a threadpool
        thread). Hub internals (sync thread-safe fan-out) untouched:
        keepalive, prune-on-disconnect (finally/CancelledError), and
        drop-oldest semantics all survive from the M5 unit tests."""
        import asyncio
        import time
        cid, client = self.subscribe()
        try:
            while True:
                try:
                    yield client.q.get_nowait()
                except queue.Empty:
                    # quiet slice: brief async sleep (event loop stays
                    # live for OTHER clients), then keepalive at 5s
                    await asyncio.sleep(0.05)
                    if client.q.empty():
                        # approximate 5s keepalive cadence via sentinel
                        yield {"keepalive": True, "ts": time.time()}
                        await asyncio.sleep(4.9)
        except (GeneratorExit, asyncio.CancelledError):
            raise                      # prune via finally
        finally:
            self.unsubscribe(cid)
            if client.dropped:
                log.info("sse client %x dropped %d events (slow reader)",
                         cid, client.dropped)
