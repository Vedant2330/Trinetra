"""TRINETRA fence geometry — pure functions, normalized frame space (M4).

All coordinates are NORMALIZED [0.0–1.0] frame space (§12): the frontend
canvas and this backend consume identical numbers. Standard math,
reimplemented in own words (audited VFE / AGPL repos are reference only —
no code copied; "standard ray-cast / debounce geometry").

Determinism rules:
  - point_in_polygon: ray-cast, concave-safe; on-edge is resolved by a
    documented epsilon-based on-segment check so a foot point exactly on
    a boundary yields the SAME answer every call (no float-order jitter).
  - side_sign: sign of the 2D cross product (line vector × point vector);
    +1 / -1 / 0 (zero = on the line's infinite extension).
"""

from __future__ import annotations

import math
from typing import Sequence

Point = tuple[float, float]           # (x, y) normalized
Segment = tuple[Point, Point]

_EPS = 1e-9                           # geometric zero tolerance (normalized space)


class PolygonGeometryError(ValueError):
    """Invalid polygon zone geometry (degenerate / out-of-range / non-finite)."""


class LineGeometryError(ValueError):
    """Invalid line zone geometry (p1≈p2 / out-of-range / non-finite)."""


# ---- side sign -----------------------------------------------------------

def side_sign(p1: Point, p2: Point, p: Point) -> int:
    """Sign of cross((p2-p1), (p-p1)) — which side of line p1->p2 p is on.

    +1 = left of the directed line, -1 = right, 0 = on the line
    (within epsilon). Pure; direction-aware (swap p1/p2 flips the sign).
    """
    lx, ly = p2[0] - p1[0], p2[1] - p1[1]
    vx, vy = p[0] - p1[0], p[1] - p1[1]
    cross = lx * vy - ly * vx
    if cross > _EPS:
        return 1
    if cross < -_EPS:
        return -1
    return 0


# ---- point in polygon ----------------------------------------------------

def _on_segment(a: Point, b: Point, p: Point, eps: float = 1e-9) -> bool:
    """p within eps of segment a-b (collinear assumed not required)."""
    # distance point-to-segment, squared compare — deterministic on-edge test
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= eps * eps:
        return math.hypot(px - ax, py - ay) <= eps
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy) <= eps


def point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """Ray-cast point-in-polygon, concave-safe (§12).

    On-edge (within epsilon): counted as INSIDE, deterministically —
    the on-segment check runs before the ray cast, so a boundary point
    never depends on ray-crossing float order.
    """
    n = len(polygon)
    px, py = point
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if _on_segment(polygon[i], polygon[j], point):
            return True                      # on-edge => inside (documented rule)
        # ray-cast (crossing number): toggle when the edge straddles the
        # horizontal ray at py, and the intersection is right of px.
        if (yi > py) != (yj > py):
            x_int = xi + (py - yi) * (xj - xi) / (yj - yi)
            if x_int > px:
                inside = not inside
        j = i
    return inside


# ---- segment intersection -----------------------------------------------

def segments_intersect(a: Segment, b: Segment) -> bool:
    """True when segments a and b share at least one point (§12).

    Handles: proper crossing, endpoint touching, collinear overlap.
    Parallel non-overlapping segments return False.
    """
    (ax1, ay1), (ax2, ay2) = a
    (bx1, by1), (bx2, by2) = b

    d1 = _cross(bx1, by1, bx2, by2, ax1, ay1)
    d2 = _cross(bx1, by1, bx2, by2, ax2, ay2)
    d3 = _cross(ax1, ay1, ax2, ay2, bx1, by1)
    d4 = _cross(ax1, ay1, ax2, ay2, bx2, by2)

    if ((d1 > _EPS and d2 < -_EPS) or (d1 < -_EPS and d2 > _EPS)) and \
       ((d3 > _EPS and d4 < -_EPS) or (d3 < -_EPS and d4 > _EPS)):
        return True                          # proper crossing

    # touching / collinear cases: zero cross + on-segment
    if abs(d1) <= _EPS and _on_segment((bx1, by1), (bx2, by2), (ax1, ay1)):
        return True
    if abs(d2) <= _EPS and _on_segment((bx1, by1), (bx2, by2), (ax2, ay2)):
        return True
    if abs(d3) <= _EPS and _on_segment((ax1, ay1), (ax2, ay2), (bx1, by1)):
        return True
    if abs(d4) <= _EPS and _on_segment((ax1, ay1), (ax2, ay2), (bx2, by2)):
        return True
    return False                             # parallel, apart


def _cross(ox: float, oy: float, ax: float, ay: float,
           px: float, py: float) -> float:
    """cross((a-o), (p-o)) — raw value, epsilon-free (caller decides)."""
    return (ax - ox) * (py - oy) - (ay - oy) * (px - ox)


# ---- validators ----------------------------------------------------------

def _finite_coords(*pts: Point, what: str) -> None:
    for p in pts:
        for v in p:
            if not math.isfinite(v):
                raise _geom_error(what, f"non-finite coordinate {v!r}")


def _in_unit_range(*pts: Point, what: str) -> None:
    for p in pts:
        for v in p:
            if v < 0.0 or v > 1.0:           # inclusive bounds (§12)
                raise _geom_error(what, f"coordinate {v!r} outside [0,1]")


def _geom_error(what: str, why: str) -> ValueError:
    return PolygonGeometryError(f"{what}: {why}") if what == "polygon" \
        else LineGeometryError(f"{what}: {why}")


def validate_polygon_geometry(points: Sequence[Sequence[float]]) -> list[Point]:
    """Validate + normalize polygon points. Rejects (§12):
    <3 points, non-finite coords, coords outside [0,1] (inclusive bounds).
    Returns a list of (x, y) tuples.
    """
    pts: list[Point] = [(float(p[0]), float(p[1])) for p in points]
    if len(pts) < 3:
        raise PolygonGeometryError(
            f"polygon: {len(pts)} points (<3 — degenerate)")
    _finite_coords(*pts, what="polygon")
    _in_unit_range(*pts, what="polygon")
    return pts


def validate_line_geometry(p1: Sequence[float],
                           p2: Sequence[float]) -> tuple[Point, Point]:
    """Validate tripwire endpoints. Rejects (§12): p1≈p2 (degenerate line,
    epsilon max(|dx|,|dy|) < 1e-3), non-finite, out-of-[0,1] coords."""
    a = (float(p1[0]), float(p1[1]))
    b = (float(p2[0]), float(p2[1]))
    _finite_coords(a, b, what="line")
    _in_unit_range(a, b, what="line")
    eps = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    if eps < 1e-3:                          # frozen epsilon (§12 zero-length rule)
        raise LineGeometryError(
            f"line: p1≈p2 (max delta {eps:.6f} < 1e-3 — zero-length)")
    return a, b
