"""TRINETRA annotation — pure overlay rendering (M3).

Boundary (frozen): receives (frame, TrackedObject[], metrics) and returns a
NEW annotated ndarray. Never mutates the input, never runs detection, never
touches HTTP/sessions/DB. Renders ONLY real data:

  - bounding boxes from detector output
  - label "class conf|ID n" (ID shown only when track_id is not None)
  - pipeline FPS from the provided rolling metrics

Style: plain operational colors per class family (no neon/cyberpunk).
JPEG quality: cv2 default (95) at source; stream quality 70 is applied at
the session's encode step via config [stream] mjpeg_quality (documented;
no new config added).
"""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from backend.vision import TrackedObject

# class-family colors (BGR) — internal constants, not config (per M3 rules)
_COLOR = {
    "person": (230, 180, 60),        # warm amber
    "bicycle": (200, 200, 80),
    "car": (200, 120, 60),
    "motorcycle": (140, 180, 200),
    "bus": (160, 200, 60),
    "truck": (120, 140, 200),
}
_DEFAULT_COLOR = (160, 160, 160)
_FONT = cv2.FONT_HERSHEY_SIMPLEX
_THICK = 2


def _label_color(bgr: tuple) -> tuple:
    return tuple(int(c / 2) for c in bgr)


def annotate(
    frame: np.ndarray,
    objects: list[TrackedObject],
    pipeline_fps: Optional[float] = None,
    device: str = "",
) -> np.ndarray:
    """Return a NEW annotated copy of `frame`. Input is never mutated."""
    out = frame.copy()
    h, w = out.shape[:2]

    for o in objects:
        color = _COLOR.get(o.class_name, _DEFAULT_COLOR)
        x1, y1, x2, y2 = (int(v) for v in o.bbox)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        cv2.rectangle(out, (x1, y1), (x2, y2), color, _THICK)
        # label: real class, real confidence, real ID (only if present)
        id_part = f" | ID {o.track_id}" if o.track_id is not None else ""
        label = f"{o.class_name} {o.confidence:.2f}{id_part}"
        (tw, th), _ = cv2.getTextSize(label, _FONT, 0.5, 1)
        ly = y1 - 6 if y1 - th - 6 >= 0 else y1 + th + 6
        cv2.rectangle(out, (x1, ly - th - 4), (x1 + tw + 6, ly + 4), _label_color(color), -1)
        cv2.putText(out, label, (x1 + 3, ly), _FONT, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    # HUD: pipeline FPS + device — top-left, real measured values only
    hud = ""
    if pipeline_fps is not None:
        hud += f"FPS {pipeline_fps:.1f}"
    if device:
        hud += f"  |  {device}"
    if hud:
        cv2.putText(out, hud, (10, 24), _FONT, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    return out
