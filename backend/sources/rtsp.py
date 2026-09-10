"""TRINETRA RtspSource — Network RTSP Camera Stream Ingestion (Phase 7).

Behavior:
  - open(uri): opens cv2.VideoCapture(uri, cv2.CAP_FFMPEG) with TCP transport enforced
    via OPENCV_FFMPEG_CAPTURE_OPTIONS='rtsp_transport;tcp' to eliminate UDP packet drops
    and frame corruption.
  - Credential Protection: Sanitizes source_id to strip user:password auth from logs,
    databases, and SSE broadcasts (e.g. rtsp://admin:secret@192.168.1.10:554/live -> rtsp:192.168.1.10:554/live).
  - read(): returns FramePacket | None. Transient failed reads return None (state stays OPEN).
    N (10) consecutive failures transition state to ERROR (triggering session backoff ladder).
  - is_live = True: live timestamps (wall_ts = time.time(), video_ts = None).
  - reopen(): attempts clean reconnection for the ProcessingSession backoff ladder.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

import cv2

from backend.sources.base import FramePacket, SourceError, SourceState, VideoSource

log = logging.getLogger("trinetra.sources.rtsp")

_DISCONNECT_STREAK = 10  # consecutive failed reads => ERROR (trigger reconnect)


class RtspSource(VideoSource):
    is_live = True          # Live network stream
    type_name = "rtsp"      # DB source-type registration

    def __init__(self, uri: str) -> None:
        if not uri or not isinstance(uri, str):
            raise SourceError("RTSP URI cannot be empty")
        raw = uri.strip()
        if not (raw.startswith("rtsp://") or raw.startswith("rtsps://")):
            raise SourceError(f"invalid RTSP URI: {uri!r} (must start with rtsp:// or rtsps://)")
        self._uri = raw
        self._cap: Optional[cv2.VideoCapture] = None
        self._count = -1
        self._state = SourceState.IDLE
        self._fail_streak = 0

        # Sanitize credentials from source_id: rtsp://user:pass@host:port/path -> rtsp:host:port/path
        scheme, rest = raw.split("://", 1)
        if "@" in rest:
            _, _, rest = rest.rpartition("@")
        self.source_id = f"rtsp:{rest}"

    @property
    def state(self) -> SourceState:
        return self._state

    @property
    def uri(self) -> str:
        return self._uri

    @property
    def size(self) -> tuple[int, int]:
        if self._cap is None:
            return (0, 0)
        return (
            int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    def open(self) -> None:
        if self._state == SourceState.OPEN:
            return
        # Force TCP interleaved transport in FFmpeg/OpenCV to eliminate UDP packet loss & tearing
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        try:
            cap = cv2.VideoCapture(self._uri, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                raise SourceError(
                    f"cannot connect to RTSP stream: {self.source_id} "
                    f"(unreachable, invalid stream URL, or authentication failed)"
                )
            self._cap = cap
            self._fail_streak = 0
            self._state = SourceState.OPEN
            log.info("RTSP stream connected: %s", self.source_id)
        except SourceError:
            if "cap" in locals() and cap is not None:
                cap.release()
            raise
        except Exception as e:
            if "cap" in locals() and cap is not None:
                cap.release()
            raise SourceError(f"RTSP stream connection error on {self.source_id}: {e}") from e

    def read(self) -> Optional[FramePacket]:
        if self._cap is None or self._state is not SourceState.OPEN:
            raise SourceError(f"read() before successful open(): {self.source_id}")

        ok, frame = self._cap.read()
        if not ok:
            self._fail_streak += 1
            if self._fail_streak >= _DISCONNECT_STREAK:
                self._state = SourceState.ERROR  # Disconnected / stream lost
                log.warning("RTSP stream read error streak reached limit (%d): %s",
                            _DISCONNECT_STREAK, self.source_id)
            return None
        self._fail_streak = 0
        self._count += 1
        return FramePacket(
            frame=frame,
            wall_ts=time.time(),
            video_ts=None,
            frame_index=self._count,
            source_id=self.source_id,
        )

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._state = SourceState.RELEASED
        log.info("RTSP stream released: %s", self.source_id)

    def reopen(self) -> bool:
        """Attempt fresh reconnection. Returns True on success, False on failure."""
        try:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            self._state = SourceState.IDLE
            self.open()
            return True
        except (SourceError, Exception):
            return False
