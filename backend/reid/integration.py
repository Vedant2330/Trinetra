"""M8 integration seam — the ONLY surface a camera session needs.

DELIBERATELY NOT an AnalyticModule: §11 modules receive (ctx, TrackView)
— no pixels. Re-ID needs appearance CROPS, so it is a service the
session calls with the frame, next to (not inside) the analytics chain:

    # one call per processed tick, per camera (documented wiring):
    drafts += reid.process_tick(camera_id, ctx, view, frame)
    drafts = reid.enrich_drafts(camera_id, drafts)

Multi-camera model (mandate §6): one MultiCameraReIdService per app;
register_camera() per active camera session. Each camera keeps its own
sampling policy + pacing state; local tracking authority remains
ByteTrack/TrackStore/ProcessingSession — this module NEVER tracks,
detects, or spawns threads.

Events (mandate §8, minimal set — existing infrastructure carries the
rest):
  - PERSON_IDENTITY_MATCHED  — a local track got its FIRST confirmed
    global identity (i.e. the identity's first camera), INFO,
    metadata: global_person_id, similarity, confidence.
  - PERSON_CAMERA_TRANSITION — a CONFIRMED correlation bound the
    identity on a camera it had not been seen on, INFO, metadata:
    global_person_id, from_camera, to_camera, similarity, confidence.
    Emitted once per (identity, camera) — duplicates suppressed.
  - Zone/tripwire/detection drafts are NOT duplicated: enrich_drafts()
    attaches global_person_id (+ global track provenance) to the
    EXISTING ZONE_ENTRY/LINE_CROSSING/PERSON_DETECTED metadata, so the
    M5 severity ladder, cooldown and snapshots apply unchanged.
    (GLOBAL_PERSON_ZONE_ALERT would be a redundant event type — the
    mandate's "do not create unnecessary event types" clause.)

All returned drafts are plain backend.analytics.EventDraft objects —
the existing EventEngine commits them with zero engine changes.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from backend.analytics.base import EventDraft, FrameContext
from backend.reid.correlation import CorrelationOutcome, GlobalIdentityCorrelator
from backend.reid.embedder import (
    DummyEmbedder,
    OpenCVDnnEmbedder,
    ReIDEmbedder,
    TorchScriptEmbedder,
    preprocess_crop,
)
from backend.reid.gallery import IdentityGallery
from backend.reid.history import GlobalMovementHistory
from backend.reid.identity import GlobalIdentity, MatchState
from backend.reid.matcher import Matcher, MatcherPolicy
from backend.reid.sampling import ReIDSamplingPolicy, SamplePolicy
from backend.core.config import REID

log = logging.getLogger("trinetra.reid.integration")

_ENRICHABLE_TYPES = frozenset({
    "ZONE_ENTRY", "ZONE_EXIT", "LINE_CROSSING",
    "PERSON_DETECTED", "VEHICLE_DETECTED",
})


def _clamp_crop(frame: np.ndarray, bbox: list[float]) -> Optional[np.ndarray]:
    """Crop bbox from frame, clamped to frame bounds. None if empty."""
    h, w = frame.shape[:2]
    x1 = max(0, int(bbox[0])); y1 = max(0, int(bbox[1]))
    x2 = min(w, int(bbox[2])); y2 = min(h, int(bbox[3]))
    if x2 - x1 < 4 or y2 - y1 < 8:      # degenerate crop — no identity claim
        return None
    return frame[y1:y2, x1:x2]


def make_embedder(name: Optional[str] = None) -> ReIDEmbedder:
    """Factory honoring config [reid].embedder. 'cv2dnn' is the Phase-2
    PRIMARY (fast-reid ONNX via cv2.dnn, zero new deps); 'dummy' is the
    honest test embedder; 'torchscript' is the retained M8 seam
    (unavailable until a model file exists — callers MUST check
    .available)."""
    name = name or REID.embedder
    if name == "cv2dnn":
        return OpenCVDnnEmbedder()
    if name == "dummy":
        return DummyEmbedder()
    if name == "torchscript":
        return TorchScriptEmbedder()
    raise ValueError(f"unknown reid embedder {name!r}")


class CameraReIdSession:
    """Per-camera pacing + provenance over the shared correlator."""

    __slots__ = ("camera_id", "sampling", "class_names")

    def __init__(self, camera_id: str, sampling: ReIDSamplingPolicy,
                 class_names: Optional[set[str]] = None) -> None:
        self.camera_id = camera_id
        self.sampling = sampling
        self.class_names = class_names or {"person"}


class MultiCameraReIdService:
    """App-scoped identity service (one per app; cameras register)."""

    def __init__(self, embedder: Optional[ReIDEmbedder] = None,
                 correlator: Optional[GlobalIdentityCorrelator] = None,
                 history: Optional[GlobalMovementHistory] = None,
                 policy: Optional[SamplePolicy] = None) -> None:
        self._embedder = embedder if embedder is not None else make_embedder()
        self.correlator = correlator or GlobalIdentityCorrelator(
            gallery=IdentityGallery(), matcher=Matcher(
                MatcherPolicy.from_config()))
        self.history = history or GlobalMovementHistory()
        self._policy = policy or SamplePolicy()
        self._cameras: dict[str, CameraReIdSession] = {}

    # ---- camera lifecycle ----

    def register_camera(self, camera_id: str,
                        class_names: Optional[set[str]] = None,
                        policy: Optional[SamplePolicy] = None
                        ) -> CameraReIdSession:
        if camera_id in self._cameras:
            return self._cameras[camera_id]
        sess = CameraReIdSession(
            camera_id, ReIDSamplingPolicy(policy or self._policy),
            class_names)
        self._cameras[camera_id] = sess
        return sess

    def unregister_camera(self, camera_id: str) -> None:
        self._cameras.pop(camera_id, None)

    @property
    def embedder_available(self) -> bool:
        return self._embedder.available

    # ---- the per-tick entry point ----

    def process_tick(self, camera_id: str, ctx: FrameContext,
                     view, frame: Optional[np.ndarray] = None,
                     ) -> list[EventDraft]:
        """One processed tick for one camera. Walks the ACTIVE person
        tracks, applies selective sampling, embeds crops, correlates,
        records history, and returns NEW-match drafts (INFO events).

        `view` = the session's read-only TrackView; `frame` = the raw
        frame the detections came from (crops are taken from it). If
        the embedder is unavailable, this is a documented NO-OP — no
        identity is ever fabricated (mandate §4/§14)."""
        sess = self._cameras.get(camera_id)
        if sess is None or not self._embedder.available:
            return []

        drafts: list[EventDraft] = []
        for track in view.active_tracks:
            if track.class_name not in sess.class_names:
                continue                       # persons only in MVP
            if not sess.sampling.should_sample(
                    track.track_id, ctx.tick, ctx.wall_ts,
                    track.frames_seen):
                continue
            crop = _clamp_crop(frame, track.last_bbox) \
                if frame is not None else None
            if crop is None:
                continue                       # degenerate crop: skip honestly
            try:
                embedding = self._embedder.embed(crop)
            except Exception as e:              # noqa: BLE001 — observe, never kill the tick
                log.warning("reid embed failed cam=%s track=%s: %s",
                            camera_id, track.track_id, e)
                continue
            sess.sampling.note_embed()
            drafts += self._observe(camera_id, ctx, track.track_id,
                                    embedding)
        return drafts

    def observe_embedding(self, camera_id: str, ctx: FrameContext,
                          track_id: int, embedding: np.ndarray,
                          class_name: str = "person") -> list[EventDraft]:
        """Direct-embedding path (synthetic tests / future providers
        that already hold crops). Same correlation + history + draft
        semantics as process_tick."""
        return self._observe(camera_id, ctx, track_id, embedding,
                             class_name)

    # ---- internals ----

    def _observe(self, camera_id: str, ctx: FrameContext, track_id: int,
                 embedding: np.ndarray,
                 class_name: str = "person") -> list[EventDraft]:
        from backend.reid.identity import IdentityObservation
        obs = IdentityObservation(
            camera_id=camera_id, track_id=track_id,
            embedding=embedding, wall_ts=ctx.wall_ts,
            video_ts=ctx.video_ts, tick=ctx.tick)
        outcome = self.correlator.observe(obs, obs_class=class_name)
        return self._record(camera_id, ctx, outcome)

    def _record(self, camera_id: str, ctx: FrameContext,
                outcome: CorrelationOutcome) -> list[EventDraft]:
        """History bookkeeping + draft construction for one outcome."""
        ident = outcome.identity
        pid = ident.global_person_id
        drafts: list[EventDraft] = []
        meta_common = {
            "is_night": ctx.is_night,
            "tick": ctx.tick,
            "video_ts": ctx.video_ts,
            "global_person_id": pid,
            "camera_id": camera_id,
            "local_track_id": outcome.observation.track_id,
        }

        if outcome.is_new:
            # first home for this identity on this camera
            self.history.note_first_seen(
                ident, camera_id, outcome.observation.track_id,
                ctx.wall_ts)
            drafts.append(EventDraft(
                type="PERSON_IDENTITY_MATCHED",
                track_ids=[outcome.observation.track_id],
                zone_id=None, direction=None,
                confidence=outcome.result.confidence
                if outcome.result.confidence > 0 else 0.0,
                metadata={
                    **meta_common,
                    "match_state": outcome.result.state.value,
                    "similarity": round(outcome.result.similarity, 4),
                    "reason": outcome.result.reason,
                }))
            return drafts

        if outcome.matched and outcome.transitioned:
            # a NEW camera binding for an EXISTING identity
            recorded = self.history.note_transition(
                pid, camera_id, outcome.observation.track_id,
                from_camera=ident.cameras_visited[0]
                if ident.cameras_visited else None,
                wall_ts=ctx.wall_ts)
            if recorded:                       # once per (identity, camera)
                drafts.append(EventDraft(
                    type="PERSON_CAMERA_TRANSITION",
                    track_ids=[outcome.observation.track_id],
                    zone_id=None, direction=None,
                    confidence=outcome.result.confidence,
                    metadata={
                        **meta_common,
                        "match_state": "CONFIRMED",
                        "similarity": round(outcome.result.similarity, 4),
                        "from_camera": ident.cameras_visited[0]
                        if len(ident.cameras_visited) > 1 else None,
                    }))
        return drafts

    # ---- draft enrichment (fence integration, mandate §9) ----

    def enrich_drafts(self, camera_id: str,
                      drafts: list[EventDraft]) -> list[EventDraft]:
        """Attach global_person_id to existing event drafts IN PLACE
        where the camera session has a confirmed identity for the
        track. The fence/zone event keeps its type/severity/ladder —
        the identity rides in metadata (backward-compatible: consumers
        that don't know the field simply ignore it)."""
        for d in drafts:
            if d.type not in _ENRICHABLE_TYPES:
                continue
            for tid in d.track_ids:
                ident = self.correlator.identity_for(camera_id, tid)
                if ident is None:
                    continue                    # no identity — no claim
                d.metadata["global_person_id"] = ident.global_person_id
                d.metadata["identity_cameras"] = ident.cameras_visited
                # deterministic movement record from the REAL draft
                if d.type == "ZONE_ENTRY":
                    self.history.note_zone(
                        ident.global_person_id, camera_id, tid,
                        d.zone_id or "", "zone_entry", ctx_ts(d))
                elif d.type == "ZONE_EXIT":
                    self.history.note_zone(
                        ident.global_person_id, camera_id, tid,
                        d.zone_id or "", "zone_exit", ctx_ts(d))
                elif d.type == "LINE_CROSSING":
                    self.history.note_zone(
                        ident.global_person_id, camera_id, tid,
                        d.zone_id or "", "tripwire_crossing", ctx_ts(d))
                break                           # one identity per draft
        return drafts

    # ---- investigation queries (API surface, mandate §10) ----

    def identity_for(self, camera_id: str, track_id: int
                     ) -> Optional[GlobalIdentity]:
        return self.correlator.identity_for(camera_id, track_id)

    def person_summary(self, pid: str) -> Optional[dict]:
        ident = self.correlator.get(pid)
        if ident is None:
            return None
        d = ident.as_dict()
        d["timeline"] = self.history.timeline(pid)
        d["cameras_visited"] = self.history.cameras_visited(pid)
        return d

    def all_persons(self) -> list[dict]:
        return [self.person_summary(i.global_person_id)
                for i in self.correlator.all_identities()]


def ctx_ts(d: EventDraft) -> float:
    """Best-effort wall ts from a draft's metadata (sessions put
    video_ts/tick there; wall ts comes from ctx at commit time, so we
    approximate with video_ts when present — deterministic)."""
    v = d.metadata.get("video_ts")
    return float(v) if v is not None else 0.0
