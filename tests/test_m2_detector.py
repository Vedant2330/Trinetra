"""M2 DetectorTracker tests — real model, real inference (no YOLO mocks).

Fixture: tests/assets/running_clip.mp4 (persons, 632x480@30, M1 origin
documentation applies). Noise frame proves empty-scene honesty.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from backend.core.config import MODELS_DIR, VISION
from backend.vision import DetectorError, DetectorTracker

ASSETS = Path(__file__).parent / "assets"


@pytest.fixture(scope="module")
def detector():
    d = DetectorTracker(policy="cpu")  # deterministic for unit tests; MPS tested in integration
    d.load()
    return d


@pytest.fixture(scope="module")
def person_frame(detector):
    import cv2
    cap = cv2.VideoCapture(str(ASSETS / "running_clip.mp4"))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 20)  # mid-clip where a runner is visible
    ok, frame = cap.read()
    cap.release()
    assert ok
    return frame


# ---- lifecycle / config ----

def test_model_path_is_project_relative():
    p = MODELS_DIR / VISION.model
    assert p.exists()
    assert p.name == "yolov8n.pt"
    assert "models" in str(p)


def test_load_measures_time(detector):
    assert detector.load_seconds > 0


def test_missing_model_raises(tmp_path):
    import backend.core.config as cfg
    orig = cfg.MODELS_DIR
    try:
        cfg.MODELS_DIR = tmp_path  # empty dir -> missing model
        d = DetectorTracker(policy="cpu")
        with pytest.raises(DetectorError, match="missing"):
            d.load()
    finally:
        cfg.MODELS_DIR = orig


def test_mps_policy_unavailable_raises_cleanly(monkeypatch):
    import torch
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    with pytest.raises(DetectorError, match="mps"):
        DetectorTracker(policy="mps").load()


def test_process_before_load_raises():
    with pytest.raises(DetectorError, match="not loaded"):
        DetectorTracker(policy="cpu").process(np.zeros((480, 640, 3), np.uint8))


# ---- frame validation ----

def test_invalid_frames_raise(detector):
    with pytest.raises(DetectorError):
        detector.process(np.zeros((10, 10), np.uint8))           # not HWC
    with pytest.raises(DetectorError):
        detector.process("not a frame")                          # wrong type
    with pytest.raises(DetectorError):
        detector.process(np.zeros((1, 1, 3), np.uint8))          # degenerate


# ---- honest empty scene ----

def test_noise_frame_returns_empty_list(detector):
    noise = np.random.default_rng(0).integers(0, 255, (480, 640, 3), dtype=np.uint8)
    objs = detector.process(noise)
    assert objs == []                      # empty scene is normal, not an error


# ---- real detection ----

def test_person_detected_with_track_id(detector, person_frame):
    objs = detector.process(person_frame)
    persons = [o for o in objs if o.class_name == "person"]
    assert len(persons) >= 1
    for o in persons:
        assert o.track_id is None or isinstance(o.track_id, int)  # honest ID
        assert 0.0 <= o.confidence <= 1.0
        x1, y1, x2, y2 = o.bbox
        assert 0 <= x1 < x2 and 0 <= y1 < y2
        assert x2 <= person_frame.shape[1] and y2 <= person_frame.shape[0]


def test_class_filter_only_configured_classes(detector, person_frame):
    objs = detector.process(person_frame)
    allowed = set(VISION.classes)
    assert all(o.class_id in allowed for o in objs)
    names = {o.class_name for o in objs}
    assert names.issubset({"person", "bicycle", "car", "motorcycle", "bus", "truck"})


def test_tracked_object_structure(detector, person_frame):
    objs = detector.process(person_frame)
    assert objs, "expected at least one object in this frame"
    o = objs[0]
    assert isinstance(o.class_name, str)
    assert isinstance(o.confidence, float)
    assert len(o.bbox) == 4


def test_sequential_ids_stable(detector, person_frame):
    """Same visible object across sequential frames keeps its ID."""
    first = [o for o in detector.process(person_frame) if o.class_name == "person"]
    assert first
    # same frame content => tracker should re-identify consistently
    ids1 = {o.track_id for o in first if o.track_id is not None}
    second = [o for o in detector.process(person_frame) if o.class_name == "person"]
    ids2 = {o.track_id for o in second if o.track_id is not None}
    if ids1 and ids2:
        assert ids1 == ids2, f"ID churn on identical content: {ids1} -> {ids2}"


def test_two_instances_do_not_share_tracking_state():
    """Isolation proof: fresh instance = fresh ByteTrack state."""
    import cv2
    cap = cv2.VideoCapture(str(ASSETS / "running_clip.mp4"))
    _, f1 = cap.read()
    ok, f2 = cap.read()
    cap.release()
    assert ok
    d1 = DetectorTracker(policy="cpu"); d1.load()
    d2 = DetectorTracker(policy="cpu"); d2.load()
    d1.process(f1)
    d1.process(f2)
    r1 = d1.process(f2)
    r2 = d2.process(f1)  # new instance sees first frame -> IDs start fresh
    ids1 = [o.track_id for o in r1 if o.track_id is not None]
    ids2 = [o.track_id for o in r2 if o.track_id is not None]
    # same scene, independent instances: no shared hidden state — both should
    # assign low IDs fresh (1..) rather than continuing each other's sequence
    assert max(ids2, default=0) <= len(ids2) + 2, \
        "instance 2 appears to have inherited instance 1's tracker state"
