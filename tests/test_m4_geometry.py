"""M4 geometry tests — pure functions (§12): ray-cast PIP, segment
intersection, side-sign, validators. Edge list from the architect's
mandatory set: concave, on-edge determinism, touching/parallel/crossing
segments, direction both ways, every validator rejection case."""

from __future__ import annotations

import math

import pytest

from backend.analytics.geometry import (
    LineGeometryError,
    PolygonGeometryError,
    point_in_polygon,
    segments_intersect,
    side_sign,
    validate_line_geometry,
    validate_polygon_geometry,
)

SQUARE = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
CONCAVE = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.5, 0.5), (0.1, 0.9)]
# concave notch on the top edge: the (0.9,0.9)->(0.5,0.5)->(0.1,0.9) chain
# carves a bite out of the upper-right region.


# ---- point in polygon ----

def test_pip_inside_outside_square():
    assert point_in_polygon((0.5, 0.5), SQUARE) is True
    assert point_in_polygon((0.95, 0.95), SQUARE) is False
    assert point_in_polygon((0.0, 0.5), SQUARE) is False


def test_pip_concave_polygon():
    # inside the body (above the notch diagonals)
    assert point_in_polygon((0.3, 0.3), CONCAVE) is True
    assert point_in_polygon((0.7, 0.7), CONCAVE) is True
    # below the notch vertex -> outside the concave hull
    assert point_in_polygon((0.5, 0.8), CONCAVE) is False
    assert point_in_polygon((0.5, 0.95), CONCAVE) is False


def test_pip_on_edge_deterministic():
    # exactly on the bottom edge + vertex: documented rule = INSIDE,
    # and the SAME answer on every call (no float-order jitter).
    for _ in range(10):
        assert point_in_polygon((0.5, 0.1), SQUARE) is True
        assert point_in_polygon((0.1, 0.1), SQUARE) is True


def test_pip_vertex_and_near_boundary():
    # every vertex counts inside (on-segment rule)
    for v in SQUARE:
        assert point_in_polygon(v, SQUARE) is True
    # just-outside epsilon below the bottom edge
    assert point_in_polygon((0.5, 0.09), SQUARE) is False


# ---- segment intersection ----

def test_segments_proper_crossing():
    a = ((0.1, 0.5), (0.9, 0.5))
    b = ((0.5, 0.1), (0.5, 0.9))
    assert segments_intersect(a, b) is True
    assert segments_intersect(b, a) is True      # symmetric


def test_segments_parallel_disjoint():
    a = ((0.1, 0.3), (0.9, 0.3))
    b = ((0.1, 0.7), (0.9, 0.7))
    assert segments_intersect(a, b) is False


def test_segments_collinear_disjoint():
    a = ((0.1, 0.5), (0.4, 0.5))
    b = ((0.6, 0.5), (0.9, 0.5))
    assert segments_intersect(a, b) is False


def test_segments_collinear_overlapping():
    a = ((0.1, 0.5), (0.5, 0.5))
    b = ((0.3, 0.5), (0.9, 0.5))
    assert segments_intersect(a, b) is True


def test_segments_endpoint_touching():
    a = ((0.1, 0.3), (0.5, 0.3))
    b = ((0.5, 0.3), (0.5, 0.9))          # T-junction: exact endpoint touch
    assert segments_intersect(a, b) is True


def test_segments_endpoint_touching_off_axis():
    a = ((0.2, 0.2), (0.4, 0.4))
    b = ((0.4, 0.4), (0.4, 0.8))
    assert segments_intersect(a, b) is True


def test_segments_no_intersection():
    a = ((0.1, 0.1), (0.3, 0.3))
    b = ((0.8, 0.8), (0.9, 0.9))
    assert segments_intersect(a, b) is False


# ---- side sign ----

def test_side_sign_left_right_on():
    line = ((0.1, 0.5), (0.9, 0.5))       # rightward arrow
    # image coords (y grows DOWN): a point above the arrow has NEGATIVE
    # cross product — sign +1/-1 convention is cross>0 => +1 (below/right
    # of arrow), cross<0 => -1 (above/left of arrow).
    assert side_sign(*line, (0.5, 0.3)) == -1   # above = left of arrow
    assert side_sign(*line, (0.5, 0.7)) == 1    # below = right of arrow
    assert side_sign(*line, (0.5, 0.5)) == 0    # on the line


