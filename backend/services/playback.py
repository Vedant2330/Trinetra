"""TRINETRA playback/inference decoupling — shared handoff (media-clock
playback, independent inference).

Mandate: playback speed is NEVER limited by inference speed.

Two participants:

  DisplayLoop (media clock)
    reads frames from the source, paces presentation by
    wall_start + frame_index / (src_fps * speed), publishes the
    ANNOTATED JPEG to LatestFrameSlot at SOURCE rate. When fresh
    inference results exist (bounded staleness) they are drawn on the
    CURRENT frame; otherwise the clean frame is displayed (never
    frozen waiting for the detector).

  InferenceLoop (independent consumer)
    samples the LATEST unread frame (no queue, no backlog — stale
    frames are skipped by design), runs detection+tracking+analytics,
    and posts an OverlayResult for the display loop.

Shared structures in this module:

  FrameHandoff  — single-slot latest-frame mailbox (display -> inference)
  OverlayResult — one inference result bound to its source frame metadata
  OverlayBoard  — single-slot latest-overlay board (inference -> display)

Thread-safety: each structure is one slot guarded by a lock/condition
(bounded memory by design — same discipline as LatestFrameSlot).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


class FrameHandoff:
    """Single-slot latest-frame mailbox (display -> inference).

    The display loop OFFERS every frame; the inference loop takes the
    LATEST one (older frames are simply overwritten — the bounded-memory
    latest-frame sampling the mandate requires). `take()` returns None
    when nothing new arrived since the last take (inference simply
    waits on the condition).
    """

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._frame: Optional[np.ndarray] = None
        self._meta: Optional[dict] = None
        self._pending = 0            # frames offered minus taken (capped 1)
        self._closed = False

    def offer(self, frame: np.ndarray, meta: dict) -> None:
        """Display offers the CURRENT frame (replaces any untaken one)."""
        with self._cond:
            if self._closed:
                return
            self._frame = frame
            self._meta = meta
            self._pending = 1
            self._cond.notify_all()

    def take(self, timeout: float = 0.05) -> Optional[tuple[np.ndarray, dict]]:
        """Inference takes the LATEST offered frame (or None on timeout).
        Short default timeout keeps the session-shutdown join fast;
        returns None immediately once closed."""
        with self._cond:
            if self._closed:
                return None
            if self._pending == 0:
                self._cond.wait(timeout)
                if self._closed or self._pending == 0:
                    return None
            if self._pending == 0 or self._frame is None:
                return None
            f, m = self._frame, self._meta
            self._frame = None
            self._meta = None
            self._pending = 0
            return f, m

    def close(self) -> None:
        """Mark closed: parked takers wake immediately (session end)."""
        with self._cond:
            self._closed = True
            self._frame = None
            self._meta = None
            self._pending = 0
            self._cond.notify_all()

    def clear(self) -> None:
        """Drop any stashed frame (seek)."""
        with self._cond:
            self._frame = None
            self._meta = None
            self._pending = 0


@dataclass
class OverlayResult:
    """One inference result bound to the analyzed frame's metadata.

    `objects` are TrackedObject instances at the analyzed frame's
    coordinate space; trajectories/faces/poses are computed IN the
    inference thread (never by iterating live state cross-thread) and
    carried here for the display loop to draw.
    """

    objects: list = field(default_factory=list)
    trajectories: Optional[dict] = None    # {track_id: [(x, y), ...]} pixels
    faces: Optional[list] = None
    poses: Optional[list] = None
    frame_index: int = 0
    video_ts: Optional[float] = None
    analyzed_at: float = 0.0          # perf_counter stamp

    @property
    def age_s(self) -> float:
        return time.perf_counter() - self.analyzed_at


class OverlayBoard:
    """Single-slot latest-overlay board (inference -> display).

    The display loop reads the latest result WITHOUT consuming it
    (peek) and applies a bounded staleness rule (tolerance seconds);
    an expired overlay is dropped (clean frame displayed instead).
    """

    def __init__(self, tolerance_s: float = 1.0) -> None:
        self._cond = threading.Condition()
        self._result: Optional[OverlayResult] = None
        self.tolerance_s = float(tolerance_s)

    def post(self, result: OverlayResult) -> None:
        with self._cond:
            self._result = result
            self._cond.notify_all()

    def peek_fresh(self) -> Optional[OverlayResult]:
        """Latest result if within the staleness tolerance, else None."""
        with self._cond:
            r = self._result
            if r is not None and r.age_s <= self.tolerance_s:
                return r
            return None

    def clear(self) -> None:
        with self._cond:
            self._result = None
