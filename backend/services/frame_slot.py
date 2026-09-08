"""TRINETRA latest-frame slot — single-slot latest-JPEG sharing (M3).

Writer (processing thread): publish(bytes) — replaces the one slot.
Readers (MJPEG endpoint / frame.jpg): wait(t) blocks until a NEW frame is
published, returns bytes and clears the slot. If a reader is slow it simply
lags behind (frames are skipped, never queued) — bounded memory by design.
No queues, no history, no per-client state.
"""

from __future__ import annotations

import threading
from typing import Optional


class LatestFrameSlot:
    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._frame: Optional[bytes] = None

    def publish(self, jpeg: bytes) -> None:
        with self._cond:
            self._frame = jpeg
            self._cond.notify_all()

    def wait_new(self, timeout: float) -> Optional[bytes]:
        """Wait for an unpublished frame. Returns bytes (slot consumed) or None on timeout."""
        with self._cond:
            if self._frame is None:
                self._cond.wait(timeout)
            if self._frame is None:
                return None
            f = self._frame
            self._frame = None
            return f

    def peek(self) -> Optional[bytes]:
        """Non-consuming read of the latest frame (for frame.jpg)."""
        with self._cond:
            return self._frame