def test_side_sign_flips_when_line_reversed():
    p1, p2 = (0.1, 0.5), (0.9, 0.5)
    p = (0.5, 0.3)
    assert side_sign(p1, p2, p) == -side_sign(p2, p1, p)


def test_side_sign_vertical_line():
    line = ((0.5, 0.1), (0.5, 0.9))       # downward arrow
    # cross = lx*vy - ly*vx with l=(0, +0.8): screen-left point has vx<0
    # => cross>0 => +1; screen-right => -1. (Pure right-hand rule in
    # image coords; the ARROW direction defines the sign, not the screen.)
    assert side_sign(*line, (0.3, 0.5)) == 1     # screen-left of arrow
    assert side_sign(*line, (0.7, 0.5)) == -1    # screen-right of arrow


# ---- validators: polygon ----

def test_validate_polygon_ok():
    pts = validate_polygon_geometry([[0.1, 0.3], [0.88, 0.3], [0.88, 0.95], [0.12, 0.95]])
    assert pts == [(0.1, 0.3), (0.88, 0.3), (0.88, 0.95), (0.12, 0.95)]


def test_validate_polygon_rejects_too_few_points():
    with pytest.raises(PolygonGeometryError):
        validate_polygon_geometry([[0.1, 0.2], [0.3, 0.4]])
    with pytest.raises(PolygonGeometryError):
        validate_polygon_geometry([])


def test_validate_polygon_rejects_out_of_bounds():
    with pytest.raises(PolygonGeometryError):
        validate_polygon_geometry([[0, 0], [1.2, 0.5], [0.5, 0.9]])
    with pytest.raises(PolygonGeometryError):
        validate_polygon_geometry([[0, 0], [-0.01, 0.5], [0.5, 0.9]])


def test_validate_polygon_accepts_exact_unit_bounds():
    # inclusive bounds: 0.0 and 1.0 are legal (§12)
    pts = validate_polygon_geometry([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
    assert len(pts) == 4


def test_validate_polygon_rejects_nan_inf():
    with pytest.raises(PolygonGeometryError):
        validate_polygon_geometry([[0.0, 0.0], [math.nan, 0.5], [0.5, 0.9]])
    with pytest.raises(PolygonGeometryError):
        validate_polygon_geometry([[0.0, 0.0], [math.inf, 0.5], [0.5, 0.9]])
    with pytest.raises(PolygonGeometryError):
        validate_polygon_geometry([[0.0, -math.inf], [0.5, 0.5], [0.5, 0.9]])


# ---- validators: line ----

def test_validate_line_ok():
    a, b = validate_line_geometry([0.1, 0.6], [0.9, 0.6])
    assert a == (0.1, 0.6) and b == (0.9, 0.6)


def test_validate_line_rejects_degenerate():
    with pytest.raises(LineGeometryError):
        validate_line_geometry([0.5, 0.5], [0.5, 0.5])          # identical
    with pytest.raises(LineGeometryError):
        validate_line_geometry([0.5, 0.5], [0.5005, 0.5])      # dx < 1e-3
    with pytest.raises(LineGeometryError):
        validate_line_geometry([0.5, 0.5], [0.5, 0.5009])      # dy < 1e-3


def test_validate_line_accepts_minimal_length():
    # exactly at the epsilon boundary behavior: >= 1e-3 passes
    a, b = validate_line_geometry([0.5, 0.5], [0.501, 0.5])
    assert b[0] == 0.501


def test_validate_line_rejects_out_of_bounds():
    with pytest.raises(LineGeometryError):
        validate_line_geometry([0.0, 0.0], [1.5, 0.5])
    with pytest.raises(LineGeometryError):
        validate_line_geometry([-0.2, 0.0], [0.9, 0.5])


def test_validate_line_rejects_nan_inf():
    with pytest.raises(LineGeometryError):
        validate_line_geometry([math.nan, 0.5], [0.9, 0.5])
    with pytest.raises(LineGeometryError):
        validate_line_geometry([0.1, 0.5], [math.inf, 0.5])


# ---- property-style determinism smoke ----

def test_pip_deterministic_under_repeated_calls():
    # boundary-adjacent points must be stable across calls (concordance
    # with the on-edge rule; guards against float-order regressions)
    pts = [(0.1, 0.3), (0.88, 0.3), (0.88, 0.95), (0.12, 0.95)]
    edge_pt = (0.12, 0.3)   # on the bottom edge between vertices
    results = {point_in_polygon(edge_pt, pts) for _ in range(50)}
    assert len(results) == 1
