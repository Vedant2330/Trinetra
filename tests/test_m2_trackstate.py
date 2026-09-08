"""M2 TrackStore tests — state logic only (synthetic TrackedObjects OK here)."""

from __future__ import annotations

from backend.state import TrackState, TrackStore
from backend.vision import TrackedObject


def mk(tid, cls="person", bbox=(10, 10, 50, 90), cid=0):
    return TrackedObject(
        track_id=tid, class_id=cid, class_name=cls,
        confidence=0.9, bbox=list(bbox),
    )


def test_store_updates_and_queries():
    s = TrackStore()
    n = s.update([mk(1), mk(2, "car", cid=2)], tick=0, wall_ts=100.0)
    assert n == 2
    t1 = s.get(1)
    assert t1.class_name == "person"
    assert t1.first_seen == 100.0 and t1.last_seen == 100.0
    assert t1.frames_seen == 1
    assert t1.active is True


def test_position_history_and_retention_bound():
    s = TrackStore()
    for i in range(100):  # exceeds history_len=60
        s.update([mk(1, bbox=(i, 0, i + 40, 80))], tick=i, wall_ts=float(i))
    t = s.get(1)
    assert t.frames_seen == 100
    assert len(t.positions) == 60               # bounded retention
    assert t.positions[-1][0] == (99 + 139) / 2  # latest center x
    assert t.position[0] == t.positions[-1][0]


def test_none_id_never_creates_state():
    s = TrackStore()
    n = s.update([mk(None), mk(3)], tick=0, wall_ts=1.0)
    assert n == 1                                  # only the identified object
    assert s.get(None) is None                     # no fabricated identity
    assert s.get(3) is not None
    assert 3 in s.tracks


def test_store_never_generates_ids():
    s = TrackStore()
    s.update([], tick=0, wall_ts=0.0)              # nothing in, nothing out
    assert s.tracks == {}
    s.update([mk(7)], tick=1, wall_ts=1.0)
    assert set(s.tracks.keys()) == {7}             # exactly what detector gave


def test_lost_track_marked_inactive_after_timeout():
    s = TrackStore()
    s.update([mk(1)], tick=0, wall_ts=0.0)
    for tick in range(1, 31):                       # 30 > lost_timeout_frames=30? boundary:
        s.update([], tick=tick, wall_ts=float(tick))
    # at tick 30: last_tick=0, tick-last_tick=30 which is NOT > 30 -> still active
    assert s.get(1).active is True
    s.update([], tick=31, wall_ts=31.0)             # now 31 > 30
    assert s.get(1).active is False
    assert s.get(1) is not None                    # retained, not evicted


def test_reappearing_track_reactivates_and_keeps_history():
    s = TrackStore()
    s.update([mk(5)], tick=0, wall_ts=0.0)
    s.update([], tick=35, wall_ts=35.0)            # goes inactive
    assert s.get(5).active is False
    s.update([mk(5, bbox=(100, 0, 140, 80))], tick=36, wall_ts=36.0)
    t = s.get(5)
    assert t.active is True
    assert t.frames_seen == 2
    assert t.last_tick == 36
    assert len(t.positions) == 2                   # history continues


def test_active_count_by_class():
    s = TrackStore()
    s.update([mk(1), mk(2, "car", cid=2), mk(3, "car", cid=2)], tick=0, wall_ts=0.0)
    assert s.count_active() == 3
    assert s.count_active("person") == 1
    assert s.count_active("car") == 2
    assert s.count_active("bus") == 0


def test_duplicate_id_in_single_frame_counted_once():
    s = TrackStore()
    n = s.update([mk(1), mk(1, bbox=(1, 1, 2, 2))], tick=0, wall_ts=0.0)
    assert n == 1
    assert s.get(1).frames_seen == 1
