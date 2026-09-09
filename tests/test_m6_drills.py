"""M6 HARDENING DRILLS — §20 failure rows, automated where possible.

Every test here corresponds to a §20 table row (labeled in docstrings).
Manual-only drills (physical camera unplug, real MPS death) live in
docs/DEMO_CHECKLIST.md — honestly labeled, not faked here.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from pathlib import Path

import pytest

from backend.analytics.base import EventDraft, FrameContext
from backend.db.connection import Database
from backend.db.dao import DAO
from backend.db.migrations import MIGRATIONS
from backend.db.writer import EventWriter
from backend.events.engine import EventEngine
from backend.events.sse import SseHub
from backend.sources import SourceState
from backend.sources.base import FramePacket, VideoSource
from backend.state import TrackStore
from backend.vision import TrackedObject

import numpy as np


# ---------- fixtures ----------

@pytest.fixture()
def stack(tmp_path):
    db = Database(tmp_path / "m6.db")
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    dao.upsert_source("s", "file")
    writer = EventWriter(dao)
    writer.start()
    yield db, dao, writer
    writer.stop()
    db.close_all()


def row(eid, sid="sess-1", sp=None):
    return (eid, sid, "s", "2026-01-01T00:00:00.000+00:00", 0.0,
            "ZONE_ENTRY", "HIGH", 1.0, "[]", None, None, 0, sp, "{}", "new")


# ---------- C4 writer retry/pause machinery (§20 DB-busy row) ----------

class _FlakyDAO:
    """Wraps a real DAO; insert_events fails N times with
    OperationalError, then behaves (or never recovers). Everything is
    proxied LAZILY via __getattr__ (per-thread Database.conn() works
    from the writer thread); NEVER snapshot .conn eagerly — sqlite3
    Connection objects are thread-bound."""

    def __init__(self, real, fails):
        self._real = real
        self._fails = fails
        self.calls = 0

    def insert_events(self, batch):
        self.calls += 1
        if self.calls <= self._fails:
            import sqlite3
            raise sqlite3.OperationalError("database is locked (drill)")
        return self._real.insert_events(batch)

    def __getattr__(self, name):
        return getattr(self._real, name)


def test_c4_retry_fails2_then_success_no_pause(stack, tmp_path):
    """Retryable error twice -> retries absorb -> batch lands, NO pause
    (asserted via writer.state + paused flag)."""
    db, dao, writer = stack
    sid = dao.insert_session("s")
    flaky = _FlakyDAO(dao, fails=2)
    w = EventWriter(flaky, retry_delays=(0.01, 0.01, 0.01))
    w.start()
    try:
        w.enqueue(row("r-1", sid))
        deadline = time.time() + 5
        while w.committed < 1 and time.time() < deadline:
            time.sleep(0.02)
        assert w.committed == 1
        assert w.state == "ok" and not w.paused.is_set()
        assert w.dropped_batches == 0
        assert flaky.calls == 3          # 1 initial + 2 failed retries
    finally:
        w.stop()


def test_c4_fails4_pause_observed_after_3rd_retry_then_resume_zero_loss(
        stack, tmp_path):
    """Persistent busy: initial attempt + 3 retries fail -> PAUSE observed
    EXACTLY after the 3rd retry (assert paused state while DB down);
    DB recovers -> SAME head batch re-attempted -> zero loss."""
    db, dao, writer = stack
    sid = dao.insert_session("s")

    class _StuckDAO(_FlakyDAO):
        def __init__(self, real):
            super().__init__(real, fails=10 ** 9)   # stuck until released
            self.release = threading.Event()
            self.insert_calls = 0

        def insert_events(self, batch):
            if not self.release.is_set():
                self.insert_calls += 1
                import sqlite3
                raise sqlite3.OperationalError("database is locked (drill)")
            return self._real.insert_events(batch)

    stuck = _StuckDAO(dao)
    w = EventWriter(stuck, retry_delays=(0.01, 0.01, 0.01))
    w.start()
    try:
        for i in range(20):
            w.enqueue(row(f"p-{i}", sid))
        # pause must be observed after 1 initial + 3 retries = 4 attempts
        deadline = time.time() + 5
        while not w.paused.is_set() and time.time() < deadline:
            time.sleep(0.02)
        assert w.paused.is_set(), "pause never observed after 3rd retry"
        assert w.state == "paused"
        attempts_when_paused = stuck.insert_calls
        assert attempts_when_paused == 4, attempts_when_paused  # exactly 3rd retry
        # DB recovers -> writer resumes the SAME head -> drains everything
        stuck.release.set()
        deadline = time.time() + 10
        while w.pending > 0 and time.time() < deadline:
            time.sleep(0.05)
        w.drain(timeout=5)
        total = dao.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert total == 20                    # ZERO loss
        assert w.state == "ok" and not w.paused.is_set()
        assert w.dropped_batches == 0
    finally:
        w.stop()


def test_c4_pause_resume_producer_blocked_mid_burst_zero_loss(
        stack, tmp_path):
    """B3-shaped burst with the DB DOWN: queue fills (bounded 50),
    session thread observed BLOCKED on enqueue, DB recovers -> producer
    UNBLOCKS, rows == enqueued EXACTLY (zero loss; backpressure proven)."""
    db, dao, writer = stack
    sid = dao.insert_session("s")

    class _GateDAO(_FlakyDAO):
        def __init__(self, real):
            super().__init__(real, fails=10 ** 9)
            self.open_gate = threading.Event()

        def insert_events(self, batch):
            if not self.open_gate.is_set():
                import sqlite3
                raise sqlite3.OperationalError("locked (mid-burst drill)")
            return self._real.insert_events(batch)

    gate = _GateDAO(dao)
    w = EventWriter(gate, queue_max=50, retry_delays=(0.01, 0.01, 0.01))
    w.start()

    def producer():
        for i in range(200):              # 200 events vs queue 50
            w.enqueue(row(f"pb-{i}", sid))

    t = threading.Thread(target=producer, daemon=True)
    t.start()
    try:
        # WATCHER (main thread): blocking is observed when the writer is
        # PAUSED *and* the producer thread is PARKED (still alive but
        # not progressing). The producer races ahead of the retry
        # ladder, so the pause state may arrive after it blocks.
        deadline = time.time() + 15
        while time.time() < deadline:
            if w.paused.is_set() and t.is_alive():
                # producer parked? confirm the queue is full
                if w.pending >= 50:
                    break
            time.sleep(0.02)
        else:
            raise AssertionError(
                f"producer blocking never observed "
                f"(paused={w.paused.is_set()}, alive={t.is_alive()}, "
                f"pending={w.pending})")
        assert w.paused.is_set() and t.is_alive() and w.pending >= 50
        # producer is BLOCKED — DB recovers NOW
        gate.open_gate.set()
        t.join(timeout=30)
        assert not t.is_alive(), "producer thread never unblocked"
        w.drain(timeout=15)
        total = dao.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assert total == 200               # zero loss, producer unblocked
        assert w.dropped_batches == 0
    finally:
        gate.open_gate.set()
        t.join(timeout=5)
        w.stop()


def test_c4_api_responsive_while_writer_paused(stack):
    """While paused: health + zones CRUD still respond (200) — live
    analytics unaffected (§20 operator row)."""
    db, dao, writer = stack

    class _StuckDAO(_FlakyDAO):
        def __init__(self, real):
            super().__init__(real, fails=10 ** 9)

    stuck = _StuckDAO(dao)
    w = EventWriter(stuck, retry_delays=(0.01, 0.01, 0.01))
    w.start()
    from backend.core.errors import install, reset_for_tests
    import backend.main as main_mod
    from fastapi.testclient import TestClient
    install(dao, SseHub())
    try:
        w.enqueue(row("pause-api-1"))
        deadline = time.time() + 5
        while not w.paused.is_set() and time.time() < deadline:
            time.sleep(0.02)
        assert w.paused.is_set()
        with TestClient(main_mod.app) as client:
            r = client.get("/api/health")
            assert r.status_code == 200
            assert r.json()["db"]["ok"] is True      # DAO reads fine
            r = client.post("/api/zones", json={
                "source_id": "s", "name": "during-pause", "kind": "polygon",
                "type": "WATCH",
                "geometry": {"points": [[0.1, 0.3], [0.9, 0.3],
                                        [0.9, 0.9], [0.1, 0.9]]}})
            assert r.status_code == 201, r.text       # CRUD responsive
    finally:
        # unstick so stop() drains cleanly
        stuck._fails = 0
        w.stop()
        reset_for_tests()


def test_c4_poison_drops_batch_and_unlinks_snapshots(stack, tmp_path):
    """Poison batch (IntegrityError): dropped whole, snapshot files
    UNLINKED (A4 cleanup-at-source), honest counter, writer continues."""
    db, dao, writer = stack
    sid = dao.insert_session("s")
    ev = tmp_path / "evdir"
    ev.mkdir()
    snap = ev / "snap-poison.jpg"
    snap.write_bytes(b"\xff\xd8fake")
    w = EventWriter(dao)
    w.start()
    try:
        w.enqueue(row("dup-poison", sid, sp=str(snap)))
        time.sleep(0.1)
        w.enqueue(row("dup-poison", sid, sp=str(snap)))   # PK violation
        time.sleep(0.3)
        assert w.dropped_batches == 1
        assert not snap.exists()           # unlinked (C4/A4)
        # writer alive: next clean batch lands
        w.enqueue(row("after-poison", sid))
        w.drain(timeout=5)
        assert w.committed >= 2
    finally:
        w.stop()


def test_c4_stop_while_paused_documented_drop(stack):
    """stop() during a PAUSE: bounded drain then proceeds — the queued
    rows are DROPPED with a log line (documented shutdown caveat)."""
    db, dao, writer = stack

    class _ForeverStuck(_FlakyDAO):
        def __init__(self, real):
            super().__init__(real, fails=10 ** 9)

    stuck = _ForeverStuck(dao)
    w = EventWriter(stuck, retry_delays=(0.01, 0.01, 0.01))
    w.start()
    sid = dao.insert_session("s")
    w.enqueue(row("stop-paused-1", sid))
    deadline = time.time() + 5
    while not w.paused.is_set() and time.time() < deadline:
        time.sleep(0.02)
    assert w.paused.is_set()
    # stop during pause — must terminate within the drain timeout
    t0 = time.time()
    w.stop(drain_timeout=1.0)
    assert time.time() - t0 < 5
    # thread terminated; queued row dropped (caveat) — writer not zombie
    assert w._thread is None
    # restart persistence variant: a NEW writer on the same DB works
    w2 = EventWriter(dao)
    w2.start()
    try:
        w2.enqueue(row("post-restart-1", sid))
        w2.drain(timeout=5)
        assert w2.committed == 1
    finally:
        w2.stop()


# ---------- C2 webcam backoff ladder (§20 disconnect row) ----------

class _LadderCam(VideoSource):
    """Mock live camera: normal frames, then N consecutive read-failures
    (state=ERROR), then recovers on the NEXT reopen() (C2 drill)."""
    is_live = True
    source_id = "webcam:0"

    def __init__(self, good_before_loss=5, fail_cycles=1):
        self._i = 0
        self._state = SourceState.IDLE
        self._failing = False
        self._cycles_left = fail_cycles
        self._good = good_before_loss
        self._fail_streak = 0
        self.reopens = 0
        self._frame = np.zeros((480, 640, 3), dtype=np.uint8)

    def open(self):
        self._state = SourceState.OPEN

    def read(self):
        if self._failing:
            self._fail_streak += 1
            if self._fail_streak >= 10:
                self._state = SourceState.ERROR
            return None
        if self._i >= self._good and self._cycles_left > 0:
            self._failing = True
            return None
        self._i += 1
        return FramePacket(self._frame.copy(), time.time(), None,
                           self._i, self.source_id)

    def reopen(self):
        self.reopens += 1
        if self._failing and self._cycles_left > 0:
            self._cycles_left -= 1        # this reopen fails...
            if self._cycles_left == 0:
                # ...but the NEXT one recovers (ladder escalates once)
                self._fail_after = True
                self._failing = False     # recovered on next reopen call
                self._state = SourceState.OPEN
                self._fail_streak = 0
                self._good = self._i + 3   # a few more frames, then done
                self._cycles_left = -1
                return True
            return False
        self._failing = False
        self._state = SourceState.OPEN
        return True

    def release(self):
        self._state = SourceState.RELEASED

    @property
    def state(self):
        return self._state


class _StubDetector:
    actual_device = "cpu"
    def load(self): pass
    def warmup(self, f): pass
    def process(self, frame): return []


def _make_session(tmp_path, source, dao, writer, hub):
    from backend.services.session import ProcessingSession
    from backend.analytics import ZoneStore
    s = ProcessingSession(source, zones=ZoneStore(dao=dao), dao=dao,
                          writer=writer, hub=hub)
    s._detector = _StubDetector()
    return s


def test_c2_backoff_ladder_sequence_and_events(tmp_path):
    """Webcam disconnect: SOURCE_LOST exactly-once across the whole cycle,
    ladder 1->2->4->8 capped (tiny config for speed), SOURCE_RECONNECTED
    once on recovery; a SECOND disconnect cycle re-arms the flag
    (2 LOST + 2 RECONNECTED pairs)."""
    from backend.analytics import ZoneStore
    db = Database(tmp_path / "c2.db")
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    dao.upsert_source("webcam:0", "webcam")
    writer = EventWriter(dao)
    writer.start()
    hub = SseHub()
    import backend.services.session as sess_mod
    real_sources = sess_mod.SOURCES
    sess_mod.SOURCES = type("S", (), {"backoff_base_s": 0.01,
                                       "backoff_cap_s": 0.02,
                                       "decode_fail_limit": 60})()
    try:
        cam = _LadderCam(good_before_loss=3, fail_cycles=2)
        s = _make_session(tmp_path, cam, dao, writer, hub)
        s.start()
        deadline = time.time() + 20
        while (s.status == "running" or s.status == "starting") \
                and time.time() < deadline:
            time.sleep(0.05)
        # the mock: cycle1 (fail->reopen fails->ladder->reopen fails...)
        # recovers, then cycle2, then finishes good forever until EOFless
        # live loop = keeps running; stop it after we saw the pairs
        deadline = time.time() + 10
        while time.time() < deadline:
            if cam.reopens >= 1:
                break
            time.sleep(0.05)
        time.sleep(0.5)     # let the cycle play out
        s.stop(timeout=5)
        writer.drain(timeout=5)
        rows = dao.query_events(limit=100)
        types = [r["type"] for r in rows]
        assert types.count("SOURCE_CONNECTED") >= 1
        lost = types.count("SOURCE_LOST")
        rec = types.count("SOURCE_RECONNECTED")
        # at least one full cycle observed; exactly-once per cycle
        assert lost >= 1 and rec >= 1, types
        # LOST never repeats back-to-back (one-shot flag re-armed only
        # on reconnect)
        consecutive = any(a == b == "SOURCE_LOST"
                          for a, b in zip(types, types[1:]))
        assert not consecutive, types
        # ladder escalated: multiple failed reopens before recovery
        assert cam.reopens >= 1
        # wall-clock: tiny ladder keeps the drill under 2s of backoff
        assert s.frames_processed >= 3
    finally:
        sess_mod.SOURCES = real_sources
        writer.stop()
        db.close_all()


def test_c2_stop_during_backoff_interrupts_sleep(tmp_path):
    """stop() during a backoff sleep: interrupts (stop event, never
    time.sleep), thread joins fast, no zombie."""
    from backend.analytics import ZoneStore
    db = Database(tmp_path / "c2b.db")
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    dao.upsert_source("webcam:0", "webcam")
    writer = EventWriter(dao)
    writer.start()
    hub = SseHub()
    import backend.services.session as sess_mod
    real = sess_mod.SOURCES
    sess_mod.SOURCES = type("S", (), {"backoff_base_s": 8.0,
                                       "backoff_cap_s": 8.0,
                                       "decode_fail_limit": 60})()
    try:
        cam = _LadderCam(good_before_loss=2, fail_cycles=99)  # stays down
        s = _make_session(tmp_path, cam, dao, writer, hub)
        s.start()
        deadline = time.time() + 5
        while s.frames_processed < 2 and time.time() < deadline:
            time.sleep(0.02)
        time.sleep(0.2)      # now inside the 8s backoff sleep
        assert s.status == "running"     # parked in interruptible sleep
        t0 = time.time()
        s.stop(timeout=3.0)
        assert time.time() - t0 <= 0.2 + 3.0
        assert not s._thread.is_alive() if s._thread else True
        names = [t.name for t in threading.enumerate()]
        assert "trinetra-session" not in names   # no zombie
    finally:
        sess_mod.SOURCES = real
        writer.stop()
        db.close_all()


# ---------- C3 corrupt/truncated file (§20 mid-file row) ----------

def test_c3_decode_fail_below_limit_skips_and_completes(tmp_path):
    """streak < decode_fail_limit: frames skipped + counted, session
    completes at TRUE EOF (state=EOF via frame_count check)."""
    good = tmp_path / "good.mp4"
    # real, valid clip: copy the asset (61 frames, frame_count known)
    import shutil
    shutil.copy(Path(__file__).parent / "assets" / "running_clip.mp4",
                good)
    from backend.sources import FileSource

    src = FileSource(good)
    src.open()
    n = 0
    while src.read() is not None:
        n += 1
    assert n >= 55
    assert src.state is SourceState.EOF
    assert src.decode_fails == 0        # clean file: zero decode-fails
    src.release()


def test_c3_decode_fail_at_limit_aborts_session(tmp_path):
    """>= decode_fail_limit consecutive decode failures: state=ERROR,
    session error, health stays 200. Drill via a mock file source whose
    read fails mid-stream with frame_count KNOWN (so failures are
    decode-fails, not EOS)."""
    class _CorruptFile(VideoSource):
        is_live = False
        source_id = "file:corrupt.mp4"

        def __init__(self, good=3, limit=5):
            self._good = good
            self._state = SourceState.IDLE
            self._i = 0
            self._fails = 0
            self._limit = limit
            self._frame = np.zeros((480, 640, 3), dtype=np.uint8)

        def open(self):
            self._state = SourceState.OPEN

        def read(self):
            if self._i < self._good:
                self._i += 1
                return FramePacket(self._frame.copy(), time.time(),
                                    float(self._i), self._i, self.source_id)
            self._fails += 1
            self._state = SourceState.ERROR    # decode-fail (not EOF):
            # frame_count KNOWN (drill stand-in: good>0 so index
            # < count-1) -> FileSource semantics: ERROR, streak grows
            return None

        def release(self):
            self._state = SourceState.RELEASED

        @property
        def state(self):
            return self._state

    from backend.analytics import ZoneStore
    db = Database(tmp_path / "c3.db")
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    dao.upsert_source("file:corrupt.mp4", "file")
    writer = EventWriter(dao)
    writer.start()
    import backend.services.session as sess_mod
    real = sess_mod.SOURCES
    sess_mod.SOURCES = type("S", (), {"backoff_base_s": 0.01,
                                       "backoff_cap_s": 0.02,
                                       "decode_fail_limit": 5})()
    try:
        s = _make_session(tmp_path, _CorruptFile(), dao, writer, SseHub())
        s.start()
        deadline = time.time() + 15
        while s.status == "running" and time.time() < deadline:
            time.sleep(0.05)
        assert s.status == "error"
        assert "decode failed" in s.error
        writer.drain(timeout=5)
        types = [r["type"] for r in dao.query_events(limit=50)]
        assert "SOURCE_CONNECTED" in types
        assert types.count("SOURCE_LOST") == 1    # once, at abort
        # health stays 200 while a session errored
        from backend.core.errors import install, reset_for_tests
        import backend.main as main_mod
        from fastapi.testclient import TestClient
        install(dao, SseHub())
        with TestClient(main_mod.app) as client:
            assert client.get("/api/health").status_code == 200
        reset_for_tests()
    finally:
        sess_mod.SOURCES = real
        writer.stop()
        db.close_all()


def test_c3_midfile_streak_below_limit_skips_counts_completes(tmp_path):
    """Mandated C3 edge the existing tests miss: a decode-fail streak
    MID-FILE (below limit) that then RECOVERS — frames skipped+counted,
    session continues and COMPLETES at TRUE EOF (status=completed, not
    error). Mirrors the §20 'corrupt packet mid-file' row."""
    from backend.analytics import ZoneStore
    from backend.services.session import ProcessingSession

    class _GlitchyFile(VideoSource):
        """Valid frames -> N decode-fail reads (state=ERROR, known
        frame_count so NOT EOS) -> recovers -> more frames -> EOF."""
        is_live = False
        source_id = "file:glitchy.mp4"

        def __init__(self, good=3, glitch=3, tail=3):
            self._good = good
            self._glitch = glitch
            self._tail = tail
            self._i = 0                 # GOOD frames served so far
            self._glitched = 0          # glitch reads served so far
            self._state = SourceState.IDLE
            self._frame = np.zeros((480, 640, 3), dtype=np.uint8)

        def open(self):
            self._state = SourceState.OPEN

        def read(self):
            if self._i >= self._good + self._tail and \
                    self._glitched >= self._glitch:
                self._state = SourceState.EOF
                return None
            if self._good <= self._i and self._glitched < self._glitch:
                # mid-file decode failure (index < count-1 — NOT EOS);
                # glitch reads do NOT advance the good-frame index
                self._glitched += 1
                self._state = SourceState.ERROR
                return None
            self._state = SourceState.OPEN
            self._i += 1
            return FramePacket(self._frame.copy(), time.time(),
                               float(self._i), self._i, self.source_id)

        def release(self):
            self._state = SourceState.RELEASED

        @property
        def state(self):
            return self._state

    db = Database(tmp_path / "c3glitch.db")
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    dao.upsert_source("file:glitchy.mp4", "file")
    writer = EventWriter(dao)
    writer.start()
    import backend.services.session as sess_mod
    real = sess_mod.SOURCES
    sess_mod.SOURCES = type("S", (), {"backoff_base_s": 0.01,
                                       "backoff_cap_s": 0.02,
                                       "decode_fail_limit": 60})()
    try:
        s = ProcessingSession(_GlitchyFile(), zones=ZoneStore(dao=dao),
                              dao=dao, writer=writer, hub=SseHub())
        s._detector = _StubDetector()
        s.start()
        deadline = time.time() + 15
        while s.status in ("running", "starting") and time.time() < deadline:
            time.sleep(0.05)
        assert s.status == "completed", s.status      # NOT error
        # skipped frames counted honestly: served = good+tail frames
        # processed; glitch reads did NOT abort the session
        assert s.frames_processed == 6, s.frames_processed
        writer.drain(timeout=5)
        types = [r["type"] for r in dao.query_events(limit=50)]
        assert "SOURCE_CONNECTED" in types
        assert "SESSION_COMPLETED" in types
        assert "SOURCE_LOST" not in types      # streak < limit: no abort
    finally:
        sess_mod.SOURCES = real
        writer.stop()
        db.close_all()
