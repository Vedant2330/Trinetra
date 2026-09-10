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
    "backpack": (180, 100, 220),     # purple
    "handbag": (200, 100, 180),
    "suitcase": (160, 140, 210),
    "chair": (100, 200, 180),        # teal
    "couch": (120, 180, 160),
    "potted plant": (100, 220, 120),  # green
    "dining table": (140, 160, 180),
    "laptop": (220, 160, 80),        # cyan/blue-tint
    "tv": (200, 150, 100),
    "cell phone": (230, 140, 120),
    "bottle": (120, 210, 220),
    "cup": (140, 200, 220),
    "book": (180, 160, 140),
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
    except (KeyError, ValueError, TypeError, IndexError,
            OverflowError, cv2.error):
        return                    # malformed zone geometry — skip cleanly


def _draw_trajectory(out: np.ndarray, pts: list, color: tuple = (0, 225, 255)) -> None:
    """Draw ONE track's foot-point polyline. pts = PIXEL (x, y) 2-tuples.
    Renders high-contrast anti-aliased polyline with dark shadow outline
    and distinct ground-contact anchor points."""
    try:
        if not pts:
            return
        px = [(int(x), int(y)) for x, y in pts]
        if len(px) < 2:
            cv2.circle(out, px[0], 3, (20, 20, 20), -1, cv2.LINE_AA)
            cv2.circle(out, px[0], 2, color, -1, cv2.LINE_AA)
            return
        poly = np.array(px, dtype=np.int32).reshape(-1, 1, 2)
        # 1) Dark outer outline (shadow) for contrast against white/light backgrounds
        cv2.polylines(out, [poly], False, (20, 20, 20), 4, cv2.LINE_AA)
        # 2) High-contrast vibrant polyline
        cv2.polylines(out, [poly], False, color, 2, cv2.LINE_AA)
        # 3) Current foot-point dot
        cv2.circle(out, px[-1], 4, (20, 20, 20), -1, cv2.LINE_AA)
        cv2.circle(out, px[-1], 2, (255, 255, 255), -1, cv2.LINE_AA)
    except (KeyError, ValueError, TypeError, IndexError):
        return                    # malformed trajectory — skip cleanly


