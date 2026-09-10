"""TRINETRA analytics — per-frame state-transition modules (M4).

Design (frozen Phase 1 §11):
  - Chain = an ordered Python list of AnalyticModule instances installed by
    the session. MVP installs exactly one module: FenceAnalytic.
  - No plugin framework, no registry, no dynamic loading — a list.
  - Modules receive a read-only TrackView + FrameContext; they emit EventDraft
    lists and mutate ONLY their own private state.
"""

from backend.analytics.anpr import (
    ANPRAnalytic,
    classify_anpr_read,
    clean_plate_text,
    locate_plate_heuristic,
    validate_indian_plate,
)
from backend.analytics.base import AnalyticModule, EventDraft, FrameContext
from backend.analytics.crowd import CrowdDensityAnalytic
from backend.analytics.fence import FenceAnalytic
from backend.analytics.geometry import (
    LineGeometryError,
    PolygonGeometryError,
    point_in_polygon,
    segments_intersect,
    side_sign,
    validate_line_geometry,
    validate_polygon_geometry,
)
from backend.analytics.kinematics import KinematicTrajectoryAnalytic
from backend.analytics.zones import Zone, ZoneStore

__all__ = [
    "ANPRAnalytic",
    "AnalyticModule",
    "CrowdDensityAnalytic",
    "EventDraft",
    "FrameContext",
    "FenceAnalytic",
    "KinematicTrajectoryAnalytic",
    "LineGeometryError",
    "PolygonGeometryError",
    "Zone",
    "ZoneStore",
    "classify_anpr_read",
    "clean_plate_text",
    "locate_plate_heuristic",
    "point_in_polygon",
    "segments_intersect",
    "side_sign",
    "validate_indian_plate",
    "validate_line_geometry",
    "validate_polygon_geometry",
]
