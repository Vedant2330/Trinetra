"""M8 matcher — cosine similarity + plausibility gates -> MatchResult.

Decision structure (mandate §4, NO FAKE IDENTITY):
  1. cosine(query, best exemplar of candidate identity) — max over the
     identity's exemplar set (per-camera and recent history), because a
     person's appearance varies; max-over-exemplars is the standard
     gallery matching rule.
  2. Temporal plausibility: a match between observations whose time
     gap exceeds max_gap_s is only possible if travel between the two
     cameras is configured plausible (camera graph); unconfigured ->
     conservative fallback (same gap rule). Violations demote or veto.
  3. Class guard: identities only match same-class tracks (person vs
     person). Different class -> UNMATCHED, always.

Thresholds (defaults, config [reid]):
  confirm_similarity   0.80  — >= this AND gates pass -> CONFIRMED
  candidate_similarity 0.55  — >= this but < confirm -> CANDIDATE
  below candidate       -> UNMATCHED (never merged, mandate §4 example:
  0.55 must NOT merge)

CANDIDATE is reported (surface for review / UI), never linked.
Confidence = similarity scaled by gate outcomes (soft penalties), so
the reported number stays honest about what actually supported it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from backend.core.config import REID
from backend.reid.identity import GlobalIdentity, IdentityObservation, MatchState


@dataclass(frozen=True)
class MatcherPolicy:
    confirm_similarity: float = 0.80
    candidate_similarity: float = 0.55
    max_gap_s: float = 600.0            # temporal plausibility ceiling
    min_confidence: float = 0.5         # report floor for CONFIRMED

    @classmethod
    def from_config(cls) -> "MatcherPolicy":
        return cls(
            confirm_similarity=REID.confirm_similarity,
            candidate_similarity=REID.candidate_similarity,
            max_gap_s=REID.max_gap_s,
        )


@dataclass(frozen=True)
class CameraTransition:
    """Optional plausibility edge in the camera graph (seconds)."""
    from_camera: str
    to_camera: str
    min_travel_s: float = 0.0
    max_travel_s: float = 600.0


@dataclass(frozen=True)
class MatchResult:
    """The matcher's complete verdict for one observation."""

    state: MatchState
    similarity: float                    # best raw cosine
    confidence: float                    # gated confidence
    identity: Optional[str] = None       # global_person_id when matched
    reason: str = ""

    @property
    def matched(self) -> bool:
        return self.state is MatchState.CONFIRMED


class Matcher:
    """Stateless decision core (pure functions over immutable data)."""

    def __init__(self, policy: Optional[MatcherPolicy] = None,
                 camera_graph: Optional[dict] = None) -> None:
        """`camera_graph`: {(from_cam, to_cam): CameraTransition} —
        optional; absent edges fall back to the global max_gap_s rule."""
        self.policy = policy or MatcherPolicy.from_config()
        self.camera_graph = camera_graph or {}

    # ---- similarity ----

    @staticmethod
    def cosine(a: np.ndarray, b: np.ndarray) -> float:
        if a.shape != b.shape:
            raise ValueError("embedding dimension mismatch")
        return float(np.dot(a, b))       # both L2-normalized upstream

    def similarity_to(self, obs: IdentityObservation,
                       identity: GlobalIdentity) -> float:
        """Best cosine over the identity's exemplar set. No exemplars
        for a camera -> cross-camera exemplars (that is the point).
        Returns -1.0 when the identity has no exemplars at all."""
        best = -1.0
        for _cam, bucket in identity.exemplars.items():
            if not bucket:
                continue
            matrix = np.stack(bucket)               # (k, d)
            sims = matrix @ obs.embedding           # (k,) cosines
            m = float(sims.max())
            if m > best:
                best = m
        return best

    # ---- gates ----

    def _temporal_verdict(self, obs: IdentityObservation,
                          identity: GlobalIdentity,
                          ) -> tuple[bool, str]:
        """True if plausible. Gap too large -> veto (reason)."""
        gap = obs.wall_ts - identity.last_seen_ts
        if gap < 0:
            gap = 0.0                      # same instant / clock skew
        edge = self._edge_for(identity.cameras_visited, obs.camera_id)
        ceiling = edge.max_travel_s if edge else self.policy.max_gap_s
        if gap > ceiling:
            return False, (
                f"temporal: gap {gap:.1f}s > ceiling {ceiling:.1f}s")
        return True, ""

    def _edge_for(self, from_cameras: list[str],
                  to_camera: str) -> Optional[CameraTransition]:
        for fc in from_cameras:
            t = self.camera_graph.get((fc, to_camera))
            if t is not None:
                return t
        return None

    # ---- main ----

    def best_match(self, obs: IdentityObservation,
                   identities: list[GlobalIdentity],
                   obs_class: str = "person",
                   ) -> MatchResult:
        """Decide the best association for `obs` among live identities."""
        best: Optional[tuple[float, GlobalIdentity]] = None
        for ident in identities:
            if ident.class_name != obs_class:
                continue                  # class guard — hard
            sim = self.similarity_to(obs, ident)
            if sim < self.policy.candidate_similarity:
                continue                  # below candidate bar — not even close
            if best is None or sim > best[0]:
                best = (sim, ident)
        if best is None:
            return MatchResult(MatchState.UNMATCHED, -1.0, 0.0, None,
                               "no identity above candidate threshold")
        sim, ident = best
        # candidate band first
        if sim < self.policy.confirm_similarity:
            return MatchResult(MatchState.CANDIDATE, sim, sim,
                               ident.global_person_id,
                               f"similarity {sim:.3f} < confirm "
                               f"{self.policy.confirm_similarity:.2f}")
        # confirm band: gates
        ok, reason = self._temporal_verdict(obs, ident)
        if not ok:
            return MatchResult(MatchState.CANDIDATE, sim, sim,
                               ident.global_person_id, reason)
        confidence = self._confidence(sim, obs, ident)
        if confidence < self.policy.min_confidence:
            return MatchResult(MatchState.CANDIDATE, sim, confidence,
                               ident.global_person_id,
                               f"confidence {confidence:.3f} < floor")
        return MatchResult(
            MatchState.CONFIRMED, sim, confidence,
            ident.global_person_id,
            f"sim {sim:.3f} >= {self.policy.confirm_similarity:.2f}, "
            f"gates passed")

    @staticmethod
    def _confidence(sim: float, obs: IdentityObservation,
                    ident: GlobalIdentity) -> float:
        """Honest confidence: similarity, softly discounted by time gap
        and exemplar sparsity. Range (0, sim]."""
        c = max(0.0, min(1.0, sim))
        gap = max(0.0, obs.wall_ts - ident.last_seen_ts)
        # gentle decay: 1.0 at gap=0 to 0.85 at 600s
        decay = max(0.85, 1.0 - (gap / 600.0) * 0.15) if gap <= 600.0 else 0.85
        n_ex = sum(len(v) for v in ident.exemplars.values())
        support = min(1.0, 0.9 + 0.1 * (n_ex / 5.0))   # more sightings -> fuller
        return float(min(1.0, c * decay * support))
