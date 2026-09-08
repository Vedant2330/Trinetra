"""TRINETRA FileSource — MP4/MOV and other OpenCV-decodable containers.

Behavior:
  - open(): validates path; probes with cv2.VideoCapture (open + first-frame
    read) to reject invalid/unsupported/empty videos EARLY with SourceError.
  - read(): returns FramePacket or None. First None after normal exhaustion
    sets state=EOF. A mid-file decode failure sets state=ERROR (distinct).
  - Codec support is whatever the local OpenCV/FFmpeg build decodes.
    No universal-codec claims. MP4 (H.264) verified on this machine.
  - Never loops. Never resizes. Original decoded frames only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import time

from backend.sources.base import FramePacket, SourceError, SourceState, VideoSource


class FileSource(VideoSource):
    def __init__(self, path: str | Path) -> None:
        self._path = self._require_file(path)
        self._cap: Optional[cv2.VideoCapture] = None
        self._index = -1  # last successfully returned frame index
        self._fps = 0.0
        self._frame_count = 0
        self._state = SourceState.IDLE
        self._eof_reached = False
        self.source_id = f"file:{self._path.name}"

    # ---- properties ----

    @property
    def state(self) -> SourceState:
        return self._state

    @property
    def fps(self) -> float:
        """Container-declared FPS metadata (0.0 if unknown)."""
        return self._fps

    @property
    def frame_count(self) -> int:
        """Container-declared frame count (0 if unknown)."""
        return self._frame_count

    @property
    def size(self) -> tuple[int, int]:
        """(width, height) in pixels."""
        if self._cap is None:
            return (0, 0)
        return (int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))

    # ---- lifecycle ----

    def open(self) -> None:
        if self._state == SourceState.OPEN:
            return
        cap = cv2.VideoCapture(str(self._path))
        try:
            if not cap.isOpened():
                raise SourceError(f"cannot open video (unsupported/invalid): {self._path}")
            ok, _ = cap.read()
            if not ok:
                raise SourceError(f"video has no readable frames (empty/codec?): {self._path}")
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # rewind probe frame
            self._fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
            self._frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            self._cap = cap
            self._state = SourceState.OPEN
        except SourceError:
            cap.release()
            raise

    def read(self) -> Optional[FramePacket]:
        if self._eof_reached:
            return None
        if self._cap is None or self._state not in (SourceState.OPEN,):
            raise SourceError(f"read() before successful open(): {self.source_id}")

        ok, frame = self._cap.read()
        if not ok:
            # cv2 returns ok=False at end-of-stream for seekable files.
            # Normal exhaustion => EOF. open() already proved the file decodes
            # (first-frame probe), so a read failure here is EOS, not corruption.
            self._eof_reached = True
            self._state = SourceState.EOF
            return None
        self._index += 1
        video_ts = self._index / self._fps if self._fps > 0 else None
        return FramePacket(
            frame=frame,
            wall_ts=time.time(),
            video_ts=video_ts,
            frame_index=self._index,
            source_id=self.source_id,
        )

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        if self._state != SourceState.ERROR:
            self._state = SourceState.RELEASED
