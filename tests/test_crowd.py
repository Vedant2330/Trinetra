"""TRINETRA V3.5 — Count-Based Crowd Density Analytics Tests.

Validates:
- CROWD_DENSITY_MEDIUM: >= 4 persons in zone sustained >= 2 consecutive frames.
- CROWD_DENSITY_HIGH: >= 8 persons in zone sustained >= 2 consecutive frames.
- Cooldown period enforcement (10.0s).
- Direct update API and scene fallback.
- Reset lifecycle and state clearing.
"""

from __future__ import annotations

import pytest

from backend.analytics.base import FrameContext
from backend.analytics.crowd import CrowdDensityAnalytic
from backend.analytics.zones import ZoneStore
from backend.events.engine import EventEngine


class _MockFenceAnalytic:
    def __init__(self, counts: dict[str, int]) -> None:
        self._counts = dict(counts)

    def zone_person_counts(self) -> dict[str, int]:
        return dict(self._counts)

    def set_counts(self, counts: dict[str, int]) -> None:
        self._counts = dict(counts)


class _MockTrack:
    def __init__(self, track_id: int, class_name: str = "person") -> None:
        self.track_id = track_id
        self.class_name = class_name


class _MockTrackView:
    def __init__(self, active_tracks: list[_MockTrack]) -> None:
        self.active_tracks = active_tracks


def _ctx(tick: int = 0, wall_ts: float = 0.0) -> FrameContext:
    return FrameContext(
        tick=tick,
        wall_ts=wall_ts,
        video_ts=wall_ts,
        luminance=128.0,
        is_night=False,
        shape=(640, 480),
    )


def test_medium_crowd_density_requires_sustain():
    fence = _MockFenceAnalytic({"zone_a": 4})
    crowd = CrowdDensityAnalytic(fence_analytic=fence, medium_thresh=4, high_thresh=8, sustain_frames=2)
    crowd.reset("session-1")

    # Frame 1: count=4 -> consecutive=1 (sustain_frames=2, so 0 drafts)
    drafts1 = crowd.process(_ctx(tick=1, wall_ts=1.0), _MockTrackView([]))
    assert len(drafts1) == 0

    # Frame 2: count=4 -> consecutive=2 -> fires CROWD_DENSITY_MEDIUM
    drafts2 = crowd.process(_ctx(tick=2, wall_ts=1.5), _MockTrackView([]))
    assert len(drafts2) == 1
    assert drafts2[0].type == "CROWD_DENSITY_MEDIUM"
    assert drafts2[0].zone_id == "zone_a"
    assert drafts2[0].metadata["person_count"] == 4
    assert drafts2[0].metadata["density_level"] == "MEDIUM"


def test_high_crowd_density_triggers():
    fence = _MockFenceAnalytic({"zone_b": 9})
    crowd = CrowdDensityAnalytic(fence_analytic=fence, medium_thresh=4, high_thresh=8, sustain_frames=2)
    crowd.reset("session-1")

    # Frame 1: count=9
    drafts1 = crowd.process(_ctx(tick=1, wall_ts=1.0), _MockTrackView([]))
    assert len(drafts1) == 0

    # Frame 2: count=9 -> fires CROWD_DENSITY_HIGH
    drafts2 = crowd.process(_ctx(tick=2, wall_ts=1.5), _MockTrackView([]))
    assert len(drafts2) == 1
    assert drafts2[0].type == "CROWD_DENSITY_HIGH"
    assert drafts2[0].zone_id == "zone_b"
    assert drafts2[0].metadata["person_count"] == 9
    assert drafts2[0].metadata["density_level"] == "HIGH"


def test_crowd_density_cooldown():
    fence = _MockFenceAnalytic({"zone_a": 5})
    crowd = CrowdDensityAnalytic(fence_analytic=fence, medium_thresh=4, high_thresh=8, sustain_frames=2)
    crowd.reset("session-1")

    # Frame 1 & 2 -> fire at t=1.5
    crowd.process(_ctx(tick=1, wall_ts=1.0), _MockTrackView([]))
    drafts2 = crowd.process(_ctx(tick=2, wall_ts=1.5), _MockTrackView([]))
    assert len(drafts2) == 1

    # Frame 3 at t=3.0 (within 10s cooldown) -> 0 drafts
    drafts3 = crowd.process(_ctx(tick=3, wall_ts=3.0), _MockTrackView([]))
    assert len(drafts3) == 0

    # Frame 4 at t=12.0 (> 10s cooldown) -> fires again
    drafts4 = crowd.process(_ctx(tick=4, wall_ts=12.0), _MockTrackView([]))
    assert len(drafts4) == 1
    assert drafts4[0].type == "CROWD_DENSITY_MEDIUM"


