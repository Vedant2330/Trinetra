"""TRINETRA events query + ack API (M5, §15).

GET  /api/events?session_id&type&severity&limit&before   (paginated, DESC)
POST /api/events/{id}/ack                                  -> status=acked

Ack semantics (pinned): double-ack stays 200 (idempotent); unknown id
404. Nothing else mutates event rows.
"""

from __future__ import annotations

import json
import logging

from pathlib import Path

from fastapi import APIRouter, HTTPException, Response

from backend.core import config as cfg
from backend.core.errors import get_dao
from backend.services.summary import generate_event_summary

log = logging.getLogger("trinetra.api.events")
router = APIRouter(prefix="/api/events", tags=["events"])


def _row_to_json(row) -> dict:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "source_id": row["source_id"],
        "ts": row["ts"],
        "video_ts": row["video_ts"],
        "type": row["type"],
        "severity": row["severity"],
        "confidence": row["confidence"],
        "track_ids": json.loads(row["track_ids"] or "[]"),
        "zone_id": row["zone_id"],
        "direction": row["direction"],
        "is_night": bool(row["is_night"]),
        "snapshot_path": row["snapshot_path"],
        "metadata": json.loads(row["metadata"] or "{}"),
        "status": row["status"],
    }


@router.get("")
def query_events(session_id: str = "", type: str = "", severity: str = "",
                 limit: int = 100, before: str = "",
                 before_id: str = "") -> dict:
    """A6 keyset cursor (C8): the cursor is the PAIR (before, before_id)
    — a row's (ts, id). ts collisions are real (multiple events in one
    ms; uuid4 ids give the total order), so EITHER half alone silently
    loses data (DAO skips same-ts rows on a lone `before`; ignores a
    lone `before_id`). The API therefore 400s on a HALF cursor — both
    directions — rather than serving a lie."""
    if bool(before) != bool(before_id):
        missing = "before_id" if before else "before"
        raise HTTPException(
            400, f"pagination cursor is the pair (before, before_id) — "
                 f"got only 'before'{'_id' if before else ''}; pass "
                 f"'{missing}' too (the previous page's last row has both)")
    dao = get_dao()
    rows = dao.query_events(session_id=session_id or None,
                            type_=type or None, severity=severity or None,
                            limit=limit, before=before or None,
                            before_id=before_id or None)
    events = [_row_to_json(r) for r in rows]
    return {
        "events": events,
        "count": len(events),
        # keyset cursor: pass BOTH back for the next page
        "next_before": events[-1]["ts"] if len(events) == limit else None,
        "next_before_id": events[-1]["id"] if len(events) == limit else None,
    }


@router.post("/{event_id}/ack")
def ack_event(event_id: str) -> dict:
    dao = get_dao()
    existed, newly = dao.ack_event(event_id)
    if not existed:
        raise HTTPException(404, f"event {event_id} not found")
    return {"status": "ok", "event_id": event_id, "acked": newly}


@router.get("/{event_id}/summary")
def get_event_summary_endpoint(event_id: str) -> dict:
    """Deterministic structured event audit summary (V3.5 / Phase 6).

    Answers WHAT/WHO/WHERE/WHEN/MOVEMENT/WHY/EVIDENCE from real database rows.
    """
    dao = get_dao()
    summary = generate_event_summary(dao, event_id)
    if summary is None:
        raise HTTPException(404, f"event {event_id} not found")
    return summary


@router.get("/{event_id}/snapshot")
def get_event_snapshot(event_id: str) -> Response:
    """Serve the JPEG snapshot for an event if available."""
    dao = get_dao()
    event_row = dao.get_event(event_id)
    if event_row is None:
        raise HTTPException(404, f"event {event_id} not found")

    snapshot_path = event_row["snapshot_path"]
    if not snapshot_path:
        ev_rows = dao.conn.execute("SELECT path FROM evidence WHERE event_id=?", (event_id,)).fetchall()
        if ev_rows:
            snapshot_path = ev_rows[0]["path"]

    if not snapshot_path:
        raise HTTPException(404, f"no snapshot available for event {event_id}")

    p = Path(snapshot_path)
    if not p.is_absolute():
        p = cfg.EVIDENCE_DIR / p

    try:
        resolved = p.resolve(strict=True)
        if not resolved.is_file() or resolved.is_symlink() or cfg.EVIDENCE_DIR.resolve() not in resolved.parents:
            raise HTTPException(404, "snapshot file not in evidence directory")
        data = resolved.read_bytes()
    except (OSError, RuntimeError) as e:
        raise HTTPException(404, f"snapshot file not accessible: {e}")

    return Response(
        content=data,
        media_type="image/jpeg" if resolved.suffix.lower() in (".jpg", ".jpeg") else "application/octet-stream",
        headers={"Cache-Control": "private, max-age=60"},
    )


