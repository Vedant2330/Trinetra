"""M8 sampling policy — selective Re-ID (mandate §5).

Re-ID runs ONLY:
  - every `interval_ticks` ticks a track is seen (default 25), AND
  - the track must be structurally stable (`min_frames_seen`, default
    5 — matches the tracker's own confirmation idea), AND
  - never more often than `min_gap_s` wall seconds (default 10).

Override triggers (checked FIRST, before the periodic rule):
  - force=True  — camera change, manual, or investigation trigger
  - stable_now  — track just crossed min_confirm_frames this call

The policy is a pure per-track state machine: should_sample(track)
updates and answers. It does NOT know about frames or crops — the
session/adapter decides what a "sample" is. Counters are exposed for
the mandated test: selective sampling must REDUCE inference calls vs
every-frame embedding.

ByteTrack stays authoritative for local tracking; this only paces
appearance sampling.
"""

from __future__ import annotations

import time
from typing import Optional

from backend.core.config import TRACKING, REID


class SamplePolicy:
    """Immutable knobs (config [reid] sampling section)."""

    __slots__ = ("interval_ticks", "min_frames_seen", "min_gap_s")

    def __init__(self, interval_ticks: Optional[int] = None,
                 min_frames_seen: Optional[int] = None,
                 min_gap_s: Optional[float] = None) -> None:
        self.interval_ticks = (interval_ticks if interval_ticks is not None
                               else REID.sample_interval_ticks)
        self.min_frames_seen = (min_frames_seen if min_frames_seen is not None
                                else REID.sample_min_frames_seen)
        self.min_gap_s = min_gap_s if min_gap_s is not None else REID.sample_min_gap_s

    @classmethod
    def every_frame(cls) -> "SamplePolicy":
        """The anti-policy: embed every tick (used by tests to prove
        the real policy reduces inference calls)."""
        return cls(interval_ticks=1, min_frames_seen=1, min_gap_s=0.0)


class ReIDSamplingPolicy:
    """Per-camera pacing state for selective Re-ID."""

    def __init__(self, policy: Optional[SamplePolicy] = None) -> None:
        self.policy = policy or SamplePolicy()
        self._last_tick: dict[int, int] = {}        # track -> last sampled tick
        self._last_ts: dict[int, float] = {}        # track -> last sampled wall ts
        self._confirmed_yet: set[int] = set()       # tracks already stable-sampled
        self.embed_calls = 0                        # observed embed invocations

    def note_embed(self) -> None:
        self.embed_calls += 1

    def should_sample(self, track_id: int, tick: int, wall_ts: float,
                      frames_seen: int, *, force: bool = False,
                      camera_changed: bool = False) -> bool:
        """Decide + record. Pure bookkeeping, no clock reads
        (wall_ts is passed in — deterministic and testable)."""
        p = self.policy
        # 1. structural stability bar (unless forced)
        if frames_seen < p.min_frames_seen and not (force or camera_changed):
            return False
        # 2. override triggers
        if camera_changed:
            self._record(track_id, tick, wall_ts)
            return True
        if force:
            self._record(track_id, tick, wall_ts)
            return True
        just_stable = (frames_seen >= TRACKING.min_confirm_frames
                       and track_id not in self._confirmed_yet)
        if just_stable:
            self._confirmed_yet.add(track_id)
            self._record(track_id, tick, wall_ts)
            return True
        # 3. periodic rule
        last_t = self._last_tick.get(track_id)
        if last_t is not None and (tick - last_t) < p.interval_ticks:
            return False
        last_ts = self._last_ts.get(track_id)
        if last_ts is not None and (wall_ts - last_ts) < p.min_gap_s:
            return False
        self._record(track_id, tick, wall_ts)
        return True

    def _record(self, track_id: int, tick: int, wall_ts: float) -> None:
        self._last_tick[track_id] = tick
        self._last_ts[track_id] = wall_ts

    def forget(self, track_id: int) -> None:
        """Track ended — drop pacing state (bounded memory)."""
        self._last_tick.pop(track_id, None)
        self._last_ts.pop(track_id, None)
        self._confirmed_yet.discard(track_id)

    @property
    def now(self) -> float:
        """Test convenience only (never used in decisions)."""
        return time.time()
