"""TRINETRA analytics — per-frame state-transition modules (M4).

Design (frozen Phase 1 §11):
  - Chain = an ordered Python list of AnalyticModule instances installed by
    the session. MVP installs exactly one module: FenceAnalytic.
  - No plugin framework, no registry, no dynamic loading — a list.
  - Modules receive a read-only TrackView + FrameContext; they emit EventDraft
    lists and mutate ONLY their own private state.
"""

from backend.analytics.base import AnalyticModule, EventDraft, FrameContext
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
from backend.analytics.zones import Zone, ZoneStore

__all__ = [
    "AnalyticModule",
    "EventDraft",
    "FrameContext",
    "FenceAnalytic",
    "LineGeometryError",
    "PolygonGeometryError",
    "Zone",
    "ZoneStore",
    "point_in_polygon",
    "segments_intersect",
    "side_sign",
    "validate_line_geometry",
    "validate_polygon_geometry",
]
