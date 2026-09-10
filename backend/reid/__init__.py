"""TRINETRA cross-camera identity — global person IDs over local tracks (M8).

Architecture (human mandate, M8):

    YOLO -> ByteTrack -> TrackStore (per camera, LOCAL ids)
                          |
                    selective Re-ID
                    (sampling policy; embedder)
                          v
                 IdentityObservation
                    (camera_id, track_id, embedding)
                          v
                GlobalIdentityCorrelator
                    (gallery + matcher + rules)
                          v
                 GlobalIdentity P-0001...
                          v
        fence/zone events enriched with global_person_id
        + PERSON_IDENTITY_MATCHED / PERSON_CAMERA_TRANSITION drafts
        + global movement history + investigation summary

HARD RULES (no-fake-identity, mandate §4):
  - ByteTrack ids are CAMERA/SESSION-LOCAL. Global ids exist ONLY via
    Re-ID correlation. Never merge on "both person" / "close in time" /
    "spatially near" alone.
  - Every association carries an explicit MatchState: CANDIDATE (below
    the confirm threshold but above candidate threshold) or CONFIRMED
    (similarity >= confirm AND constraints pass). UNMATCHED otherwise.
  - No embedding -> no identity claim, ever (tests pin this).

Re-ID is NOT a second tracker: local tracking authority stays with
ByteTrack/TrackStore; this package only observes and correlates.

Thread model: a correlator may receive observations from several camera
session threads; the gallery is guarded by one lock (bounded contention,
no extra threads/processes created here).
"""

from backend.reid.identity import (
    GlobalIdentity,
    IdentityObservation,
    MatchState,
    MovementPoint,
)
from backend.reid.gallery import IdentityGallery
from backend.reid.matcher import Matcher, MatchResult, MatcherPolicy
from backend.reid.embedder import (
    DummyEmbedder,
    OpenCVDnnEmbedder,
    ReIDEmbedder,
    TorchScriptEmbedder,
    preprocess_crop,
)
from backend.reid.correlation import (
    CorrelationOutcome,
    GlobalIdentityCorrelator,
)
from backend.reid.sampling import ReIDSamplingPolicy, SamplePolicy
from backend.reid.history import GlobalMovementHistory
from backend.reid.summary import ClipSummary, build_clip_summary
from backend.reid.integration import (
    CameraReIdSession,
    MultiCameraReIdService,
    make_embedder,
)

__all__ = [
    "GlobalIdentity",
    "IdentityObservation",
    "MatchState",
    "MovementPoint",
    "IdentityGallery",
    "Matcher",
    "MatchResult",
    "MatcherPolicy",
    "ReIDEmbedder",
    "TorchScriptEmbedder",
    "OpenCVDnnEmbedder",
    "DummyEmbedder",
    "preprocess_crop",
    "CorrelationOutcome",
    "GlobalIdentityCorrelator",
    "ReIDSamplingPolicy",
    "SamplePolicy",
    "GlobalMovementHistory",
    "HistoryEvent",
    "ClipSummary",
    "build_clip_summary",
    "CameraReIdSession",
    "MultiCameraReIdService",
    "make_embedder",
]
