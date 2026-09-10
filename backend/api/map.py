"""TRINETRA geographic/map API (M7, ADR-002/ADR-003).

GET  /api/map/config    — Google Maps key (from .env via the §19
                           reserved loader), key-presence flag, fallback
                           state, demo labeling.
GET  /api/map/cameras    — camera registry w/ lat/lng when configured
                           (NULL when not — no fabricated coordinates).
PUT  /api/map/cameras/{id}/geo — attach real coordinates to a camera.
GET  /api/map/sectors    — geographic operational sectors (lat/lng
                           polygons — DISTINCT from M4 video zones).
POST /api/map/sectors    — create a geo sector.
DELETE /api/map/sectors/{id} — remove a geo sector.

SECURITY (ADR-003): the key is read from .env at REQUEST time and handed
to the frontend over the local socket; it NEVER appears in source, in
git, or in logs. Non-criticality (binding): every endpoint degrades to
an empty/schematic answer — a missing key, missing migration, or a dead
Google Maps NEVER 5xx-crashes the CV/event pipeline.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.core.errors import get_dao

log = logging.getLogger("trinetra.api.map")
router = APIRouter(prefix="/api/map", tags=["map"])

# §19 reserved 10-line loader — the key lives in .env (chmod 600,
# gitignored, NEVER committed, never logged).
_ROOT = Path(__file__).resolve().parents[2]


def load_maps_key() -> str:
    env_file = _ROOT / ".env"
    try:
        for line in env_file.read_text().splitlines():
            if line.startswith("GOOGLE_MAPS_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                return key
    except OSError:
        pass
    import os
    return os.environ.get("GOOGLE_MAPS_API_KEY", "")


def _simulated_labeling() -> tuple[bool, str]:
    """Honest labeling (ADR-002): unless a real deployment set
    TRINETRA_REAL_GEO=1 in .env, coordinates shown are DEMO —
    'Demo Operational Area' / 'Simulated Camera Deployment'."""
    try:
        for line in (_ROOT / ".env").read_text().splitlines():
            if line.startswith("TRINETRA_REAL_GEO=1"):
                return False, "Operational Area"
    except OSError:
        pass
    return True, "Demo Operational Area (Simulated Camera Deployment)"


@router.get("/config")
def map_config() -> dict:
    key = load_maps_key()
    simulated, label = _simulated_labeling()
    return {
        "google_maps_key": key,
        "has_key": bool(key),
        "has_tiles": bool(key),     # no key → frontend skips tiles outright
        "fallback": "satellite" if key else "schematic",
        "simulated": simulated,
        "label": label,
    }


@router.get("/cameras")
def map_cameras() -> dict:
    """Camera registry with coordinates when configured. lat/lng stay
    NULL (rendered as null) when never set — the frontend then parks
    the marker on the schematic, honestly unplaced."""
    dao = get_dao()
    from backend.services import get_active_session
    active = get_active_session()
    active_id = active.source_id if active is not None else None
    cameras = []
    for r in dao.sources_rows():
        keys = set(r.keys())            # sqlite Row: keys() is a METHOD
        lat = r["latitude"] if "latitude" in keys else None
        lng = r["longitude"] if "longitude" in keys else None
        status = "live" if r["id"] == active_id else (
            "error" if r["status"] == "error" else "idle")
        cameras.append({
            "camera_id": r["id"],
            "source_id": r["id"],
            "label": (r["label"] if "label" in keys and r["label"]
                      else (r["name"] or r["id"])),
            "latitude": lat,
            "longitude": lng,
            "has_coordinates": lat is not None and lng is not None,
            "status": status,
            "type": r["type"],
        })
    return {"cameras": cameras}


class CameraGeo(BaseModel):
    latitude: float
    longitude: float
    label: str = ""


@router.put("/cameras/{source_id}/geo")
def set_camera_geo(source_id: str, req: CameraGeo) -> dict:
    """Attach real coordinates to a known camera (source row). 404 when
    the camera has never been seen (no source row); 503 when the geo
    migration has not been applied."""
    if not (-90 <= req.latitude <= 90 and -180 <= req.longitude <= 180):
        raise HTTPException(400, f"invalid coordinates "
                                 f"({req.latitude}, {req.longitude}) — "
                                 f"latitude -90..90, longitude -180..180")
    dao = get_dao()
    if dao.get_source(source_id) is None:
        raise HTTPException(404, f"camera {source_id} unknown — start a "
                                 f"session on it first (row is created at "
                                 f"session start)")
    if not dao.set_source_geo(source_id, req.latitude, req.longitude,
                              req.label):
        raise HTTPException(503, "geo columns not migrated — restart the "
                                 "server to apply migration 2")
    row = dao.get_source(source_id)
    return {"status": "ok", "camera": {
        "camera_id": source_id,
        "latitude": row["latitude"], "longitude": row["longitude"],
        "label": row["label"] or source_id}}


class SectorCreate(BaseModel):
    name: str
    kind: str = "sector"
    description: str = ""
    polygon: list[list[float]]      # [[lat,lng], ...] >= 3 points
    active: bool = True


def _sector_json(r) -> dict:
    return {
        "id": r["id"], "name": r["name"], "kind": r["kind"],
        "description": r["description"],
        "polygon": json.loads(r["polygon"] or "[]"),
        "active": bool(r["active"]),
    }


@router.get("/sectors")
def list_sectors(active_only: bool = False) -> dict:
    dao = get_dao()
    return {"sectors": [_sector_json(r)
                        for r in dao.geo_sectors_rows(active_only)]}


@router.post("/sectors", status_code=201)
def create_sector(req: SectorCreate) -> dict:
    dao = get_dao()
    if len(req.polygon) < 3:
        raise HTTPException(400, "polygon needs >= 3 [lat,lng] points")
    for pt in req.polygon:
        if (not isinstance(pt, (list, tuple)) or len(pt) != 2
                or not -90 <= float(pt[0]) <= 90
                or not -180 <= float(pt[1]) <= 180):
            raise HTTPException(400, f"bad point {pt!r} — "
                                     f"[latitude -90..90, longitude "
                                     f"-180..180]")
    sector_id = f"gs-{uuid.uuid4()}"
    if not dao.insert_geo_sector(sector_id, req.name, req.kind,
                                  req.description, json.dumps(req.polygon),
                                  req.active):
        raise HTTPException(503, "geo_sectors not migrated — restart the "
                                 "server to apply migration 2")
    row = dao.get_geo_sector(sector_id)
    return _sector_json(row)


@router.delete("/sectors/{sector_id}")
def delete_sector(sector_id: str) -> dict:
    dao = get_dao()
    if not dao.delete_geo_sector(sector_id):
        raise HTTPException(404, f"sector {sector_id} not found")
    return {"status": "ok", "deleted": sector_id}
