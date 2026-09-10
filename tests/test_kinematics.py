"""TRINETRA V3.5 — Kinematic & Trajectory Analytics Tests.

Validates clean-room kinematic heuristics:
- SUSPECTED_RUNNING: velocity + net displacement sustained >= 3 ticks.
- SUSPECTED_ABNORMAL_MOVEMENT: thrashing / low straightness at high speed.
- LOITERING: track dwell >= 15s within bounding radius < 80px.
- NIGHT_MOVEMENT: active in night context >= 5 consecutive ticks.
- Reset & state purge on lost tracks.
"""

from __future__ import annotations

from collections import deque
import numpy as np
import pytest

from backend.analytics.base import FrameContext
from backend.analytics.kinematics import KinematicTrajectoryAnalytic


class _MockTrack:
    def __init__(
        self,
        track_id: int,
        positions: list[tuple[float, float, int]],
        class_name: str = "person",
        first_tick: int = 0,
        last_tick: int = 0,
        first_seen: float = 0.0,
        last_seen: float = 0.0,
    ) -> None:
        self.track_id = track_id
        self.positions = deque(positions)
        self.class_name = class_name
        self.first_tick = first_tick
        self.last_tick = last_tick
        self.first_seen = first_seen
        self.last_seen = last_seen


class _MockTrackView:
    def __init__(self, active_tracks: list[_MockTrack]) -> None:
        self.active_tracks = active_tracks


def _ctx(tick: int = 0, wall_ts: float = 0.0, is_night: bool = False, luminance: float = 128.0) -> FrameContext:
    return FrameContext(
        tick=tick,
        wall_ts=wall_ts,
        video_ts=wall_ts,
        luminance=luminance,
        is_night=is_night,
        shape=(640, 480),
    )


def test_suspected_running_triggers_after_sustained_ticks():
    analyzer = KinematicTrajectoryAnalytic(fps=25.0)
    analyzer.reset("session-1")

    # Fast runner moving 15px per tick = 375 px/s
    positions = []
    drafts = []
    for tick in range(15):
        positions.append((100.0 + tick * 15.0, 200.0, tick))
        track = _MockTrack(
            track_id=1,
            positions=positions[-10:],
            first_tick=0,
            last_tick=tick,
            first_seen=0.0,
            last_seen=tick / 25.0,
        )
        ctx = _ctx(tick=tick, wall_ts=tick / 25.0)
        d = analyzer.process(ctx, _MockTrackView([track]))
        drafts.extend(d)

    running_events = [d for d in drafts if d.type == "SUSPECTED_RUNNING"]
    assert len(running_events) >= 1
    assert running_events[0].track_ids == [1]
    assert running_events[0].confidence >= 0.50
    assert running_events[0].metadata["speed_px_s"] > 80.0


def test_slow_movement_does_not_trigger_running():
    analyzer = KinematicTrajectoryAnalytic(fps=25.0)
    analyzer.reset("session-1")

    # Slow walker moving 1px per tick = 25 px/s
    positions = []
    drafts = []
    for tick in range(15):
        positions.append((100.0 + tick * 1.0, 200.0, tick))
        track = _MockTrack(
            track_id=2,
            positions=positions[-10:],
            first_tick=0,
            last_tick=tick,
            first_seen=0.0,
            last_seen=tick / 25.0,
        )
        ctx = _ctx(tick=tick, wall_ts=tick / 25.0)
        d = analyzer.process(ctx, _MockTrackView([track]))
        drafts.extend(d)

    running_events = [d for d in drafts if d.type == "SUSPECTED_RUNNING"]
    assert len(running_events) == 0


