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


# zone overlay colors (BGR) — RESTRICTED red, WATCH blue (M4 semantics)
_ZONE_COLOR = {"RESTRICTED": (60, 60, 230), "WATCH": (200, 120, 60)}


def _draw_zone(out: np.ndarray, w: int, h: int, z: dict) -> None:
    """Draw ONE normalized-coordinates zone onto the frame. Geometry is
    §12 JSON: polygon {points:[[x,y]..]} or line {p1,p2}. Never raises on
    malformed geometry — a bad zone degrades to nothing drawn."""
    try:
        color = _ZONE_COLOR.get(z.get("zone_type", "RESTRICTED"),
                                (160, 160, 160))
        geom = z.get("geometry", {}) or {}
        name = str(z.get("name", ""))
        if z.get("kind") == "polygon":
            pts = np.array(
                [[int(x * w), int(y * h)] for x, y in geom["points"]],
                dtype=np.int32).reshape(-1, 1, 2)
            cv2.polylines(out, [pts], True, color, 2)
        elif z.get("kind") == "line":
            p1 = geom.get("p1")
            p2 = geom.get("p2")
            cv2.line(out, (int(p1[0] * w), int(p1[1] * h)),
                     (int(p2[0] * w), int(p2[1] * h)), color, 2)
            cv2.circle(out, (int(p1[0] * w), int(p1[1] * h)), 4, color, -1)
            cv2.circle(out, (int(p2[0] * w), int(p2[1] * h)), 4, color, -1)
        else:
            return
        if name:
            anchor = geom.get("p1") or geom.get("points", [[0, 0]])[0]
            cv2.putText(out, name, (int(anchor[0] * w) + 4,
                                   int(anchor[1] * h) - 6),
                        _FONT, 0.5, color, 1, cv2.LINE_AA)
    except (KeyError, ValueError, TypeError, IndexError):
        return                    # malformed zone geometry — skip cleanly


def _draw_trajectory(out: np.ndarray, pts: list) -> None:
    """Draw ONE track's foot-point polyline. pts = PIXEL (x, y) 2-tuples.
    Never raises on malformed input — bad shapes degrade to nothing
    drawn (same discipline as _draw_zone)."""
    try:
        if not pts:
            return
        px = [(int(x), int(y)) for x, y in pts]
        if len(px) < 2:
            cv2.circle(out, px[0], 2, (200, 200, 200), -1)
            return
        cv2.polylines(out, [np.array(px, dtype=np.int32).reshape(-1, 1, 2)],
                      False, (200, 200, 200), 2, cv2.LINE_AA)
    except (KeyError, ValueError, TypeError, IndexError):
        return                    # malformed trajectory — skip cleanly


def annotate(
    frame: np.ndarray,
    objects: list[TrackedObject],
    pipeline_fps: Optional[float] = None,
    device: str = "",
    zones: Optional[list] = None,
    layers: Optional[dict] = None,
    trajectories: Optional[dict] = None,
) -> np.ndarray:
    """Return a NEW annotated copy of `frame`. Input is never mutated.

    zones (M7, Oscar M5 ruling): optional list of zone dicts
    {kind, zone_type, geometry{points|p1,p2}, name} in NORMALIZED
    frame coordinates — drawn server-side so an operator snapshot can
    show the breached zone. None (default) = M3 frozen surface.

    layers (V3, additive): optional {"boxes": bool, "labels": bool,
    "fps": bool} — partial-tolerant, missing key = default True.
    "boxes" gates rectangles AND the label chip; "labels" gates ONLY
    the " | ID n" suffix (class+conf text stays — that is the
    Track-IDs toggle); "fps" gates the HUD text.

    trajectories (V3, additive): optional {track_id: [(x, y), ...]} —
    PIXEL foot-point 2-tuples (the session converts from TrackState's
    (x, y, tick) deque). Thin dim polyline per track; skips empty;
    never raises on malformed input. None (default) = frozen surface."""
    # partial-tolerant layer flags (missing key = True = frozen surface)
    lay = {"boxes": True, "labels": True, "fps": True}
    if layers:
        for k in ("boxes", "labels", "fps"):
            v = layers.get(k)
            if isinstance(v, bool):
                lay[k] = v

    out = frame.copy()
    h, w = out.shape[:2]

    if trajectories:
        for _tid, pts in trajectories.items():
            _draw_trajectory(out, pts)

    if zones:
        for z in zones:
            _draw_zone(out, w, h, z)

    for o in objects:
        color = _COLOR.get(o.class_name, _DEFAULT_COLOR)
        x1, y1, x2, y2 = (int(v) for v in o.bbox)
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)
        if x2 <= x1 or y2 <= y1:
            continue
        if lay["boxes"]:
            cv2.rectangle(out, (x1, y1), (x2, y2), color, _THICK)
        # label: real class, real confidence, real ID (only if present)
        id_part = f" | ID {o.track_id}" if (o.track_id is not None and lay["labels"]) else ""
        label = f"{o.class_name} {o.confidence:.2f}{id_part}"
        if lay["boxes"]:
            (tw, th), _ = cv2.getTextSize(label, _FONT, 0.5, 1)
            ly = y1 - 6 if y1 - th - 6 >= 0 else y1 + th + 6
            cv2.rectangle(out, (x1, ly - th - 4), (x1 + tw + 6, ly + 4), _label_color(color), -1)
            cv2.putText(out, label, (x1 + 3, ly), _FONT, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    # HUD: pipeline FPS + device — top-left, real measured values only
    if not lay["fps"]:
        return out
    hud = ""
    if pipeline_fps is not None:
        hud += f"FPS {pipeline_fps:.1f}"
    if device:
        hud += f"  |  {device}"
    if hud:
        cv2.putText(out, hud, (10, 24), _FONT, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    return out
