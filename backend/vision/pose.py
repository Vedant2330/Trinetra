"""TRINETRA YOLOv8 Human Pose Estimation Lifecycle (Phase 8, V1).

Extracts 17 COCO human body landmarks via Ultralytics YOLOv8-pose.
Honest availability gate: if model file is missing or fails to load,
available is False and pose detection is a clean no-op.

Keypoints (COCO 17):
  0: Nose, 1: Left Eye, 2: Right Eye, 3: Left Ear, 4: Right Ear
  5: Left Shoulder, 6: Right Shoulder, 7: Left Elbow, 8: Right Elbow
  9: Left Wrist, 10: Right Wrist, 11: Left Hip, 12: Right Hip
  13: Left Knee, 14: Right Knee, 15: Left Ankle, 16: Right Ankle
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from backend.core.config import MODELS_DIR

log = logging.getLogger("trinetra.vision.pose")

DEFAULT_POSE_PATH = MODELS_DIR / "yolov8n-pose.pt"

COCO_SKELETON_EDGES = [
    (0, 1), (0, 2), (1, 3), (2, 4),          # Facial landmarks
    (5, 6),                                  # Shoulders
    (5, 7), (7, 9),                          # Left arm
    (6, 8), (8, 10),                         # Right arm
    (5, 11), (6, 12),                        # Torso sides
    (11, 12),                                # Hips
    (11, 13), (13, 15),                      # Left leg
    (12, 14), (14, 16),                      # Right leg
]


@dataclass(frozen=True)
class PoseDetection:
    """Single detected human pose with 17 keypoints."""
    bbox: list[int]                           # [x1, y1, x2, y2] in pixel coordinates
    score: float                              # detection confidence score [0.0, 1.0]
    keypoints: list[list[float]]              # 17 keypoints [[x, y, conf], ...]
    track_id: Optional[int] = None            # associated person track_id if matched
    class_name: str = "person_pose"


class YOLOv8PoseDetector:
    """YOLOv8-pose detector wrapper using Ultralytics.

    Lazy-loads the model file on first use or explicit check.
    Operates on GPU (MPS/CUDA) or CPU based on system policy.
    """

    name = "yolov8n-pose"

    def __init__(
        self,
        model_path: Optional[str | Path] = None,
        conf_threshold: float = 0.4,
    ) -> None:
        self._path = Path(model_path) if model_path else DEFAULT_POSE_PATH
        self._conf_threshold = conf_threshold
        self._model = None
        self._load_error: Optional[str] = None
        self._device: str = "cpu"

    @property
    def available(self) -> bool:
        return self._try_load()

    def _try_load(self) -> bool:
        if self._model is not None:
            return True
        if self._load_error is not None:
            return False
        if not self._path.exists():
            self._load_error = f"pose model file not found: {self._path}"
            return False
        try:
            import torch
            from ultralytics import YOLO

            if torch.backends.mps.is_available():
                self._device = "mps"
            elif torch.cuda.is_available():
                self._device = "cuda"
            else:
                self._device = "cpu"

            self._model = YOLO(str(self._path))
            log.info("YOLOv8 pose detector loaded on %s: %s", self._device, self._path)
            return True
        except Exception as e:               # noqa: BLE001 — honest gate
            self._load_error = f"{type(e).__name__}: {e}"
            log.warning("YOLOv8 pose detector load failed: %s", self._load_error)
            return False

    def detect(self, frame: np.ndarray) -> list[PoseDetection]:
        """Detect poses and keypoints in frame.

        Returns empty list if detector unavailable or frame is invalid.
        """
        if frame is None or frame.size == 0 or not self._try_load():
            return []

        h, w = frame.shape[:2]
        if h < 2 or w < 2:
            return []

        try:
            results = self._model.predict(
                frame,
                conf=self._conf_threshold,
                device=self._device,
                verbose=False,
            )
            if not results:
                return []

            res = results[0]
            if res.keypoints is None or len(res.keypoints) == 0:
                return []

            boxes = res.boxes
            keypoints_data = res.keypoints.data.cpu().numpy()  # (N, 17, 3)

            poses: list[PoseDetection] = []
            for i in range(len(keypoints_data)):
                kpts = keypoints_data[i].tolist()  # [[x, y, conf], ...]
                score = float(boxes.conf[i].cpu().item()) if boxes is not None and len(boxes) > i else 1.0
                xyxy = [int(v) for v in boxes.xyxy[i].cpu().numpy()] if boxes is not None and len(boxes) > i else [0, 0, w, h]

                poses.append(
                    PoseDetection(
                        bbox=xyxy,
                        score=score,
                        keypoints=kpts,
                    )
                )
            return poses
        except Exception as e:               # noqa: BLE001 — safety
            log.debug("YOLOv8 pose detection error: %s", e)
            return []
