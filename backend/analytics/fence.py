"""TRINETRA FenceAnalytic — virtual fence zones + tripwires (M4, §12).

The MVP analytics module. Rule-based state transitions, confidence=1.0
(frozen). Dedup is STRUCTURAL: no draft while occupancy state is unchanged.

Zones (polygons): occupancy per (track, zone) = {inside, confirm_counter,
grace_counter}. ZONE_ENTRY fires after FENCE.confirm_frames=3 CONSECUTIVE
inside ticks (one outside tick resets the counter); ZONE_EXIT fires after
exit_grace_frames=10 consecutive outside ticks (confirm/hangover debounce —
standard algorithm, reimplemented).

Tripwires (lines, architect corr. 3): a crossing is
  (a) consecutive FOOT points of the SAME track on OPPOSITE side-signs of
      the line (cross-product signs differ; zero/touch/collinear = NO
      event), AND
  (b) the trajectory segment geometrically intersects the line segment.
Direction = side transition relative to the line's arrow p1->p2:
  right(-1) -> left(+1) = "forward"; left(+1) -> right(-1) = "reverse".
direction_mode both|forward|reverse filters which transitions count.
The naive `prev_y < line_y <= y` pattern is BANNED BY DESIGN (§12).

Absent tracks (god corr. 5): a track missing from a tick counts as
OUTSIDE for grace-advance, but a ZONE_EXIT never fires without a prior
confirmed entry; reappearing INSIDE the grace window resumes counters
without a second entry; a new track_id always starts fresh.

Per-zone live person counts (§12 byproduct): occupancy state is the real
data source — surfaced as a display-only stat, no events.
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.analytics.base import AnalyticModule, EventDraft, FrameContext
from backend.analytics.geometry import (
    point_in_polygon,
    segments_intersect,
    side_sign,
)
from backend.analytics.zones import Zone, ZoneStore
from backend.core.config import FENCE

log = logging.getLogger("trinetra.analytics.fence")

_ZONE_ENTRY = "ZONE_ENTRY"
_ZONE_EXIT = "ZONE_EXIT"
_LINE_CROSSING = "LINE_CROSSING"


class _Occupancy:
    """Private per-(track, polygon-zone) fence state (§12)."""

    __slots__ = ("inside", "confirm_counter", "grace_counter")

    def __init__(self) -> None:
        self.inside = False            # confirmed occupancy (entry fired)
        self.confirm_counter = 0       # consecutive inside ticks (unconfirmed)
        self.grace_counter = 0         # consecutive outside ticks since inside


class _Tripwire:
    """Private per-(track, line-zone) state: last side-sign + foot point."""

    __slots__ = ("prev_sign", "prev_point")

    def __init__(self) -> None:
        self.prev_sign: Optional[int] = None
        self.prev_point: Optional[tuple[float, float]] = None


class FenceAnalytic(AnalyticModule):
    """The MVP module. One instance per session; reset() clears everything."""

    id = "fence"

    def __init__(self, zones: ZoneStore) -> None:
        self._zones = zones            # shared store — NOT private state
        self._occupancy: dict[tuple[int, str], _Occupancy] = {}
        self._trip: dict[tuple[int, str], _Tripwire] = {}
        self._session_id = ""

    # ---- AnalyticModule API ----

    def reset(self, session_id: str) -> None:
        """Clear all private per-track state (fresh session = fresh fence)."""
        self._occupancy.clear()
        self._trip.clear()
        self._session_id = session_id

    def process(self, ctx: FrameContext, tracks) -> list[EventDraft]:
        """One tick: update occupancy/tripwire state, emit transition drafts.

        `tracks` is the read-only TrackView; foot points are frame pixels
        and are normalized here via ctx.shape (§12 frame space).
        """
        w, h = ctx.shape
        if w <= 0 or h <= 0:           # defensive: no shape, no geometry
            return []

        active = self._zones.zones()  # validated, active zones only
        seen: set[int] = set()
        drafts: list[EventDraft] = []

        for track in tracks.active_tracks:
            seen.add(track.track_id)
            fx, fy = track.foot_point
            nx, ny = fx / w, fy / h    # normalized foot point
            for zone in active:
                if zone.kind == "polygon":
                    drafts += self._process_polygon(
                        ctx, zone, track.track_id, nx, ny)
                elif zone.kind == "line":
                    drafts += self._process_line(
                        ctx, zone, track.track_id, nx, ny)

        # absent tracks: advance OUTSIDE counters, never fabricate exits
        # without a prior confirmed entry (god correction 5).
        drafts += self._process_absent(ctx, active, seen)
        return drafts

    # ---- polygons (occupancy) ----

    def _process_polygon(self, ctx: FrameContext, zone: Zone,
                         track_id: int, nx: float, ny: float
                         ) -> list[EventDraft]:
        key = (track_id, zone.id)
        occ = self._occupancy.get(key)
        if occ is None:
            occ = self._occupancy[key] = _Occupancy()
        inside_now = point_in_polygon((nx, ny), zone.polygon_points)
        drafts: list[EventDraft] = []

        if inside_now:
            occ.grace_counter = 0
            if not occ.inside:
                occ.confirm_counter += 1
                if occ.confirm_counter >= FENCE.confirm_frames:
                    occ.inside = True
                    occ.confirm_counter = 0
                    drafts.append(self._draft(
                        ctx, _ZONE_ENTRY, zone, track_id))
            # already inside: no state change, no draft (structural dedup)
        else:
            occ.confirm_counter = 0        # one outside tick resets confirm
            if occ.inside:
                occ.grace_counter += 1
                if occ.grace_counter >= FENCE.exit_grace_frames:
                    occ.inside = False
                    occ.grace_counter = 0
                    drafts.append(self._draft(
                        ctx, _ZONE_EXIT, zone, track_id))
        return drafts

    # ---- tripwires ----

    def _process_line(self, ctx: FrameContext, zone: Zone, track_id: int,
                      nx: float, ny: float) -> list[EventDraft]:
        key = (track_id, zone.id)
        trip = self._trip.get(key)
        if trip is None:
            trip = self._trip[key] = _Tripwire()
        p1, p2 = zone.line_ends
        sign = side_sign(p1, p2, (nx, ny))
        drafts: list[EventDraft] = []

        if sign != 0 and trip.prev_sign is not None \
                and trip.prev_point is not None \
                and sign != trip.prev_sign:
            # opposite side-signs AND geometric segment intersection
            if segments_intersect((trip.prev_point, (nx, ny)), (p1, p2)):
                if trip.prev_sign < 0 and sign > 0:
                    direction = "forward"    # right -> left of arrow
                else:
                    direction = "reverse"    # left -> right of arrow
                if zone.direction_mode == "both" or \
                        direction == zone.direction_mode:
                    drafts.append(self._draft(
                        ctx, _LINE_CROSSING, zone, track_id,
                        direction=direction))

        if sign != 0:                      # zero/touch/collinear: NO event
            trip.prev_sign = sign          # and NO state update (frozen)
            trip.prev_point = (nx, ny)
        return drafts

    # ---- absent tracks ----

    def _process_absent(self, ctx: FrameContext, active: list[Zone],
                        seen: set[int]) -> list[EventDraft]:
        """Tracks missing this tick: treat as OUTSIDE (advance grace), but
        emit ZONE_EXIT only if a prior confirmed entry exists. A track
        reappearing inside grace resumes counters — no second entry."""
        drafts: list[EventDraft] = []
        zone_by_id = {z.id: z for z in active}
        for (track_id, zone_id), occ in list(self._occupancy.items()):
            if track_id in seen:
                continue
            zone = zone_by_id.get(zone_id)
            if zone is None:
                continue
            occ.confirm_counter = 0        # absent = not confirming
            if occ.inside:
                occ.grace_counter += 1
                if occ.grace_counter >= FENCE.exit_grace_frames:
                    occ.inside = False
                    occ.grace_counter = 0
                    drafts.append(self._draft(
                        ctx, _ZONE_EXIT, zone, track_id))
        return drafts

    # ---- byproduct: live per-zone person counts (display-only, §12) ----

    def zone_person_counts(self) -> dict[str, int]:
        """Real occupancy -> live count per zone id (no events)."""
        counts: dict[str, int] = {}
        for (_track_id, zone_id), occ in self._occupancy.items():
            if occ.inside:
                counts[zone_id] = counts.get(zone_id, 0) + 1
        return counts

    # ---- draft construction ----

    @staticmethod
    def _draft(ctx: FrameContext, type_: str, zone: Zone,
               track_id: int, direction: Optional[str] = None
               ) -> EventDraft:
        """M5's only seam: metadata carries is_night, zone_type,
        direction_mode (architect correction 4)."""
        return EventDraft(
            type=type_,
            track_ids=[track_id],
            zone_id=zone.id,
            direction=direction,
            confidence=1.0,               # rule-based (frozen)
            metadata={
                "is_night": ctx.is_night,
                "zone_type": zone.type,
                "direction_mode": zone.direction_mode if zone.kind == "line"
                                else None,
                "zone_kind": zone.kind,
                "tick": ctx.tick,
                "video_ts": ctx.video_ts,
                "luminance": round(ctx.luminance, 2),
            },
        )
