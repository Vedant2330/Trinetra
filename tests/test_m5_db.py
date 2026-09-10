"""M5 database tests — migrations, pragmas, DAO, per-thread connections.

Real SQLite on a temp file (no mocks). Covers the architect's mandatory
list: fresh-db 0->1 migration, second boot no-op ON POPULATED db,
transactional failure leaves user_version untouched, per-thread
connections, WAL pragma, sessions/zones/tracks/events/evidence rows.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone

import pytest

from backend.db.connection import Database
from backend.db.dao import DAO
from backend.db.migrations import MIGRATIONS


@pytest.fixture()
def db(tmp_path):
    d = Database(tmp_path / "test.db")
    d.migrate(MIGRATIONS)
    yield d
    d.close_all()


@pytest.fixture()
def dao(db):
    return DAO(db)


# ---- migrations ----

def test_fresh_db_migrates_0_to_1(tmp_path):
    d = Database(tmp_path / "fresh.db")
    applied = d.migrate(MIGRATIONS)
    # M7 + V3.5: migrations 1 (M5 core), 2 (geo layer), 3 (trajectory) apply in order
    assert applied == 3
    assert d.user_version() == 3
    tables = {r[0] for r in
              d.conn().execute("SELECT name FROM sqlite_master"
                               " WHERE type='table'").fetchall()}
    assert {"sources", "zones", "sessions", "tracks", "events",
            "evidence"} <= tables
    assert "geo_sectors" in tables          # M7 geographic layer
    cols = {r[1] for r in d.conn().execute("PRAGMA table_info(tracks)").fetchall()}
    assert "trajectory" in cols             # Migration 3
    d.close_all()


def test_second_boot_noop_on_populated_db(tmp_path):
    """Boot 1: migrate + write rows. Boot 2 (new Database, same file):
    zero migrations applied, data intact."""
    path = tmp_path / "populated.db"
    d1 = Database(path)
    assert d1.migrate(MIGRATIONS) == 3      # M5 core + M7 geo layer + V3.5 trajectory
    dao1 = DAO(d1)
    dao1.upsert_source("file:x.mp4", "file", "uri")
    dao1.insert_session("file:x.mp4")
    dao1.insert_events([_evt_row("file:x.mp4", "PERSON_DETECTED")])
    d1.close_all()

    d2 = Database(path)
    assert d2.migrate(MIGRATIONS) == 0          # no-op
    dao2 = DAO(d2)
    assert dao2.get_source("file:x.mp4") is not None
    evs = dao2.query_events()
    assert len(evs) == 1 and evs[0]["type"] == "PERSON_DETECTED"
    d2.close_all()


def test_failed_migration_transactional_user_version_untouched(tmp_path):
    """Injected bad SQL: the migration ROLLS BACK and user_version stays
    at its previous value (0) — nothing half-applied survives; a
    subsequent CORRECT boot applies cleanly (idempotent by version)."""
    d = Database(tmp_path / "broken.db")
    bad = dict(MIGRATIONS)
    bad[1] = MIGRATIONS[1] + "\nCREATE TABLE oops(this is not valid sql);"
    with pytest.raises(sqlite3.Error):
        d.migrate(bad)
    assert d.user_version() == 0
    # transactional: NO table survived the rollback
    tables = {r[0] for r in
              d.conn().execute("SELECT name FROM sqlite_master"
                               " WHERE type='table'").fetchall()}
    assert "sources" not in tables and "oops" not in tables
    # a correct boot then succeeds from scratch
    ok = Database(tmp_path / "broken.db")
    assert ok.migrate(MIGRATIONS) == 3
    assert ok.user_version() == 3
    d.close_all()
    ok.close_all()


# ---- pragmas (C3) ----

def test_pragmas_applied_wal_normal_busy_fk(db):
    c = db.conn()
    assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert c.execute("PRAGMA synchronous").fetchone()[0] == 1  # NORMAL
    assert c.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_per_thread_connections_distinct(db):
    main = db.conn()
    other: list = []

    def worker():
        other.append(db.conn())

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert other[0] is not main
    # each is usable from its own thread only (check_same_thread trap)
    assert main.execute("SELECT 1").fetchone()[0] == 1


# ---- sessions row lifecycle (C4) ----

def test_session_row_lifecycle_insert_update(dao):
    dao.upsert_source("file:clip.mp4", "file", "/x/clip.mp4")
    sid = dao.insert_session("file:clip.mp4")
    row = dao.get_session(sid)
    assert row["status"] == "running"
    assert row["started_at"] and row["ended_at"] is None
    dao.update_session(sid, "completed", stats={"frames": 61})
    row = dao.get_session(sid)
    assert row["status"] == "completed"
    assert row["ended_at"] is not None
    assert json.loads(row["stats"])["frames"] == 61


def test_tracks_flush_aggregates(dao):
    dao.upsert_source("s1", "file")
    sid = dao.insert_session("s1")
    rows = [(1, "person", "2026-01-01T00:00:00", "2026-01-01T00:02:00",
             61, 0.92),
            (2, "car", "2026-01-01T00:00:01", "2026-01-01T00:01:00",
             30, 0.88)]
    dao.flush_tracks(sid, rows)
    got = dao.conn.execute(
        "SELECT * FROM tracks WHERE session_id=? ORDER BY track_id",
        (sid,)).fetchall()
    assert len(got) == 2
    assert got[0]["class_name"] == "person" and got[0]["max_conf"] == 0.92
    assert got[1]["frames"] == 30


# ---- zones CRUD + determinism (C1/C12) ----

def test_zones_crud_and_deterministic_order(dao):
    dao.upsert_source("s1", "file")            # FK target first
    for i in range(3):
        dao.insert_zone(f"z{i+1}", "s1", f"zone{i}", "polygon",
                        "RESTRICTED", '{"kind":"polygon","points":[]}',
                        active=(i != 2))
    rows = dao.zones_rows(source_id="s1")           # active_only default
    assert [r["id"] for r in rows] == ["z1", "z2"]  # ORDER BY created_at,id
    all_rows = dao.zones_rows(active_only=False)
    assert [r["id"] for r in all_rows] == ["z1", "z2", "z3"]
    assert dao.update_zone("z3", active=True)
    assert dao.get_zone("z3")["active"] == 1
    assert dao.delete_zone("z1") is True
    assert dao.delete_zone("z1") is False           # idempotent delete


def test_zone_fk_requires_source_row(dao):
    """zones.source_id REFERENCES sources — FK ON catches orphans (C4).
    (Direct SQL, not through insert_zone, to isolate the FK constraint.)"""
    with pytest.raises(sqlite3.IntegrityError):
        dao.conn.execute(
            "INSERT INTO zones(id, source_id, name, kind, zone_type,"
            " geometry, active, created_at, updated_at)"
            " VALUES('zX','no-such-source','x','polygon','RESTRICTED'"
            ",'{}',1,'t','t')")
        dao.conn.commit()


# ---- events: batch insert / filters / DESC / pagination / ack ----

def _evt_row(source_id, type_, ts=None, severity="LOW", status="new"):
    return (str(uuid.uuid4()), None, source_id, ts or _ts(0.0),
            0.0, type_, severity, 1.0, "[1]", None, None, 0, None,
            "{}", status)


def _ts(offset: float) -> str:
    return (datetime.fromtimestamp(1_000_000 + offset, tz=timezone.utc)
            .isoformat(timespec="milliseconds"))


def test_events_query_filters_desc_pagination_ack(dao):
    rows = [
        _evt_row("s", "PERSON_DETECTED", _ts(1), "LOW"),
        _evt_row("s", "ZONE_ENTRY", _ts(2), "HIGH"),
        _evt_row("s", "ZONE_ENTRY", _ts(3), "MEDIUM"),
        _evt_row("s", "ZONE_EXIT", _ts(4), "LOW"),
        _evt_row("s", "LINE_CROSSING", _ts(5), "MEDIUM"),
    ]
    dao.insert_events(rows)
    # DESC by default
    allq = dao.query_events()
    assert [r["type"] for r in allq] == ["LINE_CROSSING", "ZONE_EXIT",
                                         "ZONE_ENTRY", "ZONE_ENTRY",
                                         "PERSON_DETECTED"]
    # filter type
    entries = dao.query_events(type_="ZONE_ENTRY")
    assert len(entries) == 2
    # filter severity
    highs = dao.query_events(severity="HIGH")
    assert len(highs) == 1 and highs[0]["type"] == "ZONE_ENTRY"
    # pagination: limit 2 -> keyset page-through (ts + id cursor)
    page1 = dao.query_events(limit=2)
    assert len(page1) == 2
    page2 = dao.query_events(limit=2, before=page1[-1]["ts"],
                             before_id=page1[-1]["id"])
    ids = {r["id"] for r in page1 + page2}
    assert len(ids) == 4 and len(page2) == 2
    # ack: first ack flips, second stays acked (idempotent)
    eid = allq[0]["id"]
    assert dao.ack_event(eid) == (True, True)
    assert dao.ack_event(eid) == (True, False)
    assert dao.get_event(eid)["status"] == "acked"
    assert dao.ack_event("nonexistent") == (False, False)


# ---- evidence rows (C10) ----

def test_evidence_row_checked_lookup(dao):
    dao.insert_events([_evt_row("s", "ZONE_ENTRY")])
    ev = dao.query_events()[0]
    dao.insert_evidence(ev["id"], "snapshot", f"/data/evidence/{ev['id']}.jpg")
    hit = dao.evidence_for_event(ev["id"], f"{ev['id']}.jpg")
    assert hit is not None and hit["kind"] == "snapshot"
    # wrong filename / wrong event -> no row -> 404 path
    assert dao.evidence_for_event(ev["id"], "other.jpg") is None
    assert dao.evidence_for_event("nope", f"{ev['id']}.jpg") is None


# ---- retention sweep (C11) ----

def test_retention_prunes_old_evidence(dao, tmp_path):
    from backend.db.dao import _now
    old_ts = (datetime.now(timezone.utc)
              .fromtimestamp(time.time() - 30 * 86400, tz=timezone.utc)
              .isoformat(timespec="milliseconds"))
    dao.insert_events([_evt_row("s", "ZONE_ENTRY")])
    ev = dao.query_events()[0]
    f_old = tmp_path / "old.jpg"
    f_new = tmp_path / "new.jpg"
    f_old.write_bytes(b"x")
    f_new.write_bytes(b"y")
    dao.conn.execute(
        "INSERT INTO evidence(id, event_id, kind, path, created_at)"
        " VALUES(?,?,?,?,?)", ("e1", ev["id"], "snapshot", str(f_old), old_ts))
    dao.conn.execute(
        "INSERT INTO evidence(id, event_id, kind, path, created_at)"
        " VALUES(?,?,?,?,?)", ("e2", ev["id"], "snapshot", str(f_new), _now()))
    dao.conn.commit()
    removed = dao.prune_evidence(retention_days=7)
    assert removed == 1
    assert not f_old.exists() and f_new.exists()
