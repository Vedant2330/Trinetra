"""TRINETRA TrackStore — minimal in-memory state for tracked objects (M2).

Design (frozen Phase 1 §7):
  - One store per session. Keyed by authoritative ByteTrack track_id.
  - ID authority rule: update() only accepts TrackedObject inputs; a
    detection with track_id=None is ignored for STATE purposes (nothing to
    key on) — it remains a valid detection, just not state-tracked yet.
  - Retention: bounded position history (config tracking.history_len).
    Tracks are never evicted in M2 (single-session MVP scale); a track
    unseen for > tracking.lost_timeout_frames is flagged active=False.
    M4 will build lost-track grace on top of these fields.
  - No velocity computation here yet (M3/M4 consumer need measured
    evidence first). Fields exist to answer: where was it / where is it /
    when was it last seen.
"""

from __future__ import annotations

from collections import deque
from typing import Iterable, Optional

from backend.core.config import TRACKING
from backend.vision import TrackedObject


class TrackState:
    """Application state for one authoritative track ID."""

    __slots__ = ("track_id", "class_id", "class_name", "first_tick", "first_seen",
                 "last_tick", "last_seen", "last_bbox", "frames_seen",
                 "positions", "active")

    def __init__(self, track_id: int, class_id: int, class_name: str,
                 tick: int, wall_ts: float, bbox: list[float]) -> None:
        self.track_id = track_id
        self.class_id = class_id
        self.class_name = class_name
        self.first_tick = tick
        self.first_seen = wall_ts
        self.last_tick = tick
        self.last_seen = wall_ts
        self.last_bbox = list(bbox)
        self.frames_seen = 1
        self.positions: deque[tuple[float, float, int]] = deque(
            maxlen=TRACKING.history_len)
        self._push_position(bbox, tick)
        self.active = True

    def _push_position(self, bbox: list[float], tick: int) -> None:
        x = (bbox[0] + bbox[2]) / 2.0
        y = (bbox[1] + bbox[3]) / 2.0
        self.positions.append((x, y, tick))

    def update(self, tick: int, wall_ts: float, bbox: list[float],
               class_name: str, class_id: int) -> None:
        self.last_tick = tick
        self.last_seen = wall_ts
        self.last_bbox = list(bbox)
        self.class_name = class_name      # keep latest label (stable in practice)
        self.class_id = class_id
        self.frames_seen += 1
        self._push_position(bbox, tick)
        self.active = True

    @property
    def position(self) -> tuple[float, float]:
        """Most recent (x, y) center in frame pixels."""
        if self.positions:
            return self.positions[-1][0], self.positions[-1][1]
        return (0.0, 0.0)

    def __repr__(self) -> str:
        return (f"TrackState(id={self.track_id} {self.class_name} "
                f"frames={self.frames_seen} active={self.active} "
                f"last_tick={self.last_tick})")


class TrackStore:
    """Per-session store. Never generates IDs (hard rule)."""

    def __init__(self) -> None:
        self._tracks: dict[int, TrackState] = {}
        self._tick = 0

    # ---- queries ----

    def get(self, track_id: int) -> Optional[TrackState]:
        return self._tracks.get(track_id)

    @property
    def tracks(self) -> dict[int, TrackState]:
        return self._tracks

    @property
    def active_tracks(self) -> list[TrackState]:
        return [t for t in self._tracks.values() if t.active]

    def count_active(self, class_name: Optional[str] = None) -> int:
        """Real count query (future: zone occupancy consumers)."""
        if class_name is None:
            return len(self.active_tracks)
        return sum(1 for t in self.active_tracks if t.class_name == class_name)

    # ---- update ----

    def update(self, tracked: Iterable[TrackedObject], tick: int,
               wall_ts: float) -> int:
        """Merge this frame's tracked objects into state.

        Returns the number of state-tracked updates (detections without a
        track_id do not update state — they have no authoritative identity).
        active flags are refreshed; tracks missing this tick stay active
        until lost_timeout_frames elapses (then active=False, retained).
        """
        self._tick = tick
        seen_ids: set[int] = set()
        updates = 0
        for obj in tracked:
            if obj.track_id is None:
                continue                    # honest: no identity, no state
            if obj.track_id in seen_ids:
                continue                    # duplicate ID in one frame: first wins
            seen_ids.add(obj.track_id)
            state = self._tracks.get(obj.track_id)
            if state is None:
                self._tracks[obj.track_id] = TrackState(
                    obj.track_id, obj.class_id, obj.class_name,
                    tick, wall_ts, obj.bbox)
            else:
                state.update(tick, wall_ts, obj.bbox, obj.class_name, obj.class_id)
            updates += 1
        # lost detection
        for state in self._tracks.values():
            if state.track_id not in seen_ids:
                if tick - state.last_tick > TRACKING.lost_timeout_frames:
                    state.active = False
        return updates
