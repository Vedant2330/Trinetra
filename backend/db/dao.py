"""TRINETRA DAO — thin typed SQL surface (M5, §14).

Every DB read/write in the app funnels through these methods. Raw SQL,
no ORM. Each method uses the CALLING thread's Database connection
(C3) — safe for the writer thread and API threads alike.

Scope notes (god's corrections):
  - sources row is UPSERTED at session start (zones FK target, C4).
  - sessions row lifecycle: INSERT at start / UPDATE at end (C4).
  - tracks rows = flush-at-session-end aggregates (first/last/frames/max_conf).
  - zones CRUD = the SQLite swap of the M4 in-memory seam (C1/C2/C12).
  - events insert = batch (writer thread); query = filters/DESC/pagination;
    ack = status flip, IDEMPOTENT (double-ack stays 200, C9-adjacent).
  - evidence register = snapshot bookkeeping rows (C10 row-checked serving).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.db.connection import Database

log = logging.getLogger("trinetra.db.dao")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _uuid() -> str:
    return str(uuid.uuid4())


class DAO:
    """All persistence, one class, explicit SQL."""

    def __init__(self, db: Database) -> None:
        self.db = db

    @property
    def conn(self) -> sqlite3.Connection:
        return self.db.conn()

    # ---- sources (session-start upsert, C4) ----

    def upsert_source(self, source_id: str, type_: str, uri: str = "",
                      name: str = "", status: str = "idle") -> None:
        """Insert-or-update the source row (zones FK target). Idempotent
        per session start; restart-safe."""
        self.conn.execute(
            """
            INSERT INTO sources(id, name, type, uri, created_at, status)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
              name=COALESCE(NULLIF(excluded.name,''), sources.name),
              type=excluded.type,
              uri=COALESCE(NULLIF(excluded.uri,''), sources.uri),
              status=excluded.status
            """,
            (source_id, name or source_id, type_, uri, _now(), status))
        self.conn.commit()

    def get_source(self, source_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()

    # ---- sessions (C4 lifecycle) ----

    def insert_session(self, source_id: str, session_id: str = "",
                       started_at: str = "") -> str:
        sid = session_id or _uuid()
        self.conn.execute(
            "INSERT INTO sessions(id, source_id, started_at, status, stats)"
            " VALUES(?,?,?,?,?)",
            (sid, source_id, started_at or _now(), "running", None))
        self.conn.commit()
        return sid

    def update_session(self, session_id: str, status: str,
                       stats: Optional[dict] = None,
                       ended_at: str = "") -> None:
        self.conn.execute(
            "UPDATE sessions SET ended_at=COALESCE(?, ended_at),"
            " status=?, stats=COALESCE(?, stats) WHERE id=?",
            (ended_at or _now(), status,
             json.dumps(stats) if stats is not None else None, session_id))
        self.conn.commit()

    def get_session(self, session_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()

    # ---- tracks (flush-at-end aggregates, §14) ----

    def flush_tracks(self, session_id: str, rows: list[tuple]) -> None:
        """Bulk upsert of (track_id, class_name, first_seen, last_seen,
        frames, max_conf) aggregates for one session."""
        self.conn.executemany(
            """
            INSERT INTO tracks(session_id, track_id, class_name,
                               first_seen, last_seen, frames, max_conf)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(session_id, track_id) DO UPDATE SET
              last_seen=excluded.last_seen,
              frames=excluded.frames,
              max_conf=excluded.max_conf
            """,
            [(session_id, *r) for r in rows])
        self.conn.commit()

    # ---- zones CRUD (C1/C2/C12: app-scoped, deterministic order) ----

    def insert_zone(self, zone_id: str, source_id: str, name: str,
                    kind: str, zone_type: str, geometry_json: str,
                    active: bool = True) -> None:
        now = _now()
        self.conn.execute(
            "INSERT INTO zones(id, source_id, name, kind, zone_type,"
            " geometry, active, created_at, updated_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (zone_id, source_id, name, kind, zone_type, geometry_json,
             int(active), now, now))
        self.conn.commit()

    def update_zone(self, zone_id: str, name: str = "",
                    zone_type: str = "", geometry_json: str = "",
                    active: Optional[bool] = None) -> bool:
        """Partial update; only non-empty fields change. Returns False if
        the zone id is unknown."""
        row = self.get_zone(zone_id)
        if row is None:
            return False
        self.conn.execute(
            "UPDATE zones SET name=?, zone_type=?, geometry=?, active=?,"
            " updated_at=? WHERE id=?",
            (name or row["name"], zone_type or row["zone_type"],
             geometry_json or row["geometry"],
             row["active"] if active is None else int(active),
             _now(), zone_id))
        self.conn.commit()
        return True

    def delete_zone(self, zone_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM zones WHERE id=?", (zone_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def get_zone(self, zone_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM zones WHERE id=?", (zone_id,)).fetchone()

    def zones_rows(self, source_id: Optional[str] = None,
                   active_only: bool = True) -> list[sqlite3.Row]:
        """ALL zone reads use ORDER BY created_at, id (C12 — fence event
        ordering is deterministic and stable across restarts)."""
        q = "SELECT * FROM zones"
        clauses, args = [], []
        if active_only:
            clauses.append("active=1")
        if source_id is not None:
            clauses.append("source_id=?")
            args.append(source_id)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_at, id"
        return self.conn.execute(q, args).fetchall()

    # ---- events (writer batch insert + query/ack) ----

    def insert_events(self, rows: list[tuple]) -> int:
        """Batch insert committed events. Each row =
        (id, session_id, source_id, ts, video_ts, type, severity,
        confidence, track_ids_json, zone_id, direction, is_night,
        snapshot_path, metadata_json, status).

        Single transaction per batch; failure raises (writer catches).
        """
        if not rows:
            return 0
        self.conn.executemany(
            "INSERT INTO events(id, session_id, source_id, ts, video_ts,"
            " type, severity, confidence, track_ids, zone_id, direction,"
            " is_night, snapshot_path, metadata, status)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        self.conn.commit()
        return len(rows)

    def query_events(self, session_id: str = "", type_: str = "",
                     severity: str = "", limit: int = 100,
                     before: str = "",
                     before_id: str = "") -> list[sqlite3.Row]:
        """Filter + paginate. DESC by (ts, id) — newest first. `before`
        = exclusive (ts, id) cursor for keyset pagination: pass BOTH the
        last row's ts and its id (the API wires them together)."""
        q = "SELECT * FROM events"
        clauses, args = [], []
        if session_id:
            clauses.append("session_id=?")
            args.append(session_id)
        if type_:
            clauses.append("type=?")
            args.append(type_)
        if severity:
            clauses.append("severity=?")
            args.append(severity)
        if before:
            clauses.append(
                "(ts < ? OR (ts = ? AND id < ?))")
            args.extend([before, before, before_id])
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY ts DESC, id DESC LIMIT ?"
        args.append(max(1, min(int(limit), 1000)))
        return self.conn.execute(q, args).fetchall()

    def get_event(self, event_id: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM events WHERE id=?", (event_id,)).fetchone()

    def ack_event(self, event_id: str) -> tuple[bool, bool]:
        """status -> 'acked'. Returns (existed, newly_acked). A double-ack
        returns (True, False) — idempotent, still HTTP 200."""
        row = self.get_event(event_id)
        if row is None:
            return False, False
        if row["status"] == "acked":
            return True, False
        self.conn.execute(
            "UPDATE events SET status='acked' WHERE id=?", (event_id,))
        self.conn.commit()
        return True, True

    # ---- evidence (C10: row-checked serving) ----

    def insert_evidence(self, event_id: str, kind: str, path: str) -> str:
        eid = _uuid()
        self.conn.execute(
            "INSERT INTO evidence(id, event_id, kind, path, created_at)"
            " VALUES(?,?,?,?,?)", (eid, event_id, kind, path, _now()))
        self.conn.commit()
        return eid

    def evidence_for_event(self, event_id: str,
                           filename: str) -> Optional[sqlite3.Row]:
        """Resolve (event_id, filename) -> the REGISTERED evidence row.
        Serving is only allowed on an exact row match (C10) — a file that
        exists on disk but has no matching row is a 404, not a guess."""
        return self.conn.execute(
            "SELECT * FROM evidence WHERE event_id=? AND path LIKE ?"
            " LIMIT 1",
            (event_id, f"%/{filename}")).fetchone()

    # ---- maintenance ----

    def prune_evidence(self, retention_days: int,
                       now: float | None = None) -> int:
        """One-shot startup retention sweep (C11): delete evidence rows +
        files older than retention_days. Returns files removed."""
        from backend.core.config import EVIDENCE_DIR
        cutoff = time.time() - retention_days * 86400
        rows = self.conn.execute(
            "SELECT id, path FROM evidence WHERE created_at < ?",
            (datetime.fromtimestamp(cutoff, tz=timezone.utc)
             .isoformat(timespec="milliseconds"),)).fetchall()
        removed = 0
        for r in rows:
            p = Path(r["path"])
            if p.is_file():
                try:
                    p.unlink()
                    removed += 1
                except OSError:
                    log.warning("retention: could not unlink %s", p)
            self.conn.execute("DELETE FROM evidence WHERE id=?", (r["id"],))
        self.conn.commit()
        return removed

    def health(self) -> dict[str, Any]:
        try:
            v = self.user_version()
            return {"ok": True, "user_version": v}
        except sqlite3.Error as e:  # pragma: no cover — degraded path
            return {"ok": False, "error": str(e)}

    def user_version(self) -> int:
        return self.db.user_version()
