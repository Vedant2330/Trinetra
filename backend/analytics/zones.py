"""TRINETRA ZoneStore — zones single source of truth (M4 seam, M5 SQLite).

Architecture (§12): ONE store serves the frontend (draw/edit via CRUD,
M5 REST) and the analytics. M5 swaps the backing to SQLite WITHOUT
touching FenceAnalytic — the seam is exactly this class.

Backing (C1): SQLite zones table via the DAO. The store is APP-SCOPED
(created in FastAPI lifespan, NOT per-session) — zones CRUD works with
NO active session. FenceAnalytic re-reads `zones()` EVERY tick (C2):
a zone deactivated/deleted since last tick is simply absent from the
list (active_only filter), and the fence's zone-diff purge handles its
private state. Reactivation = fresh confirm (state purged).

Coordinates: normalized [0.0–1.0] (§12) — validated by geometry.py at
construction; invalid geometry is rejected here, never at draw time.

Zone kinds: polygon (WATCH|RESTRICTED occupancy) and line (tripwire with
direction_mode both|forward|reverse). Lines ALSO carry `type` (god's
decision) — drives severity for LINE_CROSSING (RESTRICTED line = HIGH).

Reads are deterministic: ORDER BY created_at, id (C12) — fence
iteration order feeds event ordering; stable across restarts.
"""

from __future__ import annotations

import json
import uuid
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
    geometry error (4xx equivalent at the CRUD boundary)."""
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
    try:
        return (float(v[0]), float(v[1]))
    except (TypeError, ValueError) as e:
        # Oscar-5: non-numeric coords raise the TYPED error, not bare
        raise LineGeometryError(
            f"line: '{key}' coords must be numeric") from e


def _zone_from_row(row) -> Zone:
    """DB row -> Zone (geometry JSON -> validated dict)."""
    return Zone(
        id=row["id"],
        source_id=row["source_id"],
        name=row["name"] or "",
        kind=row["kind"],
        type=row["zone_type"],
        geometry=json.loads(row["geometry"]),
        active=bool(row["active"]),
    )


class ZoneStore:
    """SQLite-backed zones (M5, C1). APP-SCOPED — one instance lives in
    the FastAPI lifespan; FenceAnalytic only depends on `zones()`.

    `dao=None` keeps the M4 in-memory behavior for unit tests that have
    no DB (same public surface; the fence cannot tell the difference).
    """

    def __init__(self, dao=None) -> None:
        self._dao = dao
        self._mem: dict[str, Zone] = {}      # in-memory fallback (M4 tests)
        self._next = 1

    # ---- CRUD (both backings; DAO path raises typed geometry errors) ----

    def add(self, source_id: str, name: str, kind: str, ztype: str,
            geometry: dict, active: bool = True,
            zone_id: Optional[str] = None) -> Zone:
        """Create + store a validated zone. Raises geometry errors on
        invalid shapes (callers map them to 4xx)."""
        if ztype not in _ZONE_TYPES:
            raise ValueError(f"zone type {ztype!r} not in {_ZONE_TYPES}")
        geom = _build_geometry(geometry, kind)
        if self._dao is None:
            zid = zone_id if zone_id is not None else f"z{self._next}"
            self._next += 1
            zone = Zone(id=zid, source_id=source_id, name=name, kind=kind,
                        type=ztype, geometry=geom, active=active)
            self._mem[zid] = zone
            return zone
        zid = zone_id if zone_id is not None else \
            f"z-{uuid.uuid4()}"      # F2: uuid — count-based ids collide
                                    # after deletes (UNIQUE violation)
        self._dao.insert_zone(zid, source_id, name, kind, ztype,
                              json.dumps(geom), active)
        row = self._dao.get_zone(zid)
        return _zone_from_row(row)

    def get(self, zone_id: str) -> Optional[Zone]:
        if self._dao is None:
            return self._mem.get(zone_id)
        row = self._dao.get_zone(zone_id)
        return _zone_from_row(row) if row is not None else None

    def remove(self, zone_id: str) -> bool:
        if self._dao is None:
            return self._mem.pop(zone_id, None) is not None
        return self._dao.delete_zone(zone_id)

    def update(self, zone_id: str, **fields) -> Optional[Zone]:
        """Partial update: name/type/active/geometry (re-validated)."""
        if self._dao is None:
            zone = self._mem.get(zone_id)
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
        row = self._dao.get_zone(zone_id)
        if row is None:
            return None
        if "type" in fields:
            if fields["type"] not in _ZONE_TYPES:
                raise ValueError(f"zone type {fields['type']!r} invalid")
        self._dao.update_zone(
            zone_id,
            name=str(fields["name"]) if "name" in fields else "",
            zone_type=fields.get("type", ""),
            geometry_json=json.dumps(
                _build_geometry(fields["geometry"], row["kind"]))
            if "geometry" in fields else "",
            active=fields.get("active"))
        return self.get(zone_id)

    # ---- queries (the FenceAnalytic seam; C12 deterministic order) ----

    def zones(self, source_id: Optional[str] = None,
              active_only: bool = True) -> list[Zone]:
        """All zones (optionally for one source). The ONLY accessor
        FenceAnalytic uses — reads go through the DAO (ORDER BY
        created_at, id) or the in-memory dict in insertion order."""
        if self._dao is not None:
            rows = self._dao.zones_rows(source_id=source_id,
                                        active_only=active_only)
            return [_zone_from_row(r) for r in rows]
        out = []
        for z in self._mem.values():
            if active_only and not z.active:
                continue
            if source_id is not None and z.source_id != source_id:
                continue
            out.append(z)
        return out

    def count(self, source_id: Optional[str] = None) -> int:
        return len(self.zones(source_id, active_only=False))

    def __iter__(self) -> Iterator[Zone]:
        return iter(self.zones(active_only=False))

    def __len__(self) -> int:
        return self.count()
