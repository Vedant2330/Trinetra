"""TRINETRA analytics base types — the one boring boundary (frozen §4/§11).

FrameContext (§4): per-tick frame metadata the session computes once and
every module reads (luminance/is_night are RULE-BASED — mean-gray threshold).

EventDraft (§4/§13): a confirmed state transition proposed by a module.
M4 drafts are NOT events yet — the event engine (M6 scope) commits them.
M5's only seam into severity/night wording is the draft's `metadata`,
which MUST carry is_night, zone_type, direction_mode (architect corr. 4).

AnalyticModule (§11): id / process(ctx, tracks) / reset(session_id).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FrameContext:
    """Per-tick context computed by the session (§3 step 3)."""

    tick: int
    wall_ts: float
    video_ts: Optional[float]
    luminance: float
    is_night: bool
    shape: tuple[int, int]              # (width, height) of the processed frame


@dataclass
class EventDraft:
    """One confirmed state transition, pre-commit (§13).

    confidence for M4 rule-based transitions is 1.0 (frozen); the field
    exists so model-driven future modules (face, reid) can carry real
    model scores without a schema change.
    """

    type: str
    track_ids: list[int]
    zone_id: Optional[str] = None
    direction: Optional[str] = None
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)


class AnalyticModule(abc.ABC):
    """Base class for every analytics module (§11).

    Contract:
      - process() is called once per processed tick by the session chain.
      - reset() clears ALL private state; the session calls it on session
        start (per-session isolation is structural, not convention).
    """

    id: str = ""

    @abc.abstractmethod
    def process(self, ctx: FrameContext, tracks) -> list[EventDraft]:
        """Read (ctx, TrackView) -> drafts. Must not mutate tracks."""

    @abc.abstractmethod
    def reset(self, session_id: str) -> None:
        """Clear private state for a fresh session."""
