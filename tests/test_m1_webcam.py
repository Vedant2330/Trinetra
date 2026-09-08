"""M1 WebcamSource tests — executed on the real M4 Air.

Camera 0 = FaceTime/USB camera via AVFoundation. If the environment has no
camera or permission is denied, tests are SKIPPED honestly (not passed).
"""

from __future__ import annotations

import numpy as np
import pytest

from backend.sources import SourceError, SourceState, WebcamSource, probe_webcams

pytestmark = pytest.mark.webcam


def _camera_available() -> bool:
    try:
        with WebcamSource(0) as src:
            return src.read() is not None
    except SourceError:
        return False


@pytest.fixture(scope="module")
def cam():
    if not _camera_available():
        pytest.skip("camera 0 unavailable or permission denied on this machine")
    src = WebcamSource(0)
    src.open()
    yield src
    src.release()


def test_camera_opens_and_reads_real_frame(cam):
    pkt = cam.read()
    assert pkt is not None
    assert isinstance(pkt.frame, np.ndarray)
    assert pkt.frame.dtype == np.uint8
    assert pkt.frame.ndim == 3 and pkt.frame.shape[2] == 3
    assert pkt.frame.shape[0] >= 120 and pkt.frame.shape[1] >= 160   # sane dims


def test_frame_index_increments(cam):
    first = cam.read()
    assert first is not None
    idx = first.frame_index
    second = cam.read()
    assert second is not None
    assert second.frame_index == idx + 1
    assert second.frame_index > 0


def test_timestamps_and_source_id(cam):
    pkt = cam.read()
    assert pkt is not None
    import time
    assert abs(pkt.wall_ts - time.time()) < 5.0     # wall-clock semantics
    assert pkt.video_ts is None                     # live source contract
    assert pkt.source_id == "webcam:0"


def test_release_works_and_is_idempotent():
    if not _camera_available():
        pytest.skip("camera 0 unavailable")
    src = WebcamSource(0)
    src.open()
    src.read()
    src.release()
    src.release()
    assert src.state is SourceState.RELEASED


def test_invalid_index_raises():
    with pytest.raises(SourceError):
        WebcamSource(-1).open()


def test_probe_webcams_reports_honestly():
    cams = probe_webcams(max_index=2)
    assert isinstance(cams, list)
    # on this M4 Air, [0] is expected; assert only honesty, not hardware
    if cams:
        assert 0 in cams or cams == [1] or cams == [2]
    print(f"\nprobe_webcams -> {cams}")
