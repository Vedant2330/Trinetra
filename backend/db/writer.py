"""TRINETRA event writer — ONE DB writer thread (M5 §13/§14, M6 C4).

Design (frozen §13 delivery): Engine -> bounded queue -> this thread ->
SQLite batch insert. The queue is BOUNDED and BLOCKS the producer when
full (B3: backpressure is the design — the session loop slows, nothing
is lost and nothing grows unboundedly).

M6 C4 failure classification:
  - sqlite3.OperationalError (locked/busy)  = RETRYABLE: retry x3 with
    backoff 0.1/0.5/2s (busy_timeout absorbs the common case) -> PAUSE
    (stop consuming; probe SELECT 1 ~1s; resume = re-attempt the SAME
    head batch; zero loss; the queue backpressures the producer).
  - anything else (IntegrityError/malformed) = POISON: drop the batch,
    unlink that batch's snapshot files, dropped_batches++.
  - Session finalize during a PAUSE: drain timeout 5s then proceed
    (queued rows flush on recovery; FK intact) — documented shutdown
    caveat. writer.stop() = one final attempt, then drop + log.
  - Health surfaces writer state: ok | paused (C4/C7 surface).
"""

from __future__ import annotations

import logging
import queue
import sqlite3
import threading
from pathlib import Path
from typing import Optional

from backend.db.dao import DAO

log = logging.getLogger("trinetra.db.writer")

_QUEUE_MAX = 2000          # bounded: blocks the producer (session thread)
_DRAIN_TIMEOUT = 5.0
_BATCH_MAX = 200
_RETRY_DELAYS = (0.1, 0.5, 2.0)     # C4 retry ladder before PAUSE
_PROBE_INTERVAL = 1.0               # PAUSE: SELECT 1 probe cadence


class WriterError(Exception):
    """Raised only for lifecycle misuse (double start, etc.)."""


