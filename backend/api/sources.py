"""TRINETRA source-integration API (V2 UI, IMPLEMENTATION_PLAN §15/M1
'POST /uploads' + 'POST /sources/webcam/scan' contracts, adapted to the
M5+ app shape).

Endpoints:
  POST /api/sources/webcam/scan   — enumerate cameras that ACTUALLY open
                                    (backend.sources.probe_webcams)
  POST /api/sources/upload        — multipart upload (mp4/mov), probe-
                                    validated by FileSource.open(), stored
                                    under PATHS.uploads_dir; returns the
                                    server path for /api/session/start
  GET  /api/sources               — known sources (rows) + live flags
  GET  /api/sessions              — session history (id, source, status,
                                    started/ended, stats) for Investigation
  GET  /api/sessions/{id}/tracks  — flushed track aggregates for a session

No fake devices: scan reports only what opens; upload accepts only what
FileSource can decode (a text file renamed .mp4 -> 4xx, nothing stored).
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from backend.core import config as cfg
from backend.core.errors import get_dao

log = logging.getLogger("trinetra.api.sources")
router = APIRouter(prefix="/api/sources", tags=["sources"])
sessions_router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# §15 M1 upload contract: mp4/mov ≤ 500 MB (probe does the real check)
_MAX_UPLOAD_BYTES = 500 * 1024 * 1024
_EXT_OK = (".mp4", ".mov", ".m4v")
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_name(name: str) -> str:
    """Sanitize ONLY the filename component; collisions get a uuid infix."""
    base = _SAFE_NAME.sub("_", Path(name).name) or "upload.mp4"
    return f"{uuid.uuid4().hex[:6]}_{base}"


@router.post("/webcam/scan")
async def webcam_scan() -> dict:
    """Bounded probe of indices 0..2 (probe_webcams opens + grabs one
    frame; macOS enumeration is best-effort by design). Returns the
    indices that ACTUALLY deliver frames — never a guessed list."""
    try:
        indices = await run_in_threadpool(_probe_indices)
    except Exception as e:  # noqa: BLE001 — enumeration must never 5xx
        raise HTTPException(503, f"camera probe failed: {e}") from e
    cameras = [{"index": i, "id": f"webcam:{i}",
                "status": "available"} for i in indices]
    return {"cameras": cameras, "count": len(cameras)}


def _probe_indices(max_index: int = 2) -> list[int]:
    from backend.sources.webcam import probe_webcams
    return probe_webcams(max_index)


@router.post("/upload")
async def upload_video(file: UploadFile = File(...)) -> dict:
    """Real upload: stream to uploads/, validate with FileSource.open()
    (the SAME probe a session start runs — one source of truth), then
    report real metadata (size, fps, frames, resolution). Invalid files
    are DELETED and 4xx'd with an actionable reason."""
    if not file.filename or not file.filename.lower().endswith(_EXT_OK):
        raise HTTPException(
            415, f"unsupported file type — use one of {list(_EXT_OK)}")
    dest_dir = cfg.PATHS.uploads_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _safe_name(file.filename)
    try:
        size = 0
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        413, f"file exceeds 500 MB limit ({size} bytes so far)")
                out.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    except OSError as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(500, f"storage failed: {e}") from e
    finally:
        await file.close()

    # probe-validate with the REAL source (early reject, M1 contract)
    try:
        meta = await run_in_threadpool(_probe_file, dest)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    return {
        "status": "ok",
        "filename": dest.name,
        "path": str(dest),
        "size_bytes": size,
        "fps": meta["fps"],
        "frame_count": meta["frame_count"],
        "width": meta["width"],
        "height": meta["height"],
    }


