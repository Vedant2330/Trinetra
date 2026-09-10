"""TRINETRA Crowd Density Analytic — Count-Based Zone Density.

Evaluates crowd density strictly via count thresholds:
- CROWD_DENSITY_MEDIUM: >= 4 persons in zone sustained for >= 2 consecutive frames.
- CROWD_DENSITY_HIGH: >= 8 persons in zone sustained for >= 2 consecutive frames.

Zero AGPL dependencies. Pure count-based geometry from FenceAnalytic.zone_person_counts().
"""

from __future__ import annotations

from typing import Any, Optional

from backend.analytics.base import AnalyticModule, EventDraft, FrameContext


class CrowdDensityAnalytic(AnalyticModule):
    """Evaluates count-based crowd density thresholds per zone."""

    id = "crowd"

    def __init__(
        self,
        medium_thresh: int = 4,
        high_thresh: int = 8,
        sustain_frames: int = 2,
        fence_analytic: Optional[Any] = None,
    ) -> None:
        self._medium_thresh = int(medium_thresh)
        self._high_thresh = int(high_thresh)
        self._sustain_frames = max(1, int(sustain_frames))
        self._fence_analytic = fence_analytic
        self._session_id = ""

        # Per-zone consecutive sustain counters
        self._medium_consecutive: dict[str, int] = {}
        self._high_consecutive: dict[str, int] = {}

        # Per-zone last fire timestamp
        self._last_medium_fire: dict[str, float] = {}
        self._last_high_fire: dict[str, float] = {}

    def reset(self, session_id: str) -> None:
        """Clear all per-zone density counters."""
        self._session_id = session_id
        self._medium_consecutive.clear()
        self._high_consecutive.clear()
        self._last_medium_fire.clear()
        self._last_high_fire.clear()

    def _zone_type(self, zone_id: str) -> str:
        """Resolve a zone's WATCH/RESTRICTED type for the engine's
        severity escalation (RESTRICTED +1). Reads through the fence
        analytic's shared zone store so CRUD updates are visible
        (same live re-read pattern as FenceAnalytic). Scene-level
        (__scene__) fallback counts have no zone row — 'SCENE'."""
        if zone_id == "__scene__":
            return "SCENE"
        zones = getattr(self._fence_analytic, "_zones", None)
        if zones is not None:
            try:
                zone = zones.get(zone_id)
                if zone is not None and getattr(zone, "type", ""):
                    return str(zone.type)
            except Exception:  # noqa: BLE001 — metadata enrichment must not kill the tick
                pass
        return ""

    def update(
        self,
        zone_counts: dict[str, int],
        video_ts: float = 0.0,
        is_night: bool = False,
        tick: int = 0,
    ) -> list[EventDraft]:
        """Evaluate density directly from a zone_counts dictionary."""
        ctx = FrameContext(
            tick=tick,
            wall_ts=video_ts,
            video_ts=video_ts,
            luminance=128.0,
            is_night=is_night,
            shape=(640, 480),
        )
        return self._evaluate_counts(ctx, zone_counts)

    def process(self, ctx: FrameContext, tracks: Any) -> list[EventDraft]:
        """Evaluate density using live counts from FenceAnalytic or active tracks."""
        zone_counts: dict[str, int] = {}
        if self._fence_analytic is not None and hasattr(self._fence_analytic, "zone_person_counts"):
            zone_counts = self._fence_analytic.zone_person_counts()

        # If no zones configured in fence analytic, fallback to total scene persons
        if not zone_counts and hasattr(tracks, "active_tracks"):
            persons = [
                t for t in tracks.active_tracks
                if getattr(t, "class_name", "") == "person"
            ]
            if persons:
                zone_counts["__scene__"] = len(persons)

        return self._evaluate_counts(ctx, zone_counts)

    def _evaluate_counts(
        self,
        ctx: FrameContext,
        zone_counts: dict[str, int],
    ) -> list[EventDraft]:
        drafts: list[EventDraft] = []
        wall_ts = ctx.wall_ts
        seen_zones = set(zone_counts.keys())

        for zid, count in zone_counts.items():
            # Check High Threshold (>= 8)
            if count >= self._high_thresh:
                self._high_consecutive[zid] = self._high_consecutive.get(zid, 0) + 1
                self._medium_consecutive[zid] = self._medium_consecutive.get(zid, 0) + 1

                if self._high_consecutive[zid] >= self._sustain_frames:
                    if zid not in self._last_high_fire or (wall_ts - self._last_high_fire[zid]) >= 10.0:
                        self._last_high_fire[zid] = wall_ts
                        drafts.append(
                            EventDraft(
                                type="CROWD_DENSITY_HIGH",
                                track_ids=[],
                                zone_id=None if zid == "__scene__" else zid,
                                direction=None,
                                confidence=1.0,
                                metadata={
                                    "zone_id": zid,
                                    "zone_type": self._zone_type(zid),
                                    "person_count": count,
                                    "density_level": "HIGH",
                                    "is_night": ctx.is_night,
                                    "consecutive_ticks": self._high_consecutive[zid],
                                    "video_ts": ctx.video_ts,
                                    "tick": ctx.tick,
                                },
                            )
                        )
            # Check Medium Threshold (>= 4)
            elif count >= self._medium_thresh:
                self._high_consecutive[zid] = 0
                self._medium_consecutive[zid] = self._medium_consecutive.get(zid, 0) + 1

                if self._medium_consecutive[zid] >= self._sustain_frames:
                    if zid not in self._last_medium_fire or (wall_ts - self._last_medium_fire[zid]) >= 10.0:
                        self._last_medium_fire[zid] = wall_ts
                        drafts.append(
                            EventDraft(
                                type="CROWD_DENSITY_MEDIUM",
                                track_ids=[],
                                zone_id=None if zid == "__scene__" else zid,
                                direction=None,
                                confidence=1.0,
                                metadata={
                                    "zone_id": zid,
                                    "zone_type": self._zone_type(zid),
                                    "person_count": count,
                                    "density_level": "MEDIUM",
                                    "is_night": ctx.is_night,
                                    "consecutive_ticks": self._medium_consecutive[zid],
                                    "video_ts": ctx.video_ts,
                                    "tick": ctx.tick,
                                },
                            )
                        )
            else:
                self._high_consecutive[zid] = 0
                self._medium_consecutive[zid] = 0

        # Purge deleted/inactive zones
        for zid in list(self._medium_consecutive):
            if zid not in seen_zones:
                self._medium_consecutive.pop(zid, None)
                self._high_consecutive.pop(zid, None)

        return drafts
