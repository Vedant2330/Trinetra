"""TRINETRA YuNet Face Detection Lifecycle (Phase 3, V2).

Detection-only face detection via cv2.FaceDetectorYN on yunet.onnx.
Honest availability gate: if model file is missing or fails to load,
available is False and detection is a clean no-op.

Features:
- Dynamic setInputSize((width, height)) synchronization before every detect() call.
- Event gating on person bbox height >= 80px.
- 5s cooldown per track for emitting FACE_DETECTED events.
- Strictly detection-only (no facial recognition, no identity gallery).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from backend.core.config import MODELS_DIR

log = logging.getLogger("trinetra.vision.face")

DEFAULT_YUNET_PATH = MODELS_DIR / "yunet.onnx"
MIN_PERSON_HEIGHT_PX = 80.0
FACE_EVENT_COOLDOWN_S = 5.0


@dataclass(frozen=True)
class FaceDetection:
    """Single detected face."""
    bbox: list[int]                    # [x, y, w, h] in pixel coordinates
    score: float                       # confidence score [0.0, 1.0]
    landmarks: list[list[float]]       # 5 landmarks [[x0, y0], ..., [x4, y4]]
    track_id: Optional[int] = None     # associated person track_id if gated
    class_name: str = "face"

    @property
    def xyxy(self) -> list[int]:
        """[x1, y1, x2, y2] bounding box."""
        x, y, w, h = self.bbox
        return [x, y, x + w, y + h]


class YuNetFaceDetector:
    """YuNet face detector wrapper using OpenCV's FaceDetectorYN.

    Lazy-loads the model file on first use or explicit check.
    Dynamically synchronizes input size to the current frame/crop size.
    """

    name = "yunet"

    def __init__(
        self,
        model_path: Optional[str | Path] = None,
        conf_threshold: float = 0.6,
        nms_threshold: float = 0.3,
        top_k: int = 5000,
    ) -> None:
        self._path = Path(model_path) if model_path else DEFAULT_YUNET_PATH
        self._conf_threshold = conf_threshold
        self._nms_threshold = nms_threshold
        self._top_k = top_k
        self._detector = None
        self._load_error: Optional[str] = None
        self._current_input_size: tuple[int, int] = (0, 0)  # (w, h)
        # track_id -> last_event_wall_ts
        self._last_event_ts: dict[int, float] = {}

    @property
    def available(self) -> bool:
        return self._try_load()

    def _try_load(self) -> bool:
        if self._detector is not None:
            return True
        if self._load_error is not None:
            return False
        if not self._path.exists():
            self._load_error = f"model file not found: {self._path}"
            return False
        try:
            self._detector = cv2.FaceDetectorYN.create(
                str(self._path),
                "",
                (320, 320),
                score_threshold=self._conf_threshold,
                nms_threshold=self._nms_threshold,
                top_k=self._top_k,
            )
            self._current_input_size = (320, 320)
            return True
        except Exception as e:               # noqa: BLE001 — honest gate
            self._load_error = f"{type(e).__name__}: {e}"
            log.warning("YuNet face detector load failed: %s", self._load_error)
            return False

    def detect(self, frame: np.ndarray, track_id: Optional[int] = None) -> list[FaceDetection]:
        """Detect faces in frame or crop.

        Dynamically updates setInputSize((width, height)) before inference.
        Returns empty list if detector unavailable or frame is invalid.
        """
        if frame is None or frame.size == 0 or not self._try_load():
            return []

        h, w = frame.shape[:2]
        if h < 2 or w < 2:
            return []

        try:
            if self._current_input_size != (w, h):
                self._detector.setInputSize((w, h))
                self._current_input_size = (w, h)

            _, faces = self._detector.detect(frame)
            if faces is None or len(faces) == 0:
                return []

            results: list[FaceDetection] = []
            for face in faces:
                x, y, fw, fh = (int(v) for v in face[:4])
                landmarks = [
                    [float(face[4 + 2 * j]), float(face[5 + 2 * j])]
                    for j in range(5)
                ]
                score = float(face[14])
                results.append(
                    FaceDetection(
                        bbox=[x, y, fw, fh],
                        score=score,
                        landmarks=landmarks,
                        track_id=track_id,
                    )
                )
            return results
        except Exception as e:               # noqa: BLE001 — detection safety
            log.debug("YuNet detection error: %s", e)
            return []

    def detect_in_person_tracks(
        self,
        frame: np.ndarray,
        tracks: list,
        wall_ts: float,
        min_height: float = MIN_PERSON_HEIGHT_PX,
        cooldown_s: float = FACE_EVENT_COOLDOWN_S,
    ) -> tuple[list[FaceDetection], list[dict]]:
        """Run face detection gated on person bboxes >= min_height (80px).

        Returns:
            (all_face_detections, face_event_draft_metadata_list)
        """
        if not self.available or frame is None or frame.size == 0:
            return [], []

        h, w = frame.shape[:2]
        all_faces: list[FaceDetection] = []
        event_drafts_meta: list[dict] = []

        for obj in tracks:
            if getattr(obj, "class_name", "") != "person":
                continue
            # TrackState exposes last_bbox (session passes store views,
            # not TrackedObject detections) — same seam reid uses.
            bbox = getattr(obj, "last_bbox", None)
            if bbox is None or len(bbox) < 4:
                continue
            x1, y1, x2, y2 = (int(v) for v in bbox)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            crop_h = y2 - y1
            crop_w = x2 - x1
            if crop_h < min_height or crop_w < 10:
                continue

            crop = frame[y1:y2, x1:x2]
            track_id = getattr(obj, "track_id", None)
            faces = self.detect(crop, track_id=track_id)
            for face in faces:
                fx, fy, fw, fh = face.bbox
                mapped_bbox = [fx + x1, fy + y1, fw, fh]
                mapped_landmarks = [
                    [lx + x1, ly + y1] for lx, ly in face.landmarks
                ]
                mapped_face = FaceDetection(
                    bbox=mapped_bbox,
                    score=face.score,
                    landmarks=mapped_landmarks,
                    track_id=track_id,
                )
                all_faces.append(mapped_face)

                # Cooldown per track_id for event generation
                if track_id is not None:
                    last_ts = self._last_event_ts.get(track_id, 0.0)
                    if (wall_ts - last_ts) >= cooldown_s:
                        self._last_event_ts[track_id] = wall_ts
                        event_drafts_meta.append({
                            "track_id": track_id,
                            "confidence": face.score,
                            "face_bbox": mapped_bbox,
                            "landmarks": mapped_landmarks,
                        })

        return all_faces, event_drafts_meta
