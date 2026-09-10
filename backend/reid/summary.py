"""M8 deterministic clip/investigation summary (mandate §11/§12).

build_clip_summary() derives a structured JSON-able object STRICTLY from
verified backend state (correlator gallery + movement history + zone
events passed in). It is the LLM-ready surface: Hermes/GLM may later
render it into natural language, but the numbers here are the SOURCE OF
TRUTH — the contract explicitly forbids an LLM from inventing
transitions, identities, events or coordinates (docs/M8_*_CONTRACT.md).

Allowed summary semantics = deterministic aggregation only:
counts, cameras, zones, transitions, timeline bounds. No behavioral
interpretation, no threat language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.reid.correlation import GlobalIdentityCorrelator
from backend.reid.history import GlobalMovementHistory


@dataclass(frozen=True)
class ClipSummary:
    """Deterministic summary of one clip / observation window."""

    clip_duration: float
    unique_global_persons: int
    cameras: tuple[str, ...]
    tracks: int
    zones_entered: tuple[str, ...]
    tripwires_crossed: int
    identity_transitions: int
    alerts: int
    persons: tuple[dict, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = {
            "clip_duration": round(self.clip_duration, 3),
            "unique_global_persons": self.unique_global_persons,
            "cameras": list(self.cameras),
            "tracks": self.tracks,
            "zones_entered": list(self.zones_entered),
            "tripwires_crossed": self.tripwires_crossed,
            "identity_transitions": self.identity_transitions,
            "alerts": self.alerts,
            "persons": [dict(p) for p in self.persons],
        }
        return d

    # the shape mandated in the brief (plus persons detail)
    def as_mandated_dict(self) -> dict:
        d = self.as_dict()
        d.pop("persons", None)
        return d


def build_clip_summary(
    correlator: GlobalIdentityCorrelator,
    history: GlobalMovementHistory,
    *,
    alerts: int = 0,
    window_start: Optional[float] = None,
    window_end: Optional[float] = None,
    clip_duration: Optional[float] = None,
) -> ClipSummary:
    """Derive the summary from real state. `alerts` = real committed
    event count for the window (caller owns event bookkeeping — this
    module never counts what it cannot see)."""
    identities = correlator.all_identities()
    if not identities:
        return ClipSummary(
            clip_duration=clip_duration or 0.0,
            unique_global_persons=0, cameras=(), tracks=0,
            zones_entered=(), tripwires_crossed=0,
            identity_transitions=0, alerts=alerts)

    # window bounds from real observation timestamps
    if window_start is None:
        window_start = min(i.first_seen_ts for i in identities)
    if window_end is None:
        window_end = max(i.last_seen_ts for i in identities)
    duration = clip_duration if clip_duration is not None \
        else max(0.0, window_end - window_start)

    cameras: set[str] = set()
    tracks = 0
    zones: set[str] = set()
    tripwires = 0
    transitions = 0
    persons: list[dict] = []

    for ident in identities:
        tracks += len(ident.track_bindings)
        cameras.update(ident.cameras_visited)
        tl = history.timeline(ident.global_person_id)
        zones.update(p["zone_id"] for p in tl
                     if p["kind"] == "zone_entry" and p.get("zone_id"))
        tripwires += sum(1 for p in tl if p["kind"] == "tripwire_crossing")
        transitions += sum(1 for p in tl
                           if p["kind"] == "camera_transition")
        # dwell/stationary analysis from real points
        stationary_points = sum(
            1 for p in tl if p["kind"] in ("stationary",
                                           "prolonged_stationary"))
        persons.append({
            "global_person_id": ident.global_person_id,
            "first_seen": ident.first_seen_ts,
            "last_seen": ident.last_seen_ts,
            "cameras": ident.cameras_visited,
            "tracks": [{"camera_id": c, "track_id": t}
                       for (c, t) in ident.local_track_ids],
            "observations": ident.observations,
            "confidence": round(ident.confidence, 4),
            "zone_entries": [p["zone_id"] for p in tl
                             if p["kind"] == "zone_entry" and p.get("zone_id")],
            "stationary_periods": stationary_points,
        })

    return ClipSummary(
        clip_duration=duration,
        unique_global_persons=len(identities),
        cameras=tuple(sorted(cameras)),
        tracks=tracks,
        zones_entered=tuple(sorted(z for z in zones if z)),
        tripwires_crossed=tripwires,
        identity_transitions=transitions,
        alerts=alerts,
        persons=tuple(persons),
    )