class EventWriter:
    """Single consumer, single producer (the session thread via the
    engine). All inserts happen on THIS thread's DB connection (C3)."""

    def __init__(self, dao: DAO, queue_max: int = _QUEUE_MAX,
                 batch_delay: float = 0.0,
                 retry_delays: tuple = _RETRY_DELAYS) -> None:
        """`batch_delay` (seconds) artificially slows each batch — a
        TEST INJECTION point for B3 (queue-full blocking observed).
        `retry_delays` overridable for fast drills."""
        self._dao = dao
        self._queue: "queue.Queue[tuple]" = queue.Queue(maxsize=queue_max)
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._drained = threading.Event()
        self._drained.set()          # empty = drained
        self._batch_delay = batch_delay
        self._retry_delays = retry_delays
        self.committed = 0           # rows successfully inserted
        self.dropped_batches = 0     # honest failure counter
        self.state = "ok"            # ok | paused (C4 health surface)
        self.paused = threading.Event()
        self.retry_count = 0         # honest total retryable failures seen

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
        """Signal stop; WAIT for drain (A6: drain precedes status flip).
        A paused writer gets drain_timeout to recover, then proceeds —
        queued rows flush on the next writer's watch (documented
        shutdown caveat, C4)."""
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
        head: Optional[list] = None    # retained across PAUSE (zero loss)
        while True:
            draining = self._stop.is_set()
            if head is None:
                try:
                    first = self._queue.get_nowait()
                except queue.Empty:
                    self._drained.set()
                    if draining:
                        return
                    # idle tick — re-check stop without busy-spinning
                    self._stop.wait(0.05)
                    continue
                head = [first]
                while len(head) < _BATCH_MAX:
                    try:
                        head.append(self._queue.get_nowait())
                    except queue.Empty:
                        break
            if self._batch_delay > 0:
                # test injection: simulate a slow consumer (B3)
                self._stop.wait(self._batch_delay)

            # ---- attempt the batch (retry -> pause -> resume same head) ----
            outcome = self._attempt(head)

            if outcome == "ok":
                self.committed += len(head)
                self._register_evidence(head)
                head = None
            elif outcome == "retryable":
                result = self._retries_exhausted(head)
                if result is True:        # 3 retries failed -> PAUSE
                    self._pause_until_recovered()
                    if self._stop.is_set():
                        # stop requested during/after the pause: give the
                        # queued head ONE final attempt then exit — never
                        # spin (stop must always win; C4 shutdown caveat).
                        try:
                            self._dao.insert_events(head)
                            self.committed += len(head)
                            self._register_evidence(head)
                        except Exception as e:  # noqa: BLE001
                            log.error("final attempt during stop failed; "
                                      "dropping %d queued rows: %s",
                                      len(head), e)
                            self.dropped_batches += 1
                        head = None
                    continue              # resume: re-attempt SAME head
                elif result == "poison-recovered":
                    head = None           # dropped inside the ladder
                # result False = recovered mid-ladder; head already
                # committed + evidence registered -> consume it
                else:
                    head = None
            else:  # poison — drop batch + unlink snapshots + count
                self._drop_poison(head)
                self.dropped_batches += 1
                head = None
            if head is None and self._stop.is_set():
                # drain what's already queued, then exit promptly
                try:
                    last = []
                    while True:
                        try:
                            last.append(self._queue.get_nowait())
                        except queue.Empty:
                            break
                    if last:
                        try:
                            self._dao.insert_events(last)
                            self.committed += len(last)
                            self._register_evidence(last)
                        except Exception as e:  # noqa: BLE001
                            log.error("stop-drain batch failed; dropping "
                                      "%d rows: %s", len(last), e)
                            self.dropped_batches += 1
                except Exception:  # pragma: no cover — best effort
                    pass
                self._drained.set()
                return

    # ---- batch attempt + classification (C4) ----

    def _attempt(self, batch: list) -> str:
        try:
            self._dao.insert_events(batch)
            return "ok"
        except sqlite3.OperationalError as e:
            log.warning("DB busy/locked (%s) — retryable", e)
            return "retryable"
        except Exception as e:  # noqa: BLE001 — poison must not kill writer
            log.error("poison batch (%s) — dropping %d events",
                      e, len(batch))
            return "poison"

    def _retries_exhausted(self, batch: list):
        """Run the retry ladder for the CURRENT head batch.
        True  = all retries failed (caller PAUSEs; head retained).
        False = a retry succeeded (batch committed + evidence + counted).
        'poison-recovered' = poison surfaced mid-ladder (batch dropped)."""
        for i, delay in enumerate(self._retry_delays, start=1):
            self._stop.wait(delay)         # interruptible, never time.sleep
            try:
                self._dao.insert_events(batch)
                self.committed += len(batch)
                self._register_evidence(batch)
                return False
            except sqlite3.OperationalError:
                log.warning("retry %d/%d failed (busy)", i,
                            len(self._retry_delays))
            except Exception as e:  # noqa: BLE001 — poison during retry
                log.error("poison batch during retry (%s) — dropping", e)
                self._drop_poison(batch)
                self.dropped_batches += 1
                return "poison-recovered"
        return True

    def _pause_until_recovered(self) -> None:
        """PAUSE: stop consuming, probe SELECT 1 every ~1s, resume the
        moment the DB answers. The producer keeps enqueueing until the
        bounded queue fills — then IT blocks (backpressure, by design)."""
        self.state = "paused"
        self.paused.set()
        log.warning("writer PAUSED (DB unavailable) — queue backpressures; "
                    "probing every %.1fs", _PROBE_INTERVAL)
        while not self._stop.is_set():
            self._stop.wait(_PROBE_INTERVAL)
            try:
                self._dao.conn.execute("SELECT 1").fetchone()
                break
            except sqlite3.Error:
                continue
        self.paused.clear()
        self.state = "ok"
        log.info("writer RESUMED")

    # ---- poison + evidence (A6/C4) ----

    @staticmethod
    def _drop_poison(batch: list) -> None:
        """Poison batch: drop rows AND unlink their snapshot files (the
        evidence files are orphaned otherwise — C4/A4 cleanup-at-source)."""
        for row in batch:
            sp = row[12]
            if sp:
                try:
                    Path(sp).unlink(missing_ok=True)
                except OSError:      # pragma: no cover — best effort
                    log.warning("could not unlink snapshot %s", sp)

    def _register_evidence(self, batch: list) -> None:
        """Evidence rows AFTER the event rows land (FK order)."""
        for row in batch:
            sp = row[12]
            if sp:
                try:
                    self._dao.insert_evidence(row[0], "snapshot", sp)
                except Exception as e:  # noqa: BLE001 — evidence is
                    # best-effort; the event row is the record
                    log.warning("evidence row insert failed for %s: %s",
                                row[0], e)

    def drain(self, timeout: float = _DRAIN_TIMEOUT) -> bool:
        """Explicit wait-until-empty (finalize path, A6). A paused
        writer may never drain within the timeout — the finalize path
        proceeds anyway (documented shutdown caveat, C4)."""
        return self._drained.wait(timeout=timeout)

    def health(self) -> dict:
        return {"writer": self.state, "pending": self.pending,
                "dropped_batches": self.dropped_batches}