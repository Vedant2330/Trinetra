"""TRINETRA unified video source abstraction (M1).

Design decisions (frozen for M1, documented per mandate):

API shape — read() returns FramePacket | None.
  - None means "no frame this call". The caller distinguishes outcomes by
    checking `source.state`:
      OPEN  -> more frames expected
      EOF   -> file ended normally (FileSource only)
      ERROR -> open succeeded but reading failed (disconnect / undecodable)
  - open() failures raise SourceError with an actionable message.
  Rationale: the processing loop (M2+) needs a cheap per-frame hot path
  (no result-object allocation, no exceptions in the steady state) while
  still separating FRAME / EOF / FAILURE.

Timestamps:
  - wall_ts : float, epoch seconds at the moment the frame was read.
              Webcam semantics = wall-clock capture time.
  - video_ts: float | None. Deterministic seconds-into-file = frame_index / fps.
              None for live sources (webcam). No synchronization layer.

Frames are real OpenCV decode output: NumPy ndarray, uint8, BGR, HWC.
Sources never resize, drop, loop, or copy-alter frames (M1 rules).
"""

from __future__ import annotations

import logging
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np

log = logging.getLogger("trinetra.sources")


class SourceError(Exception):
    """Raised when a source cannot be opened or is used invalidly.

    Carries an actionable, human-readable message. Read-time failures
    after a successful open do NOT raise; they transition state to ERROR.
    """


class SourceState(str, Enum):
    IDLE = "IDLE"      # not opened yet
    OPEN = "OPEN"      # opened, more frames expected
    EOF = "EOF"        # source ended normally (files)
    ERROR = "ERROR"    # open succeeded but reading failed
    RELEASED = "RELEASED"


class FramePacket:
    """One decoded frame + metadata. Minimal by design (M1)."""

    __slots__ = ("frame", "wall_ts", "video_ts", "frame_index", "source_id")

    def __init__(
        self,
        frame: np.ndarray,
        wall_ts: float,
        video_ts: Optional[float],
        frame_index: int,
        source_id: str,
    ) -> None:
        self.frame = frame              # np.ndarray, uint8, BGR, HWC
        self.wall_ts = wall_ts          # epoch seconds at read time
        self.video_ts = video_ts        # seconds into file (None for live)
        self.frame_index = frame_index  # 0-based sequential index
        self.source_id = source_id      # e.g. "webcam:0", "file:running_clip.mp4"

    def __repr__(self) -> str:
        h, w = self.frame.shape[:2] if self.frame.ndim == 3 else (0, 0)
        return (
            f"FramePacket(src={self.source_id!r} idx={self.frame_index} "
            f"{w}x{h} wall_ts={self.wall_ts:.3f} video_ts={self.video_ts})"
        )


class VideoSource:
    """Minimal unified interface every source must expose.

    Lifecycle: open() -> read()* -> release()
    - release() is idempotent and safe to call from __exit__.
    - No threading, no queues, no registries (M1 rules).
    """

    source_id: str = ""

    def open(self) -> None:
        raise NotImplementedError

    def read(self) -> Optional[FramePacket]:
        raise NotImplementedError

    def release(self) -> None:
        raise NotImplementedError

    @property
    def state(self) -> SourceState:
        raise NotImplementedError

    # Context manager: 4 lines, used by tests and the future session loop.
    def __enter__(self) -> "VideoSource":
        if self.state == SourceState.IDLE:
            self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.release()

    # ---- shared helpers for implementations ----

    @staticmethod
    def _require_file(path: str | Path) -> Path:
        p = Path(path)
        if not p.exists():
            raise SourceError(f"file not found: {p}")
        if not p.is_file():
            raise SourceError(f"path is not a file: {p}")
        return p
