"""TRINETRA zones CRUD API (M5, §15).

GET  /api/zones?source_id=     -> list (single source of truth)
POST /api/zones                -> create (validated geometry)
PUT  /api/zones/{id}           -> partial update (name/type/active/geometry)
DELETE /api/zones/{id}         -> remove

CRUD works with NO active session (C1): zones live in SQLite app-wide,
created in lifespan; the fence re-reads zones each tick (C2).

Validation errors — Oscar-5: BOTH typed geometry errors (2-point
polygon, zero-length line, coords>1) AND bare ValueError (non-numeric
coords) map to clean 400 with the actionable message. Malformed JSON
bodies (missing fields, wrong shape) are also 400, not 500.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.analytics.geometry import (
    LineGeometryError,
    PolygonGeometryError,
)
from backend.core.errors import ApiState, get_dao, zone_not_found

log = logging.getLogger("trinetra.api.zones")
router = APIRouter(prefix="/api/zones", tags=["zones"])


class ZoneCreate(BaseModel):
    source_id: str
    name: str = ""
    kind: str                       # "polygon" | "line"
    type: str = "RESTRICTED"        # WATCH | RESTRICTED (both kinds)
    geometry: dict                  # §12 JSON (validated)
    active: bool = True


class ZoneUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    active: bool | None = None
    geometry: dict | None = None


def _row_to_json(row) -> dict:
    return {
        "id": row["id"],
        "source_id": row["source_id"],
        "name": row["name"],
        "kind": row["kind"],
        "type": row["zone_type"],
        "geometry": json.loads(row["geometry"]),
        "active": bool(row["active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _validate_geometry(raw: dict, kind: str) -> str:
    """Route validation through the SAME geometry validators the fence
    uses (§12 single source of truth). Raises HTTP 400 on any invalid
    input — typed OR bare errors (Oscar-5)."""
    try:
        from backend.analytics.zones import _build_geometry
        built = _build_geometry(raw, kind)
        return json.dumps(built)
    except (PolygonGeometryError, LineGeometryError, ValueError,
            TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("")
def list_zones(source_id: str = "") -> dict:
    dao = get_dao()
    rows = dao.zones_rows(source_id=source_id or None, active_only=False)
    return {"zones": [_row_to_json(r) for r in rows]}


@router.post("", status_code=201)
def create_zone(req: ZoneCreate) -> dict:
    dao = get_dao()
    if req.kind not in ("polygon", "line"):
        raise HTTPException(400, f"kind must be 'polygon' or 'line', "
                                 f"got {req.kind!r}")
    if req.type not in ("WATCH", "RESTRICTED"):
        raise HTTPException(400, f"type must be WATCH or RESTRICTED, "
                                 f"got {req.type!r}")
    geometry_json = _validate_geometry(req.geometry, req.kind)
    # FK target: the source row must exist before the zone row (C4 —
    # the CRUD surface upserts it; sessions do the same at start)
    src = dao.get_source(req.source_id)
    if src is None:
        stype = "webcam" if "webcam" in req.source_id else "file"
        dao.upsert_source(req.source_id, stype)
    # F2: uuid4 ids — f"z{count+1}" collides after deletes
    # (z1,z2,z3 -> delete z2 -> create -> UNIQUE violation -> 500).
    zone_id = f"z-{uuid.uuid4()}"
    dao.insert_zone(zone_id, req.source_id, req.name, req.kind, req.type,
                    geometry_json, req.active)
    row = dao.get_zone(zone_id)
    zone_not_found(row, zone_id)
    return _row_to_json(row)


@router.put("/{zone_id}")
def update_zone(zone_id: str, req: ZoneUpdate) -> dict:
    dao = get_dao()
    row = dao.get_zone(zone_id)
    zone_not_found(row, zone_id)
    geometry_json = ""
    if req.geometry is not None:
        geometry_json = _validate_geometry(req.geometry, row["kind"])
    if req.type is not None and req.type not in ("WATCH", "RESTRICTED"):
        raise HTTPException(400, f"type must be WATCH or RESTRICTED, "
                                 f"got {req.type!r}")
    updated = dao.update_zone(zone_id, name=req.name or "",
                              zone_type=req.type or "",
                              geometry_json=geometry_json,
                              active=req.active)
    if not updated:
        raise HTTPException(404, f"zone {zone_id} not found")
    return _row_to_json(dao.get_zone(zone_id))


@router.delete("/{zone_id}")
def delete_zone(zone_id: str) -> dict:
    dao = get_dao()
    if not dao.delete_zone(zone_id):
        raise HTTPException(404, f"zone {zone_id} not found")
    return {"status": "ok", "deleted": zone_id}
