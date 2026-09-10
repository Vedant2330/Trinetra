"""TRINETRA ANPR Analytic — Three-State Validation Engine & Offline Network Gate (V3.5 / Phase 6).

Implements:
1. Indian license plate regex validation:
   - Standard format: ^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$ (e.g. DL01AB1234, MH12CD5678)
   - Bharat (BH) series: ^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$ (e.g. 22BH1234AA)
2. Three-state classification engine:
   - ANPR_READ (MEDIUM): OCR confidence >= 0.80 and regex matches valid Indian format.
   - OCR_UNCERTAIN (LOW): OCR text present but confidence < 0.80 or fails regex validation.
   - ANPR_PLATE_DETECTED (LOW): Plate region localized, but OCR unavailable/unperformed.
3. Vehicle-triggered heuristic localization on vehicle bounding boxes (width >= 100px).
4. Offline network gating:
   - Zero network/cloud requests.
   - Graceful fallback to heuristic plate localization when models/yolov8n_plate.pt is absent.
   - Plate crop size gate: skips OCR if crop width < 64px to avoid hallucinations.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

import numpy as np

from backend.analytics.base import AnalyticModule, EventDraft, FrameContext
from backend.core.config import ROOT

log = logging.getLogger("trinetra.analytics.anpr")

# Regex definitions for Indian license plates
# Standard: State (2 letters) + RTO (1-2 digits) + Series (0-3 letters) + Number (4 digits)
STANDARD_PLATE_REGEX = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$")

# Bharat (BH) Series: Year (2 digits) + 'BH' + Number (4 digits) + Series (1-2 letters)
BH_SERIES_REGEX = re.compile(r"^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$")

_VEHICLE_CLASSES = frozenset({"car", "truck", "bus", "motorcycle", "bicycle"})


def clean_plate_text(text: Optional[str]) -> str:
    """Normalize raw OCR string: strip punctuation, whitespace, and uppercase."""
    if not text:
        return ""
    # Remove all characters except alphanumeric
    cleaned = re.sub(r"[^A-Za-z0-9]", "", text).upper()
    return cleaned


def validate_indian_plate(text: Optional[str]) -> tuple[bool, str]:
    """Validate normalized plate string against Indian standard and BH-series patterns.

    Returns:
        (is_valid: bool, plate_type: str)
        plate_type is one of: "standard", "bh_series", "invalid"
    """
    cleaned = clean_plate_text(text)
    if not cleaned:
        return False, "invalid"

    if STANDARD_PLATE_REGEX.match(cleaned):
        return True, "standard"

    if BH_SERIES_REGEX.match(cleaned):
        return True, "bh_series"

    return False, "invalid"


def classify_anpr_read(
    text: Optional[str],
    confidence: float = 1.0,
    plate_bbox: Optional[list[int]] = None,
    detection_mode: str = "heuristic",
) -> tuple[str, dict[str, Any]]:
    """Classify plate observation into one of three explicit states (§2.8).

    States:
    1. ANPR_READ: OCR confidence >= 0.80 and regex matches valid Indian plate.
    2. OCR_UNCERTAIN: Text is present but confidence < 0.80 or fails regex validation.
    3. ANPR_PLATE_DETECTED: Plate region localized, but OCR unavailable or unperformed.

    Returns:
        (event_type: str, metadata: dict)
    """
    if not text:
        return "ANPR_PLATE_DETECTED", {
            "plate_text": None,
            "ocr_available": False,
            "plate_bbox": plate_bbox,
            "detection_mode": detection_mode,
        }

    cleaned = clean_plate_text(text)
    is_valid, plate_type = validate_indian_plate(cleaned)

    if confidence >= 0.80 and is_valid:
        return "ANPR_READ", {
            "plate_text": cleaned,
            "plate_type": plate_type,
            "ocr_confidence": round(float(confidence), 3),
            "ocr_validated": True,
            "plate_bbox": plate_bbox,
            "detection_mode": detection_mode,
        }

    uncertain_reason = "low_confidence" if confidence < 0.80 else "invalid_format"
    return "OCR_UNCERTAIN", {
        "raw_text": text,
        "cleaned_text": cleaned,
        "ocr_confidence": round(float(confidence), 3),
        "ocr_validated": False,
        "uncertain_reason": uncertain_reason,
        "plate_bbox": plate_bbox,
        "detection_mode": detection_mode,
    }


def locate_plate_heuristic(
    vehicle_bbox: tuple[int, int, int, int] | list[int],
    frame_shape: tuple[int, int],
    frame: Optional[np.ndarray] = None,
) -> Optional[list[int]]:
    """Estimate license plate bounding box using geometric vehicle aspect-ratio heuristics.

    Target region: Center-horizontal (20%-80% of width) and lower-third (65%-95% of height).
    Gated: Returns None if vehicle bounding box width < 100px.
    """
    vx1, vy1, vx2, vy2 = [int(v) for v in vehicle_bbox]
    vw = vx2 - vx1
    vh = vy2 - vy1

    # Vehicle size gate (Task 6.2)
    if vw < 100 or vh < 40:
        return None

    frame_w, frame_h = frame_shape

    px1 = max(0, vx1 + int(vw * 0.20))
    px2 = min(frame_w, vx1 + int(vw * 0.80))
    py1 = max(0, vy1 + int(vh * 0.65))
    py2 = min(frame_h, vy1 + int(vh * 0.95))

    pw = px2 - px1
    ph = py2 - py1

    if pw <= 0 or ph <= 0:
        return None

    return [px1, py1, px2, py2]


class ANPRAnalytic(AnalyticModule):
    """Three-state ANPR Analytic module with offline model detection and heuristic fallback."""

    id = "anpr"

    def __init__(
        self,
        model_path: Optional[Path | str] = None,
        min_vehicle_width: int = 100,
        min_plate_crop_width: int = 64,
        ocr_engine: Optional[Any] = None,
        cooldown_ticks: int = 30,
    ) -> None:
        self._min_vehicle_width = min_vehicle_width
        self._min_plate_crop_width = min_plate_crop_width
        self._ocr_engine = ocr_engine
        self._cooldown_ticks = cooldown_ticks
        self._session_id = ""

        # Model presence check (offline network gate)
        target_path = Path(model_path) if model_path else (ROOT / "models" / "yolov8n_plate.pt")
        self._model_path = target_path
        self._model: Optional[Any] = None
        self._mode = "heuristic_fallback"

        if target_path.exists():
            try:
                from ultralytics import YOLO
                self._model = YOLO(str(target_path))
                self._mode = "model"
                log.info("Loaded ANPR plate model from %s", target_path)
            except Exception as e:
                log.warning("Could not initialize ANPR model from %s: %s; using heuristic fallback", target_path, e)
                self._model = None
                self._mode = "heuristic_fallback"
        else:
            log.info("ANPR plate model %s absent; active mode is heuristic_fallback", target_path)

        # Track state tracking to prevent spamming
        self._last_processed_tick: dict[int, int] = {}
        self._last_emitted_state: dict[int, str] = {}
        # Current tick's frame (set via set_frame by the session; the
        # shape-B seam that lets the model/OCR branches run on pixels)
        self._current_frame: Optional[np.ndarray] = None

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def model_available(self) -> bool:
        return self._model is not None

    def reset(self, session_id: str) -> None:
        """Clear per-track ANPR state for a new session."""
        self._session_id = session_id
        self._last_processed_tick.clear()
        self._last_emitted_state.clear()
        self._current_frame: Optional[np.ndarray] = None

    def set_frame(self, frame: Optional[np.ndarray]) -> None:
        """Provide the current tick's frame (shape-B service seam: the
        session sets it BEFORE the analytics chain runs each tick, the
        same pixel-delivery pattern reid/face use). Without a frame the
        analytic degrades honestly to heuristic localization — the model
        and OCR branches require pixels and never fabricate reads."""
        self._current_frame = frame

    def process(self, ctx: FrameContext, tracks: Any) -> list[EventDraft]:
        """AnalyticModule interface: evaluates active tracks against vehicle ANPR criteria."""
        active_tracks = getattr(tracks, "active_tracks", None)
        if active_tracks is None:
            if hasattr(tracks, "tracks"):
                active_tracks = tracks.tracks
            elif isinstance(tracks, list):
                active_tracks = tracks
            else:
                return []

        return self.process_tracks(self._current_frame, active_tracks, ctx)

    def process_tracks(
        self,
        frame: Optional[np.ndarray],
        active_tracks: list[Any],
        ctx: FrameContext,
    ) -> list[EventDraft]:
        """Process active vehicle tracks for license plate localization and classification."""
        drafts: list[EventDraft] = []

        for t in active_tracks:
            cname = getattr(t, "class_name", "")
            if cname not in _VEHICLE_CLASSES:
                continue

            tid = getattr(t, "track_id", None)
            if tid is None:
                continue

            # Check bbox — TrackState exposes last_bbox (session passes
            # store views via process(ctx, view), not TrackedObject).
            bbox = getattr(t, "last_bbox", None)
            if bbox is None:
                continue

            x1, y1, x2, y2 = bbox
            vw = x2 - x1
            if vw < self._min_vehicle_width:
                continue

            # Check tick cooldown
            last_tick = self._last_processed_tick.get(tid, -1)
            if last_tick != -1 and (ctx.tick - last_tick) < self._cooldown_ticks:
                continue

            # Plate localization (Model or Heuristic)
            plate_bbox: Optional[list[int]] = None
            detection_mode = self._mode

            if self._model is not None and frame is not None:
                try:
                    # Run plate model on vehicle crop
                    vx1, vy1, vx2, vy2 = max(0, int(x1)), max(0, int(y1)), min(ctx.shape[0], int(x2)), min(ctx.shape[1], int(y2))
                    vcrop = frame[vy1:vy2, vx1:vx2]
                    if vcrop.size > 0:
                        results = self._model(vcrop, verbose=False)
                        if results and len(results[0].boxes) > 0:
                            box = results[0].boxes[0]
                            bx1, by1, bx2, by2 = [int(coord) for coord in box.xyxy[0].tolist()]
                            plate_bbox = [vx1 + bx1, vy1 + by1, vx1 + bx2, vy1 + by2]
                            detection_mode = "model"
                except Exception as e:
                    log.debug("Model plate detection error: %s; falling back to heuristic", e)
                    plate_bbox = None

            if plate_bbox is None:
                plate_bbox = locate_plate_heuristic((x1, y1, x2, y2), ctx.shape, frame)
                detection_mode = "heuristic"

            if plate_bbox is None:
                continue

            pw = plate_bbox[2] - plate_bbox[0]

            # Size gating on plate crop (Task 6.2)
            if pw < self._min_plate_crop_width:
                # Plate crop is too small (<64px) -> skip OCR to prevent hallucinations
                event_type, meta = classify_anpr_read(
                    text=None,
                    confidence=0.75,
                    plate_bbox=plate_bbox,
                    detection_mode=detection_mode,
                )
                meta["ocr_skipped_reason"] = "plate_crop_too_small"
            elif self._ocr_engine is not None and frame is not None:
                # Execute OCR if engine is available
                try:
                    px1, py1, px2, py2 = plate_bbox
                    pcrop = frame[py1:py2, px1:px2]
                    ocr_text, ocr_conf = self._ocr_engine.read_plate(pcrop)
                    event_type, meta = classify_anpr_read(
                        text=ocr_text,
                        confidence=ocr_conf,
                        plate_bbox=plate_bbox,
                        detection_mode=detection_mode,
                    )
                except Exception as e:
                    log.warning("OCR engine failed: %s", e)
                    event_type, meta = classify_anpr_read(
                        text=None,
                        confidence=0.75,
                        plate_bbox=plate_bbox,
                        detection_mode=detection_mode,
                    )
            else:
                # OCR unavailable or offline
                event_type, meta = classify_anpr_read(
                    text=None,
                    confidence=0.75,
                    plate_bbox=plate_bbox,
                    detection_mode=detection_mode,
                )

            # Avoid spamming duplicate identical states for the same track
            if self._last_emitted_state.get(tid) == event_type and event_type == "ANPR_PLATE_DETECTED":
                continue

            self._last_processed_tick[tid] = ctx.tick
            self._last_emitted_state[tid] = event_type

            drafts.append(
                EventDraft(
                    type=event_type,
                    track_ids=[tid],
                    zone_id=None,
                    direction=getattr(t, "direction", None),
                    confidence=meta.get("ocr_confidence", 0.85 if event_type == "ANPR_READ" else 0.75),
                    metadata={
                        **meta,
                        "is_night": ctx.is_night,
                        "video_ts": ctx.video_ts,
                        "tick": ctx.tick,
                        "vehicle_class": cname,
                        "track_id": tid,
                    },
                )
            )

        return drafts
