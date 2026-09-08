"""M1 FileSource tests — real behavior, real files.

Fixtures (tests/assets/, derived read-only via ffmpeg -c copy, origin documented):
  - running_clip.mp4 : first 2s of SIH26/crowd-...-main/assets/running.mp4 (H.264 632x480@30)
  - mov_clip.mov     : first 2s of SIH26/BorderSurvaillance/SentinelVideoDemo/SentinelFinal.mov
                       (HEVC 1920x1080 — genuine MOV, NOT a renamed MP4)
  - not_a_video.mp4  : plain text file with .mp4 extension (invalid-content test)
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from backend.sources import FileSource, SourceError, SourceState

ASSETS = Path(__file__).parent / "assets"
MP4 = ASSETS / "running_clip.mp4"
MOV = ASSETS / "mov_clip.mov"
JUNK = ASSETS / "not_a_video.mp4"


# ---------- valid MP4 ----------

def test_mp4_opens_and_reads_real_frame():
    src = FileSource(MP4)
    src.open()
    assert src.state is SourceState.OPEN
    pkt = src.read()
    assert pkt is not None
    assert isinstance(pkt.frame, np.ndarray)
    assert pkt.frame.dtype == np.uint8
    assert pkt.frame.ndim == 3 and pkt.frame.shape[2] == 3          # BGR HWC
    assert pkt.frame.shape[0] > 0 and pkt.frame.shape[1] > 0        # valid dims
    assert pkt.frame_index == 0
    assert pkt.source_id == "file:running_clip.mp4"
    assert pkt.wall_ts > 0
    assert pkt.video_ts == 0.0                                       # first frame
    src.release()


def test_mp4_frame_index_and_video_ts_increment():
    src = FileSource(MP4)
    src.open()
    fps = src.fps
    assert fps == pytest.approx(30.0, abs=1.0)
    last = None
    for _ in range(30):
        last = src.read()
        assert last is not None
    assert last.frame_index == 29
    if fps:
        assert last.video_ts == pytest.approx(29 / fps, rel=1e-6)
    src.release()


def test_mp4_eof_then_none_forever():
    src = FileSource(MP4)
    src.open()
    n = 0
    while src.read() is not None:
        n += 1
    assert src.state is SourceState.EOF
    assert src.read() is None            # stable EOF, no restart
    assert src.read() is None
    assert n >= 30                        # ~2s @30fps, sanity floor
    src.release()


def test_release_idempotent():
    src = FileSource(MP4)
    src.open()
    src.read()
    src.release()
    src.release()                          # must not crash
    assert src.state is SourceState.RELEASED


def test_context_manager():
    with FileSource(MP4) as src:
        assert src.state is SourceState.OPEN
        assert src.read() is not None
    assert src.state is SourceState.RELEASED


def test_read_before_open_raises():
    with pytest.raises(SourceError):
        FileSource(MP4).read()


# ---------- genuine MOV ----------

def test_genuine_mov_opens_and_reads():
    src = FileSource(MOV)
    src.open()
    assert src.size == (1920, 1080)
    pkt = src.read()
    assert pkt is not None and pkt.frame.shape == (1080, 1920, 3)
    src.release()


# ---------- invalid inputs ----------

def test_missing_path_raises():
    with pytest.raises(SourceError, match="not found"):
        FileSource(ASSETS / "does_not_exist.mp4")


def test_directory_path_raises():
    with pytest.raises(SourceError, match="not a file"):
        FileSource(ASSETS)


def test_non_video_file_raises_on_open():
    with pytest.raises(SourceError, match="no readable frames|cannot open"):
        src = FileSource(JUNK)
        src.open()


def test_empty_video_reports_eof():
    # zero-byte file: cv2 opens but cannot read => SourceError at open
    empty = ASSETS / "empty.mp4"
    empty.write_bytes(b"")
    try:
        with pytest.raises(SourceError):
            FileSource(empty).open()
    finally:
        empty.unlink()