def _probe_file(path: Path) -> dict:
    """Open-and-rewind via FileSource (same probe a session start uses).
    Raises HTTPException 4xx with the actionable SourceError message."""
    import cv2
    from backend.sources.file import FileSource
    from backend.sources.base import SourceError
    try:
        src = FileSource(path)
        src.open()
        w, h = src.size
        return {"fps": round(src.fps, 2), "frame_count": src.frame_count,
                "width": w, "height": h}
    except SourceError as e:
        raise HTTPException(422, f"not a decodable video: {e}") from e
    except Exception as e:  # noqa: BLE001 — cv2 blew up unexpectedly
        raise HTTPException(422, f"cannot decode file: {e}") from e


class SourceCreateRequest(BaseModel):
    id: str
    name: str | None = None
    type: str = "rtsp"
    uri: str | None = ""
    latitude: float | None = None
    longitude: float | None = None
    label: str | None = None
    status: str = "idle"


@router.get("")
def list_sources() -> dict:
    """Known sources (rows from the DB) + a live flag from the active
    session — the Sources page consumes exactly this."""
    from backend.services import get_active_session
    dao = get_dao()
    active_id = None
    session = get_active_session()
    if session is not None:
        active_id = session.source_id
    out = []
    for r in dao.sources_rows():
        keys = set(r.keys())
        out.append({
            "id": r["id"], "name": r["name"] or r["id"],
            "type": r["type"], "status": r["status"],
            "live": r["id"] == active_id,
            "created_at": r["created_at"],
            "latitude": r["latitude"] if "latitude" in keys else None,
            "longitude": r["longitude"] if "longitude" in keys else None,
            "label": r["label"] if "label" in keys else None,
        })
    return {"sources": out}


@router.post("", status_code=201)
def register_source(req: SourceCreateRequest) -> dict:
    """Register or update a camera source with optional geographical coordinates."""
    dao = get_dao()
    sid = req.id.strip()
    if not sid:
        raise HTTPException(400, "source id cannot be empty")
    dao.upsert_source(
        sid,
        type_=req.type.strip() or "rtsp",
        uri=req.uri or "",
        name=req.name or sid,
        status=req.status or "idle",
    )
    if req.latitude is not None and req.longitude is not None:
        if not (-90 <= req.latitude <= 90 and -180 <= req.longitude <= 180):
            raise HTTPException(400, f"invalid coordinates ({req.latitude}, {req.longitude}) — latitude -90..90, longitude -180..180")
        dao.set_source_geo(sid, req.latitude, req.longitude, req.label or req.name or sid)
    row = dao.get_source(sid)
    keys = set(row.keys()) if row else set()
    return {
        "status": "ok",
        "source": {
            "id": row["id"] if row else sid,
            "name": row["name"] if row else sid,
            "type": row["type"] if row else req.type,
            "status": row["status"] if row else req.status,
            "latitude": row["latitude"] if "latitude" in keys else None,
            "longitude": row["longitude"] if "longitude" in keys else None,
            "label": row["label"] if "label" in keys else None,
        },
    }


