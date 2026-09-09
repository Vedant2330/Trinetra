"""TRINETRA event writer — ONE DB writer thread (M5, §13/§14).

Design (frozen §13 delivery): Engine -> bounded queue -> this thread ->
SQLite batch insert. The queue is BOUNDED and BLOCKS the producer when
full (B3: backpressure is the design — the session loop slows, nothing
is lost and nothing grows unboundedly).

Failure behavior (A6, §20): catch-all around each batch. A DB error
kills NEITHER the writer thread NOR the session — the batch is dropped
with a logged error and consumption continues. retry×3 + queue-pause
machinery is explicitly M6 scope, not here.
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

from backend.db.dao import DAO

log = logging.getLogger("trinetra.db.writer")

_QUEUE_MAX = 2000          # bounded: blocks the producer (session thread)
_DRAIN_TIMEOUT = 5.0


class WriterError(Exception):
    """Raised only for lifecycle misuse (double start, etc.)."""


class EventWriter:
    """Single consumer, single producer (the session thread via the
    engine). All inserts happen on THIS thread's DB connection (C3)."""

    def __init__(self, dao: DAO, queue_max: int = _QUEUE_MAX,
                 batch_delay: float = 0.0) -> None:
        """`batch_delay` (seconds) artificially slows each batch — a
        TEST INJECTION point for B3 (queue-full blocking observed)."""
        self._dao = dao
        self._queue: "queue.Queue[tuple]" = queue.Queue(maxsize=queue_max)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._drained = threading.Event()
        self._drained.set()          # empty = drained
        self._batch_delay = batch_delay
        self.committed = 0           # rows successfully inserted
        self.dropped_batches = 0     # honest failure counter

    # ---- producer side (called from the session thread) ----

    def enqueue(self, row: tuple) -> None:
        """Block until space (B3 design). Called per committed event."""
        self._drained.clear()
        self._queue.put(row)

    # ---- lifecycle ----

    def start(self) -> None:
        if self._thread is not None:
            raise WriterError("writer already started")
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, name="trinetra-writer", daemon=True)
        self._thread.start()

    def stop(self, drain_timeout: float = _DRAIN_TIMEOUT) -> None:
        """Signal stop; WAIT for drain (A6: drain precedes status flip)."""
        self._stop.set()
        if self._thread is not None:
            self._drained.wait(timeout=drain_timeout)
            self._thread.join(timeout=drain_timeout)
            self._thread = None

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    # ---- consumer ----

    def _run(self) -> None:
        while True:
            draining = self._stop.is_set()
            try:
                first = self._queue.get_nowait()
            except queue.Empty:
                self._drained.set()
                if draining:
                    return
                # idle tick — re-check stop without busy-spinning
                self._stop.wait(0.05)
                continue
            batch = [first]
            while len(batch) < 200:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break
            if self._batch_delay > 0:
                # test injection: simulate a slow consumer (B3)
                self._stop.wait(self._batch_delay)
            try:
                n = self._dao.insert_events(batch)
                self.committed += n
                # evidence rows for snapshots: AFTER the event rows exist
                # (FK order); the path rides in the row's metadata JSON.
                import json as _json
                for row in batch:
                    meta = _json.loads(row[13] or "{}")
                    sp = row[12]
                    if sp:
                        try:
                            self._dao.insert_evidence(row[0], "snapshot", sp)
                        except Exception as e:  # noqa: BLE001 — evidence is
                            # best-effort; the event row is the record
                            log.warning("evidence row insert failed for %s: %s",
                                        row[0], e)
            except Exception as e:  # noqa: BLE001 — writer must survive (A6)
                self.dropped_batches += 1
                log.error("DB batch insert failed; dropping %d events: %s",
                          len(batch), e)

    def drain(self, timeout: float = _DRAIN_TIMEOUT) -> bool:
        """Explicit wait-until-empty (finalize path, A6)."""
        return self._drained.wait(timeout=timeout)
