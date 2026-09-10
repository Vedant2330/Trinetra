"""TRINETRA WebcamSource — macOS AVFoundation camera via OpenCV.

Behavior:
  - open(index): opens cv2.VideoCapture(index, CAP_AVFUNDATION). Failure to
    open => SourceError (unavailable device / permission denied / bad index).
  - read(): returns FramePacket | None. A transient failed read returns None
    (state stays OPEN — single dropped frames happen). N consecutive failures
    => state=ERROR (camera disconnected). video_ts is None (live source).
  - macOS permission denial surfaces as open failure; the OS prompt appears
    once on first use. No fake frames, ever.
  - Enumeration: probe_webcams() — bounded open/grab/release probe of
    indices 0..2. macOS enumeration via OpenCV is unreliable (no clean
    device API); we report only what actually opens. Honest, not robust.
"""

from __future__ import annotations

import time
from typing import Optional

import cv2

from backend.sources.base import FramePacket, SourceError, SourceState, VideoSource

_DISCONNECT_STREAK = 10  # consecutive failed reads => ERROR (disconnect)


class WebcamSource(VideoSource):
    is_live = True          # C2: live-source flag (files: False)
    type_name = "webcam"    # §2.9: DB source-type registration

    def __init__(self, index: int = 0) -> None:
        if index < 0:
            raise SourceError(f"invalid camera index: {index}")
        self._index = index
        self._cap: Optional[cv2.VideoCapture] = None
        self._count = -1  # frames returned so far
        self._state = SourceState.IDLE
        self._fail_streak = 0
        self.source_id = f"webcam:{index}"

    @property
    def state(self) -> SourceState:
        return self._state

    @property
    def size(self) -> tuple[int, int]:
        if self._cap is None:
            return (0, 0)
        return (int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))

    def open(self) -> None:
        if self._state == SourceState.OPEN:
            return
        cap = cv2.VideoCapture(self._index, cv2.CAP_AVFOUNDATION)
        try:
            if not cap.isOpened():
                raise SourceError(
                    f"cannot open camera {self._index} "
                    f"(unavailable, in use, or permission denied)"
                )
            ok, _ = cap.read()
            if not ok:
                raise SourceError(f"camera {self._index} opened but returned no frame")
            self._cap = cap
            self._fail_streak = 0
            self._state = SourceState.OPEN
        except SourceError:
            cap.release()
            raise

    def read(self) -> Optional[FramePacket]:
        if self._cap is None or self._state is not SourceState.OPEN:
            raise SourceError(f"read() before successful open(): {self.source_id}")

        ok, frame = self._cap.read()
        if not ok:
            self._fail_streak += 1
            if self._fail_streak >= _DISCONNECT_STREAK:
                self._state = SourceState.ERROR  # disconnected
            return None
        self._fail_streak = 0
        self._count += 1
        return FramePacket(
            frame=frame,
            wall_ts=time.time(),      # wall-clock capture time (live source)
            video_ts=None,             # no stream-relative time exists
            frame_index=self._count,
            source_id=self.source_id,
        )

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._state = SourceState.RELEASED

    def reopen(self) -> bool:
        """C2: attempt a fresh open (release + open). Returns True when the
        camera came back. The SESSION owns the backoff ladder; the SOURCE
        only owns the mechanics of trying again. Raises nothing — the
        caller decides what a failed attempt means."""
        try:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            self._state = SourceState.IDLE
            self.open()
            return True
        except SourceError:
            return False


def probe_webcams(max_index: int = 2) -> list[int]:
    """Bounded probe: return indices that open AND deliver a frame.

    macOS has no reliable OpenCV enumeration API — this is deliberately a
    simple try-open probe, not a device-discovery system.
    """
    working: list[int] = []
    for i in range(max_index + 1):
        try:
            with WebcamSource(i) as src:
                if src.read() is not None:
                    working.append(i)
        except SourceError:
            continue
    return working
