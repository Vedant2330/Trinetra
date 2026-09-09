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
        out.append({
            "id": r["id"], "name": r["name"] or r["id"],
            "type": r["type"], "status": r["status"],
            "live": r["id"] == active_id,
            "created_at": r["created_at"],
        })
    return {"sources": out}


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
    frames, max confidence, class. These are the REAL measurements the
    Investigation page is allowed to show."""
    dao = get_dao()
    row = dao.get_session(session_id)
    if row is None:
        raise HTTPException(404, f"session {session_id} not found")
    rows = dao.conn.execute(
        "SELECT track_id, class_name, first_seen, last_seen, frames,"
        " max_conf FROM tracks WHERE session_id=? ORDER BY track_id",
        (session_id,)).fetchall()
    tracks = [{
        "track_id": r["track_id"], "class_name": r["class_name"],
        "first_seen": r["first_seen"], "last_seen": r["last_seen"],
        "frames": r["frames"], "max_conf": round(r["max_conf"], 3),
    } for r in rows]
    return {"session_id": session_id, "tracks": tracks,
            "count": len(tracks)}
