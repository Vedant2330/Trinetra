"""TRINETRA TrackStore — minimal in-memory state for tracked objects (M2, M4).

Design (frozen Phase 1 §7):
  - One store per session. Keyed by authoritative ByteTrack track_id.
  - ID authority rule: update() only accepts TrackedObject inputs; a
    detection with track_id=None is ignored for STATE purposes (nothing to
    key on) — it remains a valid detection, just not state-tracked yet.
  - Retention: bounded position history (config tracking.history_len).
    Tracks are never evicted in M2 (single-session MVP scale); a track
    unseen for > tracking.lost_timeout_frames is flagged active=False.
    M4 lost-track grace lives in FenceAnalytic (its private state), not
    here — the substrate stays minimal.
  - Positions are FOOT POINTS (cx, y2) per §7 FROZEN (M4, architect
    correction 2): bottom-center is the ground-contact point fence
    geometry consumes; bbox-center was rejected for intrusion semantics.
    The x coordinate equals the bbox center-x; only y differs (y2).

M4 additions (architect corrections 1):
  - TrackStore.view() -> a read-only TrackView facade handed to analytics
    (§11 boundary: modules read tracks; they never mutate the store).
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
        # FOOT point (cx, y2) — §7 FROZEN (M4): ground-contact point for
        # fence/tripwire geometry. cx == bbox center-x; y2 == bbox bottom.
        x = (bbox[0] + bbox[2]) / 2.0
        y = float(bbox[3])
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
        """Most recent stored point (cx, y2) in frame pixels (foot point)."""
        if self.positions:
            return self.positions[-1][0], self.positions[-1][1]
        return (0.0, 0.0)

    @property
    def foot_point(self) -> tuple[float, float]:
        """Latest FOOT point (cx, y2) — the fence-geometry input (§7).
        Same as .position (positions store foot points since M4)."""
        return self.position

    @property
    def center(self) -> tuple[float, float]:
        """Bbox CENTER ((cx, cy)) of the last bbox — re-derived on demand
        for any consumer that needs center semantics (M2 compat)."""
        x1, y1, x2, y2 = self.last_bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def __repr__(self) -> str:
        return (f"TrackState(id={self.track_id} {self.class_name} "
                f"frames={self.frames_seen} active={self.active} "
                f"last_tick={self.last_tick})")


class TrackView:
    """Read-only facade over one TrackStore snapshot (M4, §11 boundary).

    Analytics modules receive this — never the store itself — so module
    code cannot mutate track state by construction. ~20 lines, frozen.
    """

    __slots__ = ("_store", "_tick")

    def __init__(self, store: "TrackStore") -> None:
        self._store = store
        self._tick = store.tick

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def active_tracks(self) -> list[TrackState]:
        """Tracks PRESENT in the current tick (fresh detection this frame).

        The store keeps missing tracks `active=True` for a lost-grace
        window (ByteTrack may re-match them) — but their positions are
        STALE. Fence logic must not consume stale points, so the view
        exposes only tracks actually seen at the current tick.
        (absence handling = god corr. 5: outside for grace-advance.)
        """
        return [t for t in self._store.active_tracks
                if t.last_tick == self._tick]

    def get(self, track_id: int) -> Optional[TrackState]:
        return self._store.get(track_id)

    def __len__(self) -> int:
        return len(self.active_tracks)


class TrackStore:
    """Per-session store. Never generates IDs (hard rule)."""

    def __init__(self) -> None:
        self._tracks: dict[int, TrackState] = {}
        self._tick = 0

    # ---- read-only view for analytics (M4) ----

    def view(self) -> TrackView:
        """The read-only snapshot handed to AnalyticModule.process()."""
        return TrackView(self)

    @property
    def tick(self) -> int:
        return self._tick

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
