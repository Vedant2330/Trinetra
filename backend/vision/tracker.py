"""TRINETRA DetectorTracker — the single detection+tracking boundary (M2).

Architecture (frozen Phase 1):
  - ONE model strategy: yolov8n.pt via backend/core/config.py (project-relative).
  - ONE tracking authority: Ultralytics ByteTrack inside model.track().
    Detector-generated track IDs are authoritative. No secondary IDs anywhere.
  - ONE instance per processing session: ByteTrack state lives inside this
    YOLO instance; creating a fresh DetectorTracker per session guarantees
    clean IDs (no cross-session contamination). No module-level model.

Device policy (config [device] policy):
  - auto: MPS if torch.backends.mps.is_available() else CPU.
  - mps : explicit; if MPS unavailable -> DetectorError (no silent fallback).
  - cpu : explicit CPU.
  Fallback: if the first MPS inference raises, the model is reloaded on CPU
  once, `actual_device` reflects the truth, and a warning is logged.
  Reports must always read `actual_device` — never the requested policy.

Frame contract (M1 frozen): consumes BGR uint8 HWC ndarray; no RGB
conversion (ultralytics handles channel order internally); the input
frame is never mutated. Output is a separate list of TrackedObject.

Track ID honesty: ultralytics assigns IDs on tracked frames; if boxes.id
is absent on a frame (e.g. before first assignment), objects carry
track_id=None. IDs are never fabricated or substituted.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np

from backend.core.config import VISION

log = logging.getLogger("trinetra.vision")


class DetectorError(Exception):
    """Model missing/invalid, unusable device request, or dead pipeline."""


# COCO names for the classes we track — single source (no scattered magic
# numbers; config carries IDs, this map carries display names only).
COCO_NAMES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}


class TrackedObject:
    """One detection on one frame, with authoritative ByteTrack ID if present.

    bbox = [x1, y1, x2, y2] float pixels in the INPUT frame's coordinate
    space (top-left origin, x right, y down). confidence = raw model score.
    """

    __slots__ = ("track_id", "class_id", "class_name", "confidence", "bbox")

    def __init__(
        self,
        track_id: Optional[int],
        class_id: int,
        class_name: str,
        confidence: float,
        bbox: list[float],
    ) -> None:
        self.track_id = track_id        # int | None — authoritative, never invented
        self.class_id = class_id
        self.class_name = class_name
        self.confidence = confidence    # raw detector confidence
        self.bbox = bbox                 # [x1, y1, x2, y2] input-frame pixels

    def __repr__(self) -> str:
        return (f"TrackedObject(id={self.track_id} {self.class_name} "
                f"conf={self.confidence:.2f} bbox={[round(v, 1) for v in self.bbox]})")


class DetectorTracker:
    """Per-session detector+tracker. Create one per processing session.

    process(frame) is the only hot-path method. Model load time is measured
    and exposed via `load_seconds`.
    """

    def __init__(self, policy: str = "") -> None:
        from backend.core.config import DEVICE
        self._policy = policy or DEVICE.policy
        self._classes = VISION.classes
        self._conf = VISION.conf
        self._imgsz = VISION.imgsz
        self._model = None
        self._model_path = None          # resolved at load()
        self._device = ""                # resolved device string
        self.load_seconds: float = 0.0
        self._frame_shape: tuple[int, int] = (0, 0)  # (h, w) expected by process()

    # ---- lifecycle ----

    def load(self) -> None:
        """Load model + resolve device. Cheap; called once per session.

        Reads MODELS_DIR at load time (not construction) so config tests
        and future overrides behave predictably.
        """
        from backend.core.config import MODELS_DIR
        self._model_path = MODELS_DIR / VISION.model
        if not self._model_path.exists():
            raise DetectorError(f"model file missing: {self._model_path}")
        self._device = self._resolve_device(self._policy)
        t0 = time.perf_counter()
        try:
            from ultralytics import YOLO
            self._model = YOLO(str(self._model_path))
            self._model.to(self._device)
        except Exception as e:
            raise DetectorError(f"model load failed: {e}") from e
        self.load_seconds = time.perf_counter() - t0

    @property
    def actual_device(self) -> str:
        """The device actually in use — the ONLY source for performance reports."""
        return self._device

    @staticmethod
    def _resolve_device(policy: str) -> str:
        import torch
        mps = torch.backends.mps.is_available()
        if policy == "cpu":
            return "cpu"
        if policy == "mps":
            if not mps:
                raise DetectorError("device policy 'mps' requested but MPS is unavailable")
            return "mps"
        # auto
        return "mps" if mps else "cpu"

    # ---- hot path ----

    def process(self, frame: np.ndarray) -> list[TrackedObject]:
        """Detect+track one BGR frame. Returns [] when nothing detected.

        Raises DetectorError on: model not loaded, invalid frame, dead
        pipeline (inference failure after CPU fallback). An empty scene is
        a NORMAL result ([]), never an error.
        """
        self._require_ready()
        self._validate_frame(frame)

        try:
            results = self._model.track(
                frame,
                persist=True,               # ByteTrack state across calls
                conf=self._conf,
                imgsz=self._imgsz,
                classes=self._classes,       # single detector, filtered classes
                tracker="bytetrack.yaml",
                verbose=False,
            )
        except Exception as e:
            msg = str(e)
            if self._device == "mps" and ("MPS" in msg or "metal" in msg.lower() or "SyntaxError" in msg):
                log.warning("MPS inference failed (%s) — falling back to CPU", msg[:120])
                self._reload_on_cpu()
                return self._retry_after_fallback(frame)
            raise DetectorError(f"inference failed: {msg}") from e

        return self._extract(results)

    # ---- internals ----

    def _require_ready(self) -> None:
        if self._model is None:
            raise DetectorError("detector not loaded — call load() first")

    @staticmethod
    def _validate_frame(frame: np.ndarray) -> None:
        if not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3:
            raise DetectorError(f"invalid frame: expected HWC BGR ndarray, got "
                                f"{type(frame).__name__} {getattr(frame, 'shape', None)}")
        if frame.shape[0] < 2 or frame.shape[1] < 2:
            raise DetectorError(f"invalid frame dimensions: {frame.shape[:2]}")

    def _reload_on_cpu(self) -> None:
        from ultralytics import YOLO
        if self._model_path is None:
            from backend.core.config import MODELS_DIR
            self._model_path = MODELS_DIR / VISION.model
        self._model = YOLO(str(self._model_path))
        self._model.to("cpu")
        self._device = "cpu (fallback from mps)"

    def _retry_after_fallback(self, frame: np.ndarray) -> list[TrackedObject]:
        try:
            results = self._model.track(
                frame, persist=True, conf=self._conf, imgsz=self._imgsz,
                classes=self._classes, tracker="bytetrack.yaml", verbose=False,
            )
        except Exception as e:
            raise DetectorError(f"inference failed after CPU fallback: {e}") from e
        return self._extract(results)

    def _extract(self, results) -> list[TrackedObject]:
        """Map ultralytics Results -> TrackedObject list, honestly."""
        out: list[TrackedObject] = []
        if not results:
            return out
        r = results[0]
        boxes = r.boxes
        if boxes is None:
            return out
        ids = boxes.id                       # None until tracker assigns
        ids_list = ids.tolist() if ids is not None else None
        for i in range(len(boxes)):
            tid = int(ids_list[i]) if ids_list is not None else None
            cls = int(boxes.cls[i].item())
            out.append(TrackedObject(
                track_id=tid,
                class_id=cls,
                class_name=COCO_NAMES.get(cls, f"cls{cls}"),
                confidence=float(boxes.conf[i].item()),
                bbox=[float(v) for v in boxes.xyxy[i].tolist()],
            ))
        return out
