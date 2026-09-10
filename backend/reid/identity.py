"""M8 identity domain types — observations, global identities, states.

Design notes:
  - `GlobalIdentity` ids are strings of the form ``P-0001`` allocated by
    the correlator/gallery (single allocation point — the gallery). This
    module never mints ids.
  - `IdentityObservation` is the immutable unit cameras produce: an
    embedding (already normalized) plus provenance (camera, track, ts).
    Observations are cheap dataclasses; the gallery owns retention.
  - MatchState is the ONLY vocabulary for identity association strength:
    UNMATCHED / CANDIDATE / CONFIRMED. CANDIDATE means "plausible but
    below the confirm bar" — it is NEVER persisted as a global identity
    association; only CONFIRMED links a camera track to a global person.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np


class MatchState(str, Enum):
    UNMATCHED = "UNMATCHED"
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"


@dataclass(frozen=True)
class IdentityObservation:
    """One appearance embedding captured for one local track.

    `embedding` MUST be L2-normalized by the embedder (cosine == dot).
    `wall_ts` is epoch seconds (FrameContext.wall_ts), `video_ts`
    optional (None for live cameras).
    """

    camera_id: str
    track_id: int
    embedding: np.ndarray
    wall_ts: float
    video_ts: Optional[float] = None
    tick: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.embedding.ndim == 1:
            raise ValueError("embedding must be 1-D")

    def copy_with(self, **kw) -> "IdentityObservation":
        d = dict(camera_id=self.camera_id, track_id=self.track_id,
                 embedding=self.embedding, wall_ts=self.wall_ts,
                 video_ts=self.video_ts, tick=self.tick)
        d.update(kw)
        return IdentityObservation(**d)


@dataclass
class MovementPoint:
    """One point in a global identity's movement timeline."""

    wall_ts: float
    camera_id: str
    track_id: int
    kind: str          # first_seen | moving | camera_transition | zone_entry | ... (deterministic verbs only)
    note: Optional[str] = None
    zone_id: Optional[str] = None

    def as_dict(self) -> dict:
        return {
            "wall_ts": self.wall_ts,
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "kind": self.kind,
            "note": self.note,
            "zone_id": self.zone_id,
        }


@dataclass
class GlobalIdentity:
    """A globally-correlated person.

    Slots referencing camera tracks are CONFIRMED associations only.
    `track_bindings` maps (camera_id, local_track_id) -> first-linked ts.
    A local track binds to exactly one global identity (binding is
    exclusive; the correlator enforces first-wins with a review seam).
    """

    global_person_id: str                      # "P-0001" — gallery-minted
    created_ts: float
    first_seen_ts: float
    last_seen_ts: float
    observations: int = 0
    # (camera_id, track_id) -> {"ts": link_ts, "state": MatchState}
    track_bindings: dict[tuple[str, int], dict] = field(default_factory=dict)
    # camera_id -> deque of recent EMA embeddings (gallery retains; the
    # identity keeps only provenance + the LIVE exemplar set)
    exemplars: dict[str, list[np.ndarray]] = field(default_factory=dict)
    candidates: list[dict] = field(default_factory=list)   # unconfirmed, review-only
    confidence: float = 0.0                   # last CONFIRMED match confidence
    class_name: str = "person"

    # ---- queries (investigation surface, mandate §10) ----

    @property
    def cameras_visited(self) -> list[str]:
        return sorted({cam for (cam, _tid) in self.track_bindings})

    @property
    def local_track_ids(self) -> list[tuple[str, int]]:
        return sorted(self.track_bindings.keys())

    def is_same_person(self, camera_id: str, track_id: int) -> bool:
        return (camera_id, track_id) in self.track_bindings

    def exemplar_matrix(self, camera_id: str) -> Optional[np.ndarray]:
        """(k, d) stacked exemplars for one camera, or None."""
        ex = self.exemplars.get(camera_id)
        if not ex:
            return None
        return np.stack(ex)

    def as_dict(self) -> dict:
        return {
            "global_person_id": self.global_person_id,
            "created_ts": self.created_ts,
            "first_seen_ts": self.first_seen_ts,
            "last_seen_ts": self.last_seen_ts,
            "observations": self.observations,
            "confidence": round(self.confidence, 4),
            "cameras_visited": self.cameras_visited,
            "track_bindings": [
                {"camera_id": cam, "track_id": tid, "linked_ts": meta["ts"],
                 "state": meta["state"].value if isinstance(
                     meta["state"], MatchState) else str(meta["state"])}
                for (cam, tid), meta in sorted(self.track_bindings.items())
            ],
            "candidate_count": len(self.candidates),
        }