def _draw_face(out: np.ndarray, face) -> None:
    """Draw ONE detected face: bounding box + 5 facial landmarks + score."""
    try:
        bbox = getattr(face, "bbox", None)
        if bbox is None and isinstance(face, dict):
            bbox = face.get("bbox")
        if not bbox or len(bbox) < 4:
            return
        fx, fy, fw, fh = [int(v) for v in bbox[:4]]
        # Cyan / teal box for faces (distinct from warm amber person)
        color = (220, 200, 60)
        cv2.rectangle(out, (fx, fy), (fx + fw, fy + fh), color, 1)

        landmarks = getattr(face, "landmarks", None)
        if landmarks is None and isinstance(face, dict):
            landmarks = face.get("landmarks")
        if landmarks:
            for pt in landmarks:
                cv2.circle(out, (int(pt[0]), int(pt[1])), 2, (0, 220, 255), -1)

        score = getattr(face, "score", None)
        if score is None and isinstance(face, dict):
            score = face.get("score")
        if score is not None:
            lbl = f"face {float(score):.2f}"
            (tw, th), _ = cv2.getTextSize(lbl, _FONT, 0.4, 1)
            ly = fy - 4 if fy - th - 4 >= 0 else fy + fh + th + 4
            cv2.rectangle(out, (fx, ly - th - 2), (fx + tw + 4, ly + 2), _label_color(color), -1)
            cv2.putText(out, lbl, (fx + 2, ly), _FONT, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
    except Exception:
        return


_COCO_EDGES = [
    (0, 1), (0, 2), (1, 3), (2, 4),
    (5, 6), (5, 7), (7, 9), (6, 8), (8, 10),
    (5, 11), (6, 12), (11, 12),
    (11, 13), (13, 15), (12, 14), (14, 16),
]


def _draw_pose(out: np.ndarray, pose) -> None:
    """Draw ONE detected human pose skeleton (17 COCO landmarks)."""
    try:
        kpts = getattr(pose, "keypoints", None)
        if kpts is None and isinstance(pose, dict):
            kpts = pose.get("keypoints")
        if not kpts or len(kpts) < 17:
            return

        conf_thresh = 0.3
        # Draw skeleton limb connections
        edge_color = (60, 220, 120)  # Bright green/cyan
        for p1_idx, p2_idx in _COCO_EDGES:
            if p1_idx < len(kpts) and p2_idx < len(kpts):
                pt1, pt2 = kpts[p1_idx], kpts[p2_idx]
                c1 = pt1[2] if len(pt1) > 2 else 1.0
                c2 = pt2[2] if len(pt2) > 2 else 1.0
                if c1 >= conf_thresh and c2 >= conf_thresh:
                    cv2.line(
                        out,
                        (int(pt1[0]), int(pt1[1])),
                        (int(pt2[0]), int(pt2[1])),
                        edge_color,
                        2,
                        cv2.LINE_AA,
                    )

        # Draw keypoint circles
        kpt_color = (0, 230, 255)  # Bright yellow
        for pt in kpts:
            c = pt[2] if len(pt) > 2 else 1.0
            if c >= conf_thresh:
                cv2.circle(out, (int(pt[0]), int(pt[1])), 3, kpt_color, -1, cv2.LINE_AA)
    except Exception:
        return


def annotate(
    frame: np.ndarray,
    objects: list[TrackedObject],
    pipeline_fps: Optional[float] = None,
    device: str = "",
    zones: Optional[list] = None,
    layers: Optional[dict] = None,
    trajectories: Optional[dict] = None,
    faces: Optional[list] = None,
    poses: Optional[list] = None,
    hud: Optional[dict] = None,
) -> np.ndarray:
    """Return a NEW annotated copy of `frame`. Input is never mutated.

    zones (M7, Oscar M5 ruling): optional list of zone dicts
    {kind, zone_type, geometry{points|p1,p2}, name} in NORMALIZED
    frame coordinates — drawn server-side so an operator snapshot can
    show the breached zone. None (default) = M3 frozen surface.

    layers (V3, additive): optional {"boxes": bool, "labels": bool,
    "fps": bool, "faces": bool, "pose": bool} — partial-tolerant, missing key = default True
    (except "faces" and "pose" which default to False per V2).
    "boxes" gates rectangles AND the label chip; "labels" gates ONLY
    the " | ID n" suffix (class+conf text stays — that is the
    Track-IDs toggle); "fps" gates the HUD text; "faces" gates face overlay;
    "pose" gates human body skeleton overlay.

    trajectories (V3, additive): optional {track_id: [(x, y), ...]} —
    PIXEL foot-point 2-tuples (the session converts from TrackState's
    (x, y, tick) deque). Thin dim polyline per track; skips empty;
    never raises on malformed input. None (default) = frozen surface.

    faces (Phase 3, V2 additive): optional list of FaceDetection objects or
    face dicts. Drawn only when layers['faces'] is True (default OFF).

    poses (Phase 8, V1 additive): optional list of PoseDetection objects or
    pose dicts. Drawn only when layers['pose'] is True (default OFF)."""
    # partial-tolerant layer flags (missing key = True for base, False for faces/pose)
    lay = {"boxes": True, "labels": True, "fps": True, "faces": False, "pose": False}
    if layers:
        for k in ("boxes", "labels", "fps", "faces", "pose"):
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

    if faces and lay["faces"]:
        for f in faces:
            _draw_face(out, f)

    if poses and lay["pose"]:
        for p in poses:
            _draw_pose(out, p)

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

    # HUD: real measured values only. `hud` (decoupled playback, honest
    # metrics): {"src": fps, "play": fps, "inf": fps, "lat": ms}.
    # Legacy `pipeline_fps`/`device` remain the frozen M3 surface.
    if not lay["fps"]:
        return out
    hud_text = ""
    if hud is not None:
        src = hud.get("src")
        play = hud.get("play")
        inf = hud.get("inf")
        lat = hud.get("lat")
        if src:
            hud_text += f"SRC {float(src):.1f}"
        if play:
            hud_text += (f"  PLAY {float(play):.1f}" if hud_text
                         else f"PLAY {float(play):.1f}")
        if inf:
            hud_text += (f"  INF {float(inf):.1f}" if hud_text
                         else f"INF {float(inf):.1f}")
        if lat is not None and float(lat) > 0:
            hud_text += (f"  LAT {float(lat):.0f}ms" if hud_text
                         else f"LAT {float(lat):.0f}ms")
        if device:
            hud_text += f"  |  {device}"
        if hud_text:
            cv2.putText(out, hud_text, (10, 24), _FONT, 0.6,
                        (255, 255, 255), 2, cv2.LINE_AA)
        return out
    hud = ""
    if pipeline_fps is not None:
        hud += f"FPS {pipeline_fps:.1f}"
    if device:
        hud += f"  |  {device}"
    if hud:
        cv2.putText(out, hud, (10, 24), _FONT, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    return out