def test_suspected_abnormal_movement_on_thrashing():
    analyzer = KinematicTrajectoryAnalytic(fps=25.0)
    analyzer.reset("session-1")

    # Establish baseline speed
    for i in range(20):
        t = _MockTrack(track_id=99, positions=[(float(i * 2), 0.0, i), (float(i * 2 + 2), 0.0, i + 1)])
        analyzer.process(_ctx(tick=i, wall_ts=i / 25.0), _MockTrackView([t]))

    # Now thrashing high speed movement (back and forth)
    # distance moved is large (high speed), but net displacement is small (dir_ratio < 0.3)
    positions = []
    drafts = []
    for tick in range(15):
        x = 200.0 + (30.0 if tick % 2 == 0 else -30.0)
        y = 200.0 + (30.0 if tick % 3 == 0 else -30.0)
        positions.append((x, y, 20 + tick))
        track = _MockTrack(
            track_id=3,
            positions=positions[-10:],
            first_tick=20,
            last_tick=20 + tick,
            first_seen=0.8,
            last_seen=(20 + tick) / 25.0,
        )
        ctx = _ctx(tick=20 + tick, wall_ts=(20 + tick) / 25.0)
        d = analyzer.process(ctx, _MockTrackView([track]))
        drafts.extend(d)

    abnormal_events = [d for d in drafts if d.type == "SUSPECTED_ABNORMAL_MOVEMENT"]
    assert len(abnormal_events) >= 1
    assert abnormal_events[0].track_ids == [3]
    assert abnormal_events[0].metadata["dir_score"] < 0.30


def test_loitering_triggers_after_dwell_threshold():
    analyzer = KinematicTrajectoryAnalytic(fps=25.0, loiter_dwell_sec=10.0)
    analyzer.reset("session-1")

    # Track stationary within 20px radius for 15 seconds (375 ticks)
    positions = [(100.0 + (i % 5), 100.0 + (i % 5), i) for i in range(375)]
    track = _MockTrack(
        track_id=4,
        positions=positions[-10:],
        first_tick=0,
        last_tick=375,
        first_seen=0.0,
        last_seen=15.0,
    )
    # Overwrite track.positions to hold all points for bounding radius
    track.positions = positions

    ctx = _ctx(tick=375, wall_ts=15.0)
    drafts = analyzer.process(ctx, _MockTrackView([track]))

    loiter_events = [d for d in drafts if d.type == "LOITERING"]
    assert len(loiter_events) == 1
    assert loiter_events[0].track_ids == [4]
    assert loiter_events[0].metadata["dwell_seconds"] >= 10.0
    assert loiter_events[0].metadata["bounding_radius"] < 80.0


def test_night_movement_triggers_in_night_context():
    analyzer = KinematicTrajectoryAnalytic(fps=25.0)
    analyzer.reset("session-1")

    drafts = []
    positions = [(50.0 + i, 50.0, i) for i in range(10)]
    for tick in range(10):
        track = _MockTrack(
            track_id=5,
            positions=positions[:tick + 1],
            first_tick=0,
            last_tick=tick,
        )
        ctx = _ctx(tick=tick, wall_ts=tick / 25.0, is_night=True, luminance=25.0)
        d = analyzer.process(ctx, _MockTrackView([track]))
        drafts.extend(d)

    night_events = [d for d in drafts if d.type == "NIGHT_MOVEMENT"]
    assert len(night_events) >= 1
    assert night_events[0].track_ids == [5]
    assert night_events[0].metadata["is_night"] is True


def test_direct_update_api():
    analyzer = KinematicTrajectoryAnalytic(fps=25.0)
    frame = np.full((480, 640, 3), 20, dtype=np.uint8)  # dark frame

    positions = [(50.0 + i, 50.0, i) for i in range(10)]
    track = _MockTrack(track_id=6, positions=positions, first_tick=0, last_tick=10)

    all_drafts = []
    for i in range(6):
        d = analyzer.update([track], frame=frame, video_ts=float(i))
        all_drafts.extend(d)
    night_events = [d for d in all_drafts if d.type == "NIGHT_MOVEMENT"]
    assert len(night_events) >= 1
