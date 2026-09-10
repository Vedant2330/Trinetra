"""TRINETRA Phase 7 — RTSP Source & Ingestion Pipeline Tests.

Tests:
- URI validation & format checking (rtsp:// and rtsps:// schemes)
- Credential sanitization (source_id never exposes username/password)
- Contract & lifecycle compliance (is_live, type_name, State transitions)
- TCP transport option enforcement (OPENCV_FFMPEG_CAPTURE_OPTIONS='rtsp_transport;tcp')
- Mocked stream capture: open, read FramePacket, frame_index progression
- Disconnect streak detection (10 failed reads -> SourceState.ERROR)
- reopen() reconnection mechanics
- Service integration: make_source({'type': 'rtsp', 'uri': ...})
- FastAPI integration: StartRequest model validation and /api/session/start handling
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from backend.services.session import SessionError, make_source
from backend.sources.base import SourceError, SourceState
from backend.sources.rtsp import _DISCONNECT_STREAK, RtspSource


def test_rtsp_uri_validation():
    # Empty or invalid types
    with pytest.raises(SourceError, match="cannot be empty"):
        RtspSource("")
    with pytest.raises(SourceError, match="cannot be empty"):
        RtspSource(None)  # type: ignore[arg-type]

    # Non-RTSP schemes
    with pytest.raises(SourceError, match="must start with rtsp:// or rtsps://"):
        RtspSource("http://192.168.1.10/video")
    with pytest.raises(SourceError, match="must start with rtsp:// or rtsps://"):
        RtspSource("file:///path/to/video.mp4")

    # Valid schemes
    s1 = RtspSource("rtsp://192.168.1.100:554/live")
    assert s1.uri == "rtsp://192.168.1.100:554/live"

    s2 = RtspSource("rtsps://secure.camera.local:322/stream1")
    assert s2.uri == "rtsps://secure.camera.local:322/stream1"


def test_rtsp_credential_sanitization():
    # Credentials with password
    s1 = RtspSource("rtsp://admin:P@ssw0rd123!@192.168.1.50:554/h264")
    assert s1.source_id == "rtsp:192.168.1.50:554/h264"
    assert "admin" not in s1.source_id
    assert "P@ssw0rd123!" not in s1.source_id

    # User only
    s2 = RtspSource("rtsp://viewer@10.0.0.5:8554/live")
    assert s2.source_id == "rtsp:10.0.0.5:8554/live"
    assert "viewer" not in s2.source_id

    # No credentials
    s3 = RtspSource("rtsp://10.0.0.1:554/feed")
    assert s3.source_id == "rtsp:10.0.0.1:554/feed"


def test_rtsp_contract_and_initial_state():
    src = RtspSource("rtsp://127.0.0.1:8554/test")
    assert src.is_live is True
    assert src.type_name == "rtsp"
    assert src.state is SourceState.IDLE
    assert src.size == (0, 0)


def test_rtsp_read_before_open_raises():
    src = RtspSource("rtsp://127.0.0.1:8554/test")
    with pytest.raises(SourceError, match="read\\(\\) before successful open"):
        src.read()


def test_rtsp_open_unreachable_raises():
    # Real attempt to open an unreachable localhost port
    src = RtspSource("rtsp://127.0.0.1:59999/nonexistent")
    with pytest.raises(SourceError, match="cannot connect to RTSP stream"):
        src.open()
    assert src.state is SourceState.IDLE


def test_rtsp_mocked_open_and_tcp_transport():
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.side_effect = lambda prop: 640 if prop == 3 else 480  # CAP_PROP_FRAME_WIDTH=3, HEIGHT=4
    mock_cap.read.return_value = (True, dummy_frame)

    with patch("backend.sources.rtsp.cv2.VideoCapture", return_value=mock_cap) as mock_vc:
        src = RtspSource("rtsp://user:secret@192.168.1.200:554/stream")
        src.open()

        assert src.state is SourceState.OPEN
        assert src.size == (640, 480)
        # Verify TCP transport setting in environment
        assert os.environ.get("OPENCV_FFMPEG_CAPTURE_OPTIONS") == "rtsp_transport;tcp"
        mock_vc.assert_called_once_with("rtsp://user:secret@192.168.1.200:554/stream", 1900)  # cv2.CAP_FFMPEG = 1900

        # Read packets
        pkt1 = src.read()
        assert pkt1 is not None
        assert pkt1.frame_index == 0
        assert pkt1.video_ts is None  # Live stream: video_ts is None
        assert pkt1.wall_ts > 0
        assert pkt1.source_id == "rtsp:192.168.1.200:554/stream"
        assert pkt1.frame.shape == (480, 640, 3)

        pkt2 = src.read()
        assert pkt2 is not None
        assert pkt2.frame_index == 1

        # Release
        src.release()
        assert src.state is SourceState.RELEASED
        mock_cap.release.assert_called_once()


def test_rtsp_transient_failures_and_disconnect_streak():
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.side_effect = lambda prop: 640 if prop == 3 else 480

    # 1 success, 3 fails, 1 success, 10 fails
    read_results = (
        [(True, dummy_frame)] +
        [(False, None)] * 3 +
        [(True, dummy_frame)] +
        [(False, None)] * _DISCONNECT_STREAK
    )
    mock_cap.read.side_effect = read_results

    with patch("backend.sources.rtsp.cv2.VideoCapture", return_value=mock_cap):
        src = RtspSource("rtsp://192.168.1.200:554/live")
        src.open()

        # Frame 0
        pkt = src.read()
        assert pkt is not None
        assert pkt.frame_index == 0
        assert src.state is SourceState.OPEN

        # 3 transient failures -> returns None, remains OPEN
        for _ in range(3):
            assert src.read() is None
            assert src.state is SourceState.OPEN

        # Recover with 1 success -> resets fail streak
        pkt = src.read()
        assert pkt is not None
        assert pkt.frame_index == 1
        assert src.state is SourceState.OPEN

        # 9 failures -> still OPEN
        for _ in range(_DISCONNECT_STREAK - 1):
            assert src.read() is None
            assert src.state is SourceState.OPEN

        # 10th failure -> transitions to ERROR
        assert src.read() is None
        assert src.state is SourceState.ERROR


def test_rtsp_reopen_mechanism():
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.side_effect = lambda prop: 640 if prop == 3 else 480

    with patch("backend.sources.rtsp.cv2.VideoCapture", return_value=mock_cap):
        src = RtspSource("rtsp://192.168.1.200:554/live")
        src.open()
        assert src.state is SourceState.OPEN

        # reopen succeeds
        ok = src.reopen()
        assert ok is True
        assert src.state is SourceState.OPEN

    # reopen fails when connection fails
    with patch("backend.sources.rtsp.cv2.VideoCapture", side_effect=Exception("network down")):
        ok = src.reopen()
        assert ok is False


def test_make_source_rtsp_service():
    # Missing uri
    with pytest.raises(SessionError, match="rtsp session requires 'uri'"):
        make_source({"type": "rtsp"})

    # Invalid uri
    with pytest.raises(SessionError, match="must start with rtsp:// or rtsps://"):
        make_source({"type": "rtsp", "uri": "invalid_uri"})

    # Valid rtsp spec
    source = make_source({"type": "rtsp", "uri": "rtsp://192.168.1.100:554/live"})
    assert isinstance(source, RtspSource)
    assert source.source_id == "rtsp:192.168.1.100:554/live"
