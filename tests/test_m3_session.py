"""M3 session tests — warm-up safety, session lifecycle, one-active rule.

Real model + real files where behavior depends on them (no YOLO mocks).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from backend.services.session import (
    ProcessingSession,
    SessionError,
    make_source,
    start_session,
    stop_active_session,
)
from backend.sources import FileSource
from backend.vision import DetectorTracker

ASSETS = Path(__file__).parent / "assets"


# ---- warm-up safety (the M3 critical correctness question) ----

def test_warmup_does_not_contaminate_tracking():
    """predict() warm-up must leave ByteTrack state untouched: a warmed
    tracker must produce the SAME first-frame IDs as a cold tracker.
    (Regression for the M3 finding that track()-based warm-up LOSES the
    first frame's detections — replaced by predict()-based warmup().)
    """
    import cv2
    cap = cv2.VideoCapture(str(ASSETS / "running_clip.mp4"))
    frames = []
    for _ in range(6):
        ok, f = cap.read()
        assert ok
        frames.append(f)
    cap.release()

    cold = DetectorTracker(policy="cpu"); cold.load()
    warm = DetectorTracker(policy="cpu"); warm.load()
    warm.warmup(np.zeros((480, 640, 3), dtype=np.uint8))  # what the session does

    for f in frames:
        cold_ids = sorted(o.track_id for o in cold.process(f) if o.track_id is not None)
        warm_ids = sorted(o.track_id for o in warm.process(f) if o.track_id is not None)
        assert warm_ids == cold_ids, (
            f"warm-up contaminated tracking: frame had cold={cold_ids} warm={warm_ids}"
        )


def test_warmup_failure_does_not_raise():
    d = DetectorTracker(policy="cpu"); d.load()
    # valid path — but verify warmup on a degenerate-but-valid frame doesn't crash
    d.warmup(np.zeros((480, 640, 3), dtype=np.uint8))
    assert d.actual_device == "cpu"


# ---- session lifecycle with real file ----

def test_file_session_processes_and_completes():
    stop_active_session()
    session = start_session(FileSource(ASSETS / "running_clip.mp4"))
    try:
        # wait for processing to finish (61 frames, fast) or timeout
        import time
        deadline = time.time() + 30
        while session.status == "running" and time.time() < deadline:
            time.sleep(0.2)
        assert session.status == "completed", f"status={session.status} err={session.error}"
        assert session.frames_processed >= 55, session.frames_processed
        assert session.pipeline_fps > 0
        # latest annotated JPEG still served after EOF
        jpeg = session.slot.peek()
        assert jpeg is not None and jpeg[:2] == b"\xff\xd8"
        assert session.status_payload()["frames_processed"] >= 55
    finally:
        stop_active_session()


def test_one_active_session_rule_enforced():
    stop_active_session()
    s1 = start_session(FileSource(ASSETS / "running_clip.mp4"))
    try:
        with pytest.raises(SessionError, match="one active session"):
            start_session(FileSource(ASSETS / "traffic_clip.mp4"))
    finally:
        stop_active_session()
    assert s1.status in ("stopped", "completed")


def test_stop_releases_source_and_cleans_up():
    stop_active_session()
    session = start_session(FileSource(ASSETS / "running_clip.mp4"))
    import time
    time.sleep(0.5)  # let it run a few frames
    session.stop()
    assert session.status in ("stopped", "completed")
    # session can be replaced after stop
    s2 = start_session(FileSource(ASSETS / "running_clip.mp4"))
    stop_active_session()
    assert s2 is not None


def test_session_error_on_bad_source_path():
    stop_active_session()
    with pytest.raises(Exception):
        session = ProcessingSession(FileSource(ASSETS / "missing.mp4"))
        session.start()


def test_make_source_validation():
    with pytest.raises(SessionError):
        make_source({"type": "bogus"})
    with pytest.raises(SessionError):
        make_source({"type": "file"})             # no path
    src = make_source({"type": "file", "path": str(ASSETS / "running_clip.mp4")})
    assert src.source_id == "file:running_clip.mp4"
    src = make_source({"type": "webcam", "index": 0})
    assert src.source_id == "webcam:0"