@router.post("/seed-demo")
def seed_demo_sources() -> dict:
    """Idempotently seed 8 standard demo cameras and 2 perimeter sectors around command coordinates (28.6139, 77.2090)."""
    dao = get_dao()
    demo_cams = [
        {"id": "CAM-01", "name": "North Gate Command", "type": "demo", "lat": 28.6139, "lng": 77.2090, "label": "North Gate Post", "status": "demo"},
        {"id": "CAM-02", "name": "Perimeter West Tower", "type": "demo", "lat": 28.6145, "lng": 77.2075, "label": "Fence West Alpha", "status": "demo"},
        {"id": "CAM-03", "name": "Outpost Delta Access", "type": "demo", "lat": 28.6128, "lng": 77.2105, "label": "Outpost Delta", "status": "demo"},
        {"id": "CAM-04", "name": "Watchtower Sector 2", "type": "demo", "lat": 28.6152, "lng": 77.2112, "label": "Watchtower 2", "status": "demo"},
        {"id": "CAM-05", "name": "Depot Logistics Entry", "type": "demo", "lat": 28.6122, "lng": 77.2078, "label": "Depot Entrance", "status": "demo"},
        {"id": "CAM-06", "name": "South Checkpoint Barrier", "type": "demo", "lat": 28.6115, "lng": 77.2095, "label": "South Checkpoint", "status": "demo"},
        {"id": "CAM-07", "name": "East Perimeter Fence", "type": "demo", "lat": 28.6148, "lng": 77.2120, "label": "Fence East Bravo", "status": "demo"},
        {"id": "CAM-08", "name": "Helipad Approach", "type": "demo", "lat": 28.6120, "lng": 77.2110, "label": "Helipad Cam", "status": "demo"},
    ]
    seeded = []
    for c in demo_cams:
        dao.upsert_source(c["id"], type_=c["type"], name=c["name"], status=c["status"])
        dao.set_source_geo(c["id"], latitude=c["lat"], longitude=c["lng"], label=c["label"])
        seeded.append(c["id"])

    # Seed sectors if none exist
    existing_sectors = dao.geo_sectors_rows()
    if not existing_sectors:
        sec1 = [[28.6130, 77.2070], [28.6155, 77.2070], [28.6155, 77.2115], [28.6130, 77.2115]]
        sec2 = [[28.6110, 77.2055], [28.6165, 77.2055], [28.6165, 77.2125], [28.6110, 77.2125]]
        dao.insert_geo_sector("gs-alpha", "Command Restricted Zone", "sector", "High-security inner perimeter", json.dumps(sec1), True)
        dao.insert_geo_sector("gs-bravo", "Perimeter Buffer Zone", "sector", "Outer perimeter surveillance zone", json.dumps(sec2), True)

    return {"status": "ok", "seeded_cameras": seeded, "count": len(seeded)}


# ---- session history (Investigation page) ----

@sessions_router.get("")
def list_sessions(limit: int = 50) -> dict:
    """Session history, newest first — the Investigation page picks a
    session from here (stats JSON included when the session flushed)."""
    dao = get_dao()
    rows = dao.conn.execute(
        "SELECT id, source_id, status, started_at, ended_at, stats"
        " FROM sessions ORDER BY started_at DESC LIMIT ?",
        (max(1, min(limit, 500)),)).fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r["id"], "source_id": r["source_id"],
            "status": r["status"], "started_at": r["started_at"],
            "ended_at": r["ended_at"],
            "stats": json.loads(r["stats"]) if r["stats"] else None,
        })
    return {"sessions": out, "count": len(out)}


@sessions_router.get("/{session_id}/tracks")
def session_tracks(session_id: str) -> dict:
    """Flushed track aggregates (§14) for one session — first/last seen,
    frames, max confidence, class, and optional persisted trajectory."""
    dao = get_dao()
    row = dao.get_session(session_id)
    if row is None:
        raise HTTPException(404, f"session {session_id} not found")
    rows = dao.get_tracks(session_id)
    tracks = []
    for r in rows:
        traj = None
        if "trajectory" in r.keys() and r["trajectory"]:
            try:
                traj = json.loads(r["trajectory"])
            except Exception:
                traj = None
        t_entry = {
            "track_id": r["track_id"],
            "class_name": r["class_name"],
            "first_seen": r["first_seen"],
            "last_seen": r["last_seen"],
            "frames": r["frames"],
            "max_conf": round(r["max_conf"], 3),
        }
        if traj is not None:
            t_entry["trajectory"] = traj
        tracks.append(t_entry)
    return {"session_id": session_id, "tracks": tracks,
            "count": len(tracks)}


@sessions_router.get("/{session_id}/summary")
def session_summary(session_id: str) -> dict:
    """Deterministic session audit summary (V3.5 / Task 5.2)."""
    from backend.services.summary import generate_session_summary
    dao = get_dao()
    summary = generate_session_summary(dao, session_id)
    if summary is None:
        raise HTTPException(404, f"session {session_id} not found")
    return summary

