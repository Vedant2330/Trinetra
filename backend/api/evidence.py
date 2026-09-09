"""TRINETRA evidence file serving API (M5, §15, C10).

GET /api/evidence/{event_id}/{file}

DB-CHECKED, not dir-listing (C10): the (event_id, filename) pair must
resolve to a REGISTERED evidence row whose stored path ENDS with the
requested filename; only then is the file served from EVIDENCE_DIR.
Traversal (../, absolute, symlink), mismatches, unknown rows → 404.
"""

from __future__ import annotations

import logging
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException, Response

from backend.core import config as cfg
from backend.core.errors import get_dao

log = logging.getLogger("trinetra.api.evidence")
router = APIRouter(prefix="/api/evidence", tags=["evidence"])


def _reject(name: str) -> None:
    raise HTTPException(404, "evidence not found")


@router.get("/{event_id}/{file}")
def serve_evidence(event_id: str, file: str) -> Response:
    dao = get_dao()

    # 1. filename sanity: single path segment, no traversal, no absolute,
    #    no symlink tricks, and a real extension
    p = PurePosixPath(file)
    if (len(p.parts) != 1 or p.is_absolute() or file in (".", "..")
            or ".." in file or "/" in file or "\\" in file
            or file.startswith(".") or not p.suffix):
        _reject(file)

    # 2. DB-checked: the (event_id, filename) pair must match a
    #    REGISTERED evidence row (C10) — never a disk listing
    row = dao.evidence_for_event(event_id, file)
    if row is None:
        _reject(file)
    registered = Path(row["path"])
    if registered.name != file:
        _reject(file)

    # 3. resolve + verify: inside EVIDENCE_DIR, regular file, NOT a symlink
    evidence_dir = cfg.EVIDENCE_DIR
    try:
        resolved = registered.resolve(strict=True)
        if (not resolved.is_file() or resolved.is_symlink()
                or evidence_dir.resolve() not in resolved.parents):
            _reject(file)
    except (OSError, RuntimeError):
        _reject(file)

    # 4. serve
    try:
        data = resolved.read_bytes()
    except OSError:
        _reject(file)
    return Response(
        content=data,
        media_type="image/jpeg" if resolved.suffix == ".jpg" else
        "application/octet-stream",
        headers={"Cache-Control": "private, max-age=60"})
