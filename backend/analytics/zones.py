"""TRINETRA ZoneStore — zones single source of truth, M4 in-memory seam.

Architecture (§12): ONE store serves the frontend (draw/edit via CRUD,
M5/M6 REST) and the analytics. M4 keeps it in-memory; M5 swaps the backing
to SQLite WITHOUT touching FenceAnalytic — the seam is exactly this class.

Coordinates: normalized [0.0–1.0] (§12) — validated by geometry.py at
construction; invalid geometry is rejected here, never at draw time.

Zone kinds: polygon (WATCH|RESTRICTED occupancy) and line (tripwire with
direction_mode both|forward|reverse). Lines ALSO carry `type` now (god's
decision) — drives severity for LINE_CROSSING (RESTRICTED line = HIGH).
"""

from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from typing import Iterator, Optional

from backend.analytics.geometry import (
    LineGeometryError,
    PolygonGeometryError,
    validate_line_geometry,
    validate_polygon_geometry,
)

_ZONE_TYPES = ("WATCH", "RESTRICTED")
_DIRECTION_MODES = ("both", "forward", "reverse")


@dataclass
class Zone:
    """One virtual-fence zone (polygon) or tripwire (line)."""

    id: str
    source_id: str
    name: str
    kind: str                        # "polygon" | "line"
    type: str                        # WATCH | RESTRICTED (both kinds)
    geometry: dict                    # §12 minimal JSON (validated)
    active: bool = True

    # ---- derived (validated at construction, cheap access after) ----

    @property
    def polygon_points(self) -> list[tuple[float, float]]:
        """Validated polygon points (kind == 'polygon')."""
        return validate_polygon_geometry(self.geometry["points"])

    @property
    def line_ends(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Validated (p1, p2) (kind == 'line')."""
        return validate_line_geometry(self.geometry["p1"], self.geometry["p2"])

    @property
    def direction_mode(self) -> str:
        """Tripwire direction filter (kind == 'line')."""
        return self.geometry.get("direction_mode", "both")


def _build_geometry(raw: dict, kind: str) -> dict:
    """Validate raw geometry dict for the given kind. Raises the matching
    geometry error (4xx equivalent at the future CRUD boundary)."""
    if kind == "polygon":
        pts = raw.get("points")
        if not isinstance(pts, (list, tuple)) or not pts:
            raise PolygonGeometryError("polygon: missing/empty 'points'")
        if not all(isinstance(p, (list, tuple)) and len(p) == 2 for p in pts):
            raise PolygonGeometryError("polygon: points must be [x, y] pairs")
        cleaned = validate_polygon_geometry(pts)
        return {"kind": "polygon",
                "points": [[x, y] for (x, y) in cleaned]}
    if kind == "line":
        p1 = _p(raw, "p1")
        p2 = _p(raw, "p2")
        a, b = validate_line_geometry(p1, p2)
        mode = raw.get("direction_mode", "both")
        if mode not in _DIRECTION_MODES:
            raise LineGeometryError(
                f"line: direction_mode {mode!r} not in {_DIRECTION_MODES}")
        return {"kind": "line", "p1": list(a), "p2": list(b),
                "direction_mode": mode}
    raise ValueError(f"unknown zone kind: {kind!r} (use 'polygon' or 'line')")


def _p(raw: dict, key: str) -> tuple[float, float]:
    v = raw.get(key)
    if not isinstance(v, (list, tuple)) or len(v) != 2:
        raise LineGeometryError(f"line: '{key}' must be an [x, y] pair")
    return (float(v[0]), float(v[1]))


class ZoneStore:
    """In-memory zones (M4). M5 swaps backing to SQLite; FenceAnalytic
    only depends on `zones()` — that is the seam."""

    def __init__(self) -> None:
        self._zones: dict[str, Zone] = {}
        self._ids = itertools.count(1)

    # ---- CRUD ----

    def add(self, source_id: str, name: str, kind: str, ztype: str,
            geometry: dict, active: bool = True,
            zone_id: Optional[str] = None) -> Zone:
        """Create + store a validated zone. Raises geometry errors on
        invalid shapes (callers map them to 4xx)."""
        if ztype not in _ZONE_TYPES:
            raise ValueError(f"zone type {ztype!r} not in {_ZONE_TYPES}")
        geom = _build_geometry(geometry, kind)
        zid = zone_id if zone_id is not None else f"z{next(self._ids)}"
        zone = Zone(id=zid, source_id=source_id, name=name, kind=kind,
                    type=ztype, geometry=geom, active=active)
        self._zones[zid] = zone
        return zone

    def get(self, zone_id: str) -> Optional[Zone]:
        return self._zones.get(zone_id)

    def remove(self, zone_id: str) -> bool:
        return self._zones.pop(zone_id, None) is not None

    def update(self, zone_id: str, **fields) -> Optional[Zone]:
        """Partial update: name/type/active/geometry (re-validated)."""
        zone = self._zones.get(zone_id)
        if zone is None:
            return None
        if "type" in fields:
            if fields["type"] not in _ZONE_TYPES:
                raise ValueError(f"zone type {fields['type']!r} invalid")
            zone.type = fields["type"]
        if "name" in fields:
            zone.name = str(fields["name"])
        if "active" in fields:
            zone.active = bool(fields["active"])
        if "geometry" in fields:
            zone.geometry = _build_geometry(fields["geometry"], zone.kind)
        return zone

    # ---- queries (the FenceAnalytic seam) ----

    def zones(self, source_id: Optional[str] = None,
              active_only: bool = True) -> list[Zone]:
        """All zones (optionally for one source). The ONLY accessor
        FenceAnalytic uses — M5's SQLite backing reimplements it."""
        out = []
        for z in self._zones.values():
            if active_only and not z.active:
                continue
            if source_id is not None and z.source_id != source_id:
                continue
            out.append(z)
        return out

    def count(self, source_id: Optional[str] = None) -> int:
        return len(self.zones(source_id, active_only=False))

    def __iter__(self) -> Iterator[Zone]:
        return iter(self._zones.values())

    def __len__(self) -> int:
        return len(self._zones)
