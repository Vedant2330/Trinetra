"""TRINETRA Phase 3: YuNet Face Detection Lifecycle Tests.

Validates:
- Honest availability gate (missing file -> False, no crash).
- Dynamic setInputSize synchronization across dynamic resolutions.
- Person bbox height >= 80px gating.
- 5s per-track event generation cooldown.
- Server-side annotation overlay with layers['faces'] toggle (default OFF).
- FACE_DETECTED event severity and night/RESTRICTED zone escalation.
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from backend.analytics.base import EventDraft, FrameContext
from backend.core.config import MODELS_DIR
from backend.events.engine import EventEngine
from backend.state.tracks import TrackState
from backend.vision import FaceDetection, YuNetFaceDetector
from backend.vision.annotation import annotate


def test_yunet_model_availability():
    """YuNet detector reports available=True when yunet.onnx is present."""
    detector = YuNetFaceDetector()
    model_file = MODELS_DIR / "yunet.onnx"
    if model_file.exists():
        assert detector.available is True
    else:
        assert detector.available is False


def test_yunet_honest_unavailable_on_missing_file(tmp_path: Path):
    """Missing model path degrades to available=False and returns empty detections."""
    detector = YuNetFaceDetector(model_path=tmp_path / "nonexistent.onnx")
    assert detector.available is False
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    assert detector.detect(frame) == []
    faces, drafts = detector.detect_in_person_tracks(frame, [], wall_ts=100.0)
    assert faces == []
    assert drafts == []


def test_yunet_dynamic_input_size_sync():
    """Dynamic resolution input syncs setInputSize((w, h)) without OpenCV assertions."""
    detector = YuNetFaceDetector()
    if not detector.available:
        pytest.skip("yunet.onnx not present")

    resolutions = [(320, 240), (640, 480), (1280, 720), (800, 600)]
    for w, h in resolutions:
        frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)
        res = detector.detect(frame)
        assert isinstance(res, list)
        assert detector._current_input_size == (w, h)


def _person_track(track_id: int, bbox: list[float]) -> "TrackState":
    """Real TrackState — the type session.detect_in_person_tracks
    actually receives (store active_tracks). Its __slots__ expose
    last_bbox ONLY; mock objects with .bbox diverge from the real
    contract and hide wiring bugs (oscar blocker 1)."""
    return TrackState(
        track_id=track_id, class_id=0, class_name="person",
        tick=1, wall_ts=100.0, bbox=bbox, confidence=0.9,
    )


def _track(track_id: int, class_name: str, bbox: list[float]) -> "TrackState":
    return TrackState(
        track_id=track_id, class_id=2, class_name=class_name,
        tick=1, wall_ts=100.0, bbox=bbox, confidence=0.9,
    )


def test_detect_in_person_tracks_gating():
    """Height < 80px or non-person tracks are skipped; >= 80px person processed."""
    detector = YuNetFaceDetector()
    if not detector.available:
        pytest.skip("yunet.onnx not present")

    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    # 1. Person with height 50px (< 80px) -> skipped
    short_person = _track(1, "person", [100, 100, 140, 150])  # h = 50
    faces, drafts = detector.detect_in_person_tracks(frame, [short_person], wall_ts=100.0)
    assert faces == []
    assert drafts == []

    # 2. Car with height 200px -> skipped (class != person)
    car = _track(2, "car", [200, 200, 400, 400])  # h = 200
    faces, drafts = detector.detect_in_person_tracks(frame, [car], wall_ts=100.0)
    assert faces == []
    assert drafts == []

    # 3. Person with height 150px (>= 80px) -> evaluated
    tall_person = _track(3, "person", [50, 50, 150, 200])  # h = 150
    faces, drafts = detector.detect_in_person_tracks(frame, [tall_person], wall_ts=100.0)
    assert isinstance(faces, list)
    assert isinstance(drafts, list)


def test_face_composition_real_trackstate():
    """COMPOSITION (must-fail on pre-fix wiring): session passes
    TrackState objects whose __slots__ expose last_bbox ONLY. The
    pre-fix code read .bbox -> None -> every real track skipped, no
    face ever detected on the product path.

    Observable seam: when a track's bbox IS read, detect() runs on the
    person crop and syncs _current_input_size to the CROP dimensions.
    Pre-fix (bbox=None -> continue) the crop is never taken and the
    input size stays at the load default (320, 320) / previous value."""
    detector = YuNetFaceDetector()
    if not detector.available:
        pytest.skip("yunet.onnx not present")

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    person = _person_track(7, [150, 30, 280, 300])   # crop = 130 x 270

    faces, drafts = detector.detect_in_person_tracks(frame, [person], wall_ts=100.0)

    # Crop dimensions for bbox [150, 30, 280, 300]: w=130, h=270.
    # detect() was invoked on the crop -> input size synced to (130, 270).
    assert detector._current_input_size == (130, 270), (
        f"person crop never taken (input size {detector._current_input_size}) — "
        "TrackState.last_bbox was not read"
    )


def test_detect_in_person_tracks_cooldown():
    """5.0s cooldown per track for event generation."""
    detector = YuNetFaceDetector()
    # Mock internal detect() to return a synthetic FaceDetection
    fake_face = FaceDetection(
        bbox=[10, 10, 40, 40],
        score=0.95,
        landmarks=[[15, 20], [35, 20], [25, 30], [20, 40], [30, 40]],
    )
    detector._detector = True  # force available
    detector.detect = lambda crop, track_id=None: [fake_face]

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    person = _person_track(42, [50, 50, 200, 300])  # h = 250

    # First detection at t=100.0 -> event emitted
    faces1, drafts1 = detector.detect_in_person_tracks(frame, [person], wall_ts=100.0)
    assert len(faces1) == 1
    assert len(drafts1) == 1
    assert drafts1[0]["track_id"] == 42
    assert drafts1[0]["confidence"] == 0.95

    # Second detection at t=104.9 (< 5.0s) -> face detected, but event suppressed
    faces2, drafts2 = detector.detect_in_person_tracks(frame, [person], wall_ts=104.9)
    assert len(faces2) == 1
    assert len(drafts2) == 0

    # Third detection at t=105.0 (>= 5.0s) -> event emitted
    faces3, drafts3 = detector.detect_in_person_tracks(frame, [person], wall_ts=105.0)
    assert len(faces3) == 1
    assert len(drafts3) == 1
    assert drafts3[0]["track_id"] == 42


def test_annotation_face_layer_toggle():
    """Annotation handles faces layer toggle (default OFF)."""
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    face = FaceDetection(
        bbox=[100, 100, 80, 80],
        score=0.92,
        landmarks=[[120, 120], [160, 120], [140, 140], [130, 160], [150, 160]],
        track_id=1,
    )

    # 1. Default layers -> faces OFF (frame unchanged from empty)
    out_default = annotate(frame, [], faces=[face])
    assert np.array_equal(out_default, frame)

    # 2. Explicit faces=False -> faces OFF
    out_off = annotate(frame, [], layers={"faces": False}, faces=[face])
    assert np.array_equal(out_off, frame)

    # 3. Explicit faces=True -> overlay drawn (frame modified)
    out_on = annotate(frame, [], layers={"faces": True}, faces=[face])
    assert not np.array_equal(out_on, frame)
    # Ensure drawing happened around bbox
    assert out_on[100, 100:180].sum() > 0


def test_face_event_severity_and_escalation():
    """FACE_DETECTED base severity is LOW; escalates on RESTRICTED zone and night."""
    eng = EventEngine("source-1", "sess-1")
    base_ctx = FrameContext(tick=0, wall_ts=1000.0, video_ts=0.0, luminance=128.0, is_night=False, shape=(640, 480))
    night_ctx = FrameContext(tick=0, wall_ts=1000.0, video_ts=0.0, luminance=20.0, is_night=True, shape=(640, 480))

    # Base: LOW
    d_base = EventDraft(type="FACE_DETECTED", track_ids=[1], zone_id=None, direction=None, confidence=0.9, metadata={"is_night": False})
    ev_base = eng.commit([d_base], None, base_ctx)
    assert len(ev_base) == 1
    assert ev_base[0].severity == "LOW"

    eng.reset("sess-2")
    # RESTRICTED zone: MEDIUM
    d_res = EventDraft(type="FACE_DETECTED", track_ids=[2], zone_id="z1", direction=None, confidence=0.9, metadata={"is_night": False, "zone_type": "RESTRICTED"})
    ev_res = eng.commit([d_res], None, base_ctx)
    assert len(ev_res) == 1
    assert ev_res[0].severity == "MEDIUM"

    eng.reset("sess-3")
    # Night: MEDIUM
    d_night = EventDraft(type="FACE_DETECTED", track_ids=[3], zone_id=None, direction=None, confidence=0.9, metadata={"is_night": True})
    ev_night = eng.commit([d_night], None, night_ctx)
    assert len(ev_night) == 1
    assert ev_night[0].severity == "MEDIUM"

    eng.reset("sess-4")
    # RESTRICTED zone + Night: HIGH
    d_both = EventDraft(type="FACE_DETECTED", track_ids=[4], zone_id="z1", direction=None, confidence=0.9, metadata={"is_night": True, "zone_type": "RESTRICTED"})
    ev_both = eng.commit([d_both], None, night_ctx)
    assert len(ev_both) == 1
    assert ev_both[0].severity == "HIGH"