def test_crowd_count_drop_resets_counter():
    fence = _MockFenceAnalytic({"zone_a": 5})
    crowd = CrowdDensityAnalytic(fence_analytic=fence, medium_thresh=4, high_thresh=8, sustain_frames=2)
    crowd.reset("session-1")

    # Frame 1: count=5 (consecutive=1)
    crowd.process(_ctx(tick=1, wall_ts=1.0), _MockTrackView([]))

    # Frame 2: count drops to 2 (consecutive resets to 0)
    fence.set_counts({"zone_a": 2})
    drafts2 = crowd.process(_ctx(tick=2, wall_ts=1.5), _MockTrackView([]))
    assert len(drafts2) == 0

    # Frame 3: count rises back to 5 (consecutive=1, not 2) -> 0 drafts
    fence.set_counts({"zone_a": 5})
    drafts3 = crowd.process(_ctx(tick=3, wall_ts=2.0), _MockTrackView([]))
    assert len(drafts3) == 0


def test_scene_fallback_when_no_zones():
    crowd = CrowdDensityAnalytic(fence_analytic=None, medium_thresh=4, high_thresh=8, sustain_frames=2)
    crowd.reset("session-1")

    tracks = [_MockTrack(i, "person") for i in range(5)]
    crowd.process(_ctx(tick=1, wall_ts=1.0), _MockTrackView(tracks))
    drafts2 = crowd.process(_ctx(tick=2, wall_ts=1.5), _MockTrackView(tracks))

    assert len(drafts2) == 1
    assert drafts2[0].type == "CROWD_DENSITY_MEDIUM"
    assert drafts2[0].zone_id is None
    assert drafts2[0].metadata["zone_id"] == "__scene__"


def test_direct_update_api():
    crowd = CrowdDensityAnalytic(medium_thresh=4, high_thresh=8, sustain_frames=2)
    crowd.update({"zone_x": 4}, video_ts=1.0)
    drafts = crowd.update({"zone_x": 4}, video_ts=1.5)
    assert len(drafts) == 1
    assert drafts[0].type == "CROWD_DENSITY_MEDIUM"


# ---------------------------------------------------------------------------
# Composition: RESTRICTED zone escalation (oscar major 1)
# ---------------------------------------------------------------------------

class _RealZoneFence:
    """Fence-like object holding a REAL ZoneStore (the same shape
    FenceAnalytic holds) so crowd resolves zone_type honestly."""

    def __init__(self, store: ZoneStore, counts: dict[str, int]) -> None:
        self._zones = store
        self._counts = dict(counts)

    def zone_person_counts(self) -> dict[str, int]:
        return dict(self._counts)


def test_crowd_restricted_zone_escalation_composition():
    """COMPOSITION (must-fail on pre-fix wiring): CROWD_DENSITY_MEDIUM
    in a RESTRICTED zone must (a) carry zone_type='RESTRICTED' in draft
    metadata and (b) commit as HIGH through the REAL EventEngine
    severity path (engine _NEW_TYPE_BASE + RESTRICTED +1). Pre-fix:
    producer omitted zone_type -> escalation never fired, crowd in a
    RESTRICTED zone stayed MEDIUM."""
    zstore = ZoneStore()
    z_res = zstore.add("src-1", "Vault", "polygon", "RESTRICTED",
                       {"points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]})
    z_watch = zstore.add("src-1", "Lobby", "polygon", "WATCH",
                          {"points": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]})

    crowd = CrowdDensityAnalytic(
        fence_analytic=_RealZoneFence(zstore, {z_res.id: 5, z_watch.id: 5}),
        medium_thresh=4, high_thresh=8, sustain_frames=2,
    )
    crowd.reset("session-esc-1")

    # Sustain two ticks -> MEDIUM drafts for both zones
    crowd.process(_ctx(tick=1, wall_ts=1.0), _MockTrackView([]))
    drafts = crowd.process(_ctx(tick=2, wall_ts=1.5), _MockTrackView([]))
    assert len(drafts) == 2

    by_zone = {d.metadata["zone_id"]: d for d in drafts}
    assert by_zone[z_res.id].metadata["zone_type"] == "RESTRICTED"
    assert by_zone[z_watch.id].metadata["zone_type"] == "WATCH"

    # Commit through the REAL engine — RESTRICTED MEDIUM escalates to HIGH
    eng = EventEngine("src-1", "session-esc-1")
    committed = eng.commit(list(drafts), None, _ctx(tick=2, wall_ts=1.5))
    sev_by_zone = {ev.zone_id: ev.severity for ev in committed}
    assert sev_by_zone[z_res.id] == "HIGH"
    assert sev_by_zone[z_watch.id] == "MEDIUM"
