"""M8 GlobalIdentityCorrelator — observations in, global identities out.

The one stateful orchestrator of the reid package:

    IdentityObservation --observe()--> match/extend/mint decision
                                        (Matcher verdict, mandate §4)
    CONFIRMED match  -> extend existing identity (bind track, add
                        exemplar, update last_seen)
    CANDIDATE match  -> record on the identity's review-only candidate
                        list; a NEW identity is minted for the track
                        (never link on candidate evidence alone)
    UNMATCHED        -> mint a new identity

Idempotence / no-fake rules enforced here:
  - A (camera, track) already CONFIRMED-bound re-observes -> the same
    identity is returned (state CONFIRMED, reason "already bound");
    no new identity, no re-bind, no duplicate transition.
  - Two different local tracks on the SAME camera never merge into one
    identity via re-observation (that is a job for local tracking, not
    Re-ID — a same-camera merge is only possible if the matcher's
    camera graph explicitly permits it, which MVP does not).
  - Every observe() returns a CorrelationOutcome with the complete
    honest story (what matched, why, what state).

Concurrency: one lock around the whole decide-and-mutate section
(matches the gallery's RLock; bounded contention — camera threads call
observe a few times per second at most).
"""

from __future__ import annotations

import threading
from typing import Optional

from backend.reid.gallery import IdentityGallery
from backend.reid.identity import (
    GlobalIdentity,
    IdentityObservation,
    MatchState,
)
from backend.reid.matcher import Matcher, MatchResult


class CorrelationOutcome:
    """What observe() did — the honest story for events + history."""

    __slots__ = ("observation", "result", "identity", "is_new",
                 "transitioned")

    def __init__(self, observation: IdentityObservation,
                 result: MatchResult, identity: GlobalIdentity,
                 is_new: bool, transitioned: bool) -> None:
        self.observation = observation
        self.result = result          # the matcher verdict
        self.identity = identity      # the identity the track now maps to
        self.is_new = is_new          # a fresh identity was minted
        self.transitioned = transitioned  # this obs added a NEW camera binding

    @property
    def matched(self) -> bool:
        return self.result.state is MatchState.CONFIRMED

    def as_dict(self) -> dict:
        return {
            "global_person_id": self.identity.global_person_id,
            "camera_id": self.observation.camera_id,
            "track_id": self.observation.track_id,
            "state": self.result.state.value,
            "similarity": round(self.result.similarity, 4),
            "confidence": round(self.result.confidence, 4),
            "reason": self.result.reason,
            "is_new": self.is_new,
            "transitioned": self.transitioned,
        }


class GlobalIdentityCorrelator:
    """Thread-safe correlator over one shared gallery."""

    def __init__(self, gallery: Optional[IdentityGallery] = None,
                 matcher: Optional[Matcher] = None) -> None:
        self._gallery = gallery or IdentityGallery()
        self._matcher = matcher or Matcher()
        self._lock = threading.Lock()

    # ---- wiring (read-only accessors) ----

    @property
    def gallery(self) -> IdentityGallery:
        return self._gallery

    @property
    def matcher(self) -> Matcher:
        return self._matcher

    # ---- the one entry point ----

    def observe(self, obs: IdentityObservation,
                obs_class: str = "person") -> CorrelationOutcome:
        """Correlate one observation. See module docstring."""
        with self._lock:
            # 0. already bound? identity is settled for this track
            bound = self._gallery.identity_for_track(
                obs.camera_id, obs.track_id)
            if bound is not None:
                self._absorb(bound, obs)
                result = MatchResult(
                    MatchState.CONFIRMED, 1.0, bound.confidence,
                    bound.global_person_id, "already bound")
                return CorrelationOutcome(obs, result, bound,
                                          is_new=False, transitioned=False)

            # 1. match against live identities
            result = self._matcher.best_match(
                obs, self._gallery.all_identities(), obs_class=obs_class)

            if result.state is MatchState.CONFIRMED:
                ident = self._gallery.get(result.identity)
                assert ident is not None           # minted ids never vanish
                was_new_camera = not ident.is_same_person(
                    obs.camera_id, obs.track_id)
                self._bind(ident, obs, result)
                return CorrelationOutcome(obs, result, ident,
                                          is_new=False,
                                          transitioned=was_new_camera)

            if result.state is MatchState.CANDIDATE:
                # honest: keep the candidate on record for review, but
                # the track still needs a (new) identity home.
                ident = self._gallery.get(result.identity)
                if ident is not None:
                    ident.candidates.append({
                        "camera_id": obs.camera_id,
                        "track_id": obs.track_id,
                        "wall_ts": obs.wall_ts,
                        "similarity": round(result.similarity, 4),
                        "reason": result.reason,
                    })
                    if len(ident.candidates) > 50:   # bounded review list
                        del ident.candidates[:-50]
                minted = self._gallery.mint(obs.wall_ts, class_name=obs_class)
                self._bind(minted, obs, result=None)
                return CorrelationOutcome(
                    obs, result, minted, is_new=True, transitioned=False)

            # UNMATCHED -> mint
            minted = self._gallery.mint(obs.wall_ts, class_name=obs_class)
            self._bind(minted, obs, result=None)
            return CorrelationOutcome(obs, result, minted,
                                      is_new=True, transitioned=False)

    # ---- internals ----

    def _bind(self, ident: GlobalIdentity, obs: IdentityObservation,
             result: Optional[MatchResult]) -> None:
        """Bind track -> identity (CONFIRMED), absorb observation."""
        key = (obs.camera_id, obs.track_id)
        link_state = MatchState.CONFIRMED
        ident.track_bindings[key] = {
            "ts": obs.wall_ts,
            "state": link_state,
            "similarity": (round(result.similarity, 4)
                           if result is not None else None),
        }
        self._absorb(ident, obs)
        if result is not None and result.confidence > 0:
            ident.confidence = max(ident.confidence,
                                   result.confidence)

    def _absorb(self, ident: GlobalIdentity, obs: IdentityObservation) -> None:
        """Update last_seen + exemplars for an already-owned observation."""
        ident.observations += 1
        if obs.wall_ts > ident.last_seen_ts:
            ident.last_seen_ts = obs.wall_ts
        if obs.wall_ts < ident.first_seen_ts:
            ident.first_seen_ts = obs.wall_ts
        self._gallery.add_exemplar(ident, obs.camera_id, obs.embedding)

    # ---- query helpers (events, history, API) ----

    def identity_for(self, camera_id: str,
                     track_id: int) -> Optional[GlobalIdentity]:
        return self._gallery.identity_for_track(camera_id, track_id)

    def get(self, pid: str) -> Optional[GlobalIdentity]:
        return self._gallery.get(pid)

    def all_identities(self) -> list[GlobalIdentity]:
        return self._gallery.all_identities()
