"""M5 API tests — zones CRUD (NO active session, C1), events query/ack,
evidence traversal safety (C10), Oscar-5 4xx validation, health contract.

Uses the REAL app via TestClient (httpx pinned C7 drives it), with a
temp DB installed via the ApiState seam — no live session needed for
anything here (that IS the C1 acceptance).
"""

from __future__ import annotations

import json
import os
import queue
import sqlite3
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.core.errors import install, reset_for_tests
from backend.db.connection import Database
from backend.db.dao import DAO, _now
from backend.db.migrations import MIGRATIONS
from backend.events.sse import SseHub


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = Database(tmp_path / "api.db")
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    # snapshots land in a temp evidence dir
    from backend.core import config as cfg
    monkeypatch.setattr(cfg, "EVIDENCE_DIR", tmp_path / "evidence")
    from backend.events import engine as eng_mod
    monkeypatch.setattr(eng_mod, "EVIDENCE_DIR", tmp_path / "evidence")
    import backend.main as main_mod
    reset_for_tests()
    install(dao, SseHub())
    with TestClient(main_mod.app) as c:     # runs lifespan
        yield c
    reset_for_tests()
    db.close_all()


def _poly(points=None):
    points = points or [[0.1, 0.3], [0.88, 0.3], [0.88, 0.95], [0.12, 0.95]]
    return {"kind": "polygon", "points": points}


def _line(p1=(0.1, 0.6), p2=(0.9, 0.6), mode="both"):
    return {"kind": "line", "p1": list(p1), "p2": list(p2),
            "direction_mode": mode}


# ---- zones CRUD with NO active session (C1 — the acceptance) ----

def test_zones_crud_full_cycle_no_active_session(client):
    # NO session was ever started in this test — CRUD works anyway.
    r = client.post("/api/zones", json={
        "source_id": "file:running_clip.mp4", "name": "gate",
        "kind": "polygon", "type": "RESTRICTED", "geometry": _poly()})
    assert r.status_code == 201, r.text
    zid = r.json()["id"]

    # GET round-trip: exactly what was drawn (normalized coords)
    r = client.get("/api/zones", params={"source_id": "file:running_clip.mp4"})
    assert r.status_code == 200
    zs = r.json()["zones"]
    assert len(zs) == 1
    assert zs[0]["geometry"]["points"] == _poly()["points"]
    assert zs[0]["type"] == "RESTRICTED"
    assert zs[0]["active"] is True

    # PUT: partial update (rename + deactivate)
    r = client.put(f"/api/zones/{zid}", json={"name": "gate-2",
                                              "active": False})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "gate-2" and body["active"] is False

    # DELETE
    r = client.delete(f"/api/zones/{zid}")
    assert r.status_code == 200
    assert client.get("/api/zones").json()["zones"] == []
    r = client.delete(f"/api/zones/{zid}")
    assert r.status_code == 404                     # idempotent delete: 404


# ---- Oscar-5: invalid geometry -> clean 4xx (typed AND bare errors) ----

@pytest.mark.parametrize("geom,kind,detail_frag", [
    ({"kind": "polygon", "points": [[0.1, 0.2], [0.3, 0.4]]}, "polygon",
     "polygon"),                       # 2-point polygon
    ({"kind": "polygon", "points": [[0.1, 0.2], [0.3, 0.4], [2.0, 0.5]]},
     "polygon", ""),                   # coord > 1
    ({"kind": "polygon", "points": [[0.1, 0.2], [0.3, 0.4], ["a", 0.5]]},
     "polygon", ""),                   # non-numeric: bare ValueError -> 400
    ({"kind": "line", "p1": [0.5, 0.5], "p2": [0.5, 0.5]}, "line",
     "line"),                          # zero-length line
    ({"kind": "line", "p1": [0.1, 0.5], "p2": [1.4, 0.5]}, "line", ""),
    ({"kind": "line", "p1": [0.1, 0.5], "p2": [0.9, 0.5],
      "direction_mode": "sideways"}, "line", "direction_mode"),
])
def test_invalid_geometry_clean_4xx(client, geom, kind, detail_frag):
    r = client.post("/api/zones", json={
        "source_id": "s", "name": "bad", "kind": kind, "type": "WATCH",
        "geometry": geom})
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
    assert r.json()["detail"]           # actionable message present


def test_unknown_zone_404_on_update(client):
    r = client.put("/api/zones/zzz", json={"name": "x"})
    assert r.status_code == 404


# ---- zones survive restart (persistence proof, M4->M5 relocation) ----

def test_zones_survive_fresh_connection(tmp_path, monkeypatch):
    db_path = tmp_path / "persist.db"
    db = Database(db_path)
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    dao.upsert_source("file:running_clip.mp4", "file")
    dao.insert_zone("z1", "file:running_clip.mp4", "gate", "line",
                    "RESTRICTED", json.dumps(_line()))
    db.close_all()
    # fresh connection = "restart"
    db2 = Database(db_path)
    dao2 = DAO(db2)
    rows = dao2.zones_rows(source_id="file:running_clip.mp4")
    assert len(rows) == 1
    geom = json.loads(rows[0]["geometry"])
    assert geom["p1"] == [0.1, 0.6] and geom["direction_mode"] == "both"
    db2.close_all()


# ---- health (M3 contract preserved + M5 additions) ----

def test_health_contract_m5(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["models"]["detector"]["present"] is True
    assert body["db"]["ok"] is True            # M5 addition
    assert "active_session" in body            # M5 addition
    assert body["active_session"] is None      # none running in this test


# ---- events query/ack over the REAL API ----

def _insert_event(dao, source="s", type_="ZONE_ENTRY", severity="HIGH",
                  ts=None):
    eid = str(uuid.uuid4())
    dao.insert_events([(eid, None, source, ts or _now(), 12.5, type_,
                        severity, 0.9, "[1]", "z1", None, 0, None,
                        '{"reason":"RESTRICTED zone entry"}', "new")])
    return eid


def test_events_query_filters_and_ack_idempotent(client):
    from backend.core.errors import get_dao
    dao = get_dao()
    e1 = _insert_event(dao, type_="ZONE_ENTRY", severity="HIGH",
                       ts="2026-01-01T00:00:01.000+00:00")
    e2 = _insert_event(dao, type_="PERSON_DETECTED", severity="LOW",
                       ts="2026-01-01T00:00:02.000+00:00")
    e3 = _insert_event(dao, type_="ZONE_ENTRY", severity="MEDIUM",
                       ts="2026-01-01T00:00:03.000+00:00")

    # DESC default
    r = client.get("/api/events")
    body = r.json()
    assert [e["id"] for e in body["events"]] == [e3, e2, e1]
    # filter: type
    r = client.get("/api/events", params={"type": "ZONE_ENTRY"})
    assert [e["id"] for e in r.json()["events"]] == [e3, e1]
    # filter: severity
    r = client.get("/api/events", params={"severity": "HIGH"})
    assert [e["id"] for e in r.json()["events"]] == [e1]
    # pagination
    r = client.get("/api/events", params={"limit": 2})
    b = r.json()
    assert len(b["events"]) == 2 and b["next_before"] is not None
    r2 = client.get("/api/events", params={
        "limit": 2, "before": b["next_before"], "before_id": b["next_before_id"]})
    assert len({e["id"] for e in r2.json()["events"]} |
               {e["id"] for e in b["events"]}) == 3
    # severity_reason surfaced in payload
    assert r.json()["events"][0]["metadata"]["reason"] == \
        "RESTRICTED zone entry"

    # ack: idempotent — double ack stays 200, unknown 404
    r = client.post(f"/api/events/{e1}/ack")
    assert r.status_code == 200 and r.json()["acked"] is True
    r = client.post(f"/api/events/{e1}/ack")
    assert r.status_code == 200 and r.json()["acked"] is False
    r = client.get("/api/events", params={"severity": "HIGH"})
    assert r.json()["events"][0]["status"] == "acked"
    r = client.post("/api/events/nonexistent/ack")
    assert r.status_code == 404


# ---- evidence serving: traversal + row-checked (C10) ----

def test_evidence_serving_row_checked_and_traversal_safe(client, tmp_path):
    from backend.core.errors import get_dao
    dao = get_dao()
    eid = str(uuid.uuid4())
    dao.insert_events([(eid, None, "s", _now(), 0.0, "ZONE_ENTRY", "HIGH",
                        1.0, "[1]", "z1", None, 0, None, "{}", "new")])
    # register a REAL evidence row + file (as the engine would)
    evdir = tmp_path / "evidence"
    evdir.mkdir(exist_ok=True)
    f = evdir / f"{eid}.jpg"
    f.write_bytes(b"\xff\xd8SNAP\xff\xd9")
    dao.insert_evidence(eid, "snapshot", str(f))

    # legit: exact (event, filename) row match -> 200 + bytes
    r = client.get(f"/api/evidence/{eid}/{eid}.jpg")
    assert r.status_code == 200
    assert r.content == b"\xff\xd8SNAP\xff\xd9"

    # traversal set: ../, absolute, symlink, mismatched event/file
    r = client.get(f"/api/evidence/{eid}/..%2f..%2fetc%2fpasswd")
    assert r.status_code == 404
    r = client.get(f"/api/evidence/{eid}/%2e%2e%2fsecret.jpg")
    assert r.status_code == 404
    r = client.get(f"/api/evidence/{eid}/%2ftmp%2fx.jpg")
    assert r.status_code == 404
    # file exists on disk but registered under a DIFFERENT event -> 404
    other = str(uuid.uuid4())
    f2 = evdir / f"{other}.jpg"
    f2.write_bytes(b"not yours")
    r = client.get(f"/api/evidence/{eid}/{other}.jpg")
    assert r.status_code == 404
    # no row at all
    r = client.get(f"/api/evidence/nosuch/{eid}.jpg")
    assert r.status_code == 404
    # symlink attack: register row for a real file, replace with symlink
    target = tmp_path / "outside.txt"
    target.write_text("secret")
    slink = evdir / f"{other}-link.jpg"
    _insert_event(dao, ts="2026-01-01T00:00:04.000+00:00")  # any event row
    ev_for_link = dao.query_events()[0]["id"]               # its id
    # re-point: register the symlink path under ev_for_link's event
    dao.insert_evidence(ev_for_link, "snapshot", str(slink))
    os.symlink(target, slink)
    r = client.get(f"/api/evidence/{ev_for_link}/{other}-link.jpg")
    assert r.status_code == 404               # symlink refused


# ================= F1/F2/A1 FIX-PASS REGRESSION TESTS (Oscar verdict) =================

def test_f1_rest_session_start_uses_full_stack(tmp_path, monkeypatch):
    """THE F1 regression guard (fails on the pre-fix wiring, passes after):
    lifespan-composed app -> POST /api/session/start on the real clip ->
    session completes -> events EXIST in SQLite and an SSE consumer
    received a frame. The REST product path must carry the M5 machinery
    (SQLite zones, DAO, writer, hub) — not the in-memory defaults."""
    import backend.events.engine as eng_mod
    ev_dir = tmp_path / "ev"
    monkeypatch.setattr(eng_mod, "EVIDENCE_DIR", ev_dir)
    # point the app's configured DB at a temp file BEFORE lifespan runs
    from backend.core import config as cfg
    monkeypatch.setattr(cfg, "DB_PATH", tmp_path / "f1.db")

    # seed a zone + source through the DAO BEFORE the client starts
    # (lifespan honors pre-installed state)
    db = Database(tmp_path / "f1.db")
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    dao.upsert_source("file:running_clip.mp4", "file")
    dao.insert_zone("z-f1", "file:running_clip.mp4", "band", "polygon",
                    "RESTRICTED",
                    json.dumps({"kind": "polygon",
                                "points": [[0.05, 0.55], [0.95, 0.55],
                                           [0.95, 0.98], [0.05, 0.98]]}))
    hub = SseHub()
    from backend.analytics import ZoneStore
    install(dao, hub, zone_store=ZoneStore(dao=dao))

    import backend.main as main_mod
    from backend.services.session import stop_active_session
    stop_active_session()                       # clean slate
    try:
        with TestClient(main_mod.app) as client:
            # a headless SSE consumer subscribes via the hub (same object
            # the endpoint serves from); subscribe() -> (id, client)
            cid, sse_client = hub.subscribe()
            sse_q = sse_client.q

            # create the zone through the REST API too (proves CRUD ->
            # session sees it: the seeded zone already proves it; the
            # POST would 201 but the seeded one is enough)
            r = client.post("/api/session/start", json={
                "type": "file",
                "path": str(Path(__file__).parent / "assets"
                            / "running_clip.mp4")})
            assert r.status_code == 200, r.text
            body = r.json()["session"]

            # wait for EOF completion (61 frames, cpu-or-mps, <90s)
            deadline = time.time() + 90
            while time.time() < deadline:
                st = client.get("/api/session/status").json()
                sess = st["session"]
                if sess is None or sess["status"] in (
                        "completed", "error", "stopped"):
                    break
                time.sleep(0.3)
            final = client.get("/api/session/status").json()
            # the registry keeps the completed session until stopped (M3
            # behavior) — stop it, as the operator flow does
            assert final["session"]["status"] == "completed", final
            client.post("/api/session/stop")
            final = client.get("/api/session/status").json()
            assert not final["active"], final

            # F1 assertions — all would be EMPTY pre-fix:
            # (a) events persisted in SQLite
            rows = dao.query_events(limit=1000)
            assert len(rows) > 0, "no events rows — writer never wired (F1)"
            types = {r["type"] for r in rows}
            assert "PERSON_DETECTED" in types
            assert "SESSION_COMPLETED" in types
            assert "SOURCE_CONNECTED" in types
            # the REST-started session saw the SEEDED SQLITE zone:
            entries = [r for r in rows if r["type"] == "ZONE_ENTRY"]
            assert entries, "no ZONE_ENTRY — SQLite zones never wired (F1)"
            assert entries[0]["zone_id"] == "z-f1"
            # (b) SSE consumer received at least one frame
            got = []
            while True:
                try:
                    got.append(sse_q.get_nowait())
                except queue.Empty:
                    break
            assert got, "SSE hub never published — hub never wired (F1)"
            assert any(e.get("type") == "ZONE_ENTRY" for e in got)
            # (c) status_payload carries events_committed (C9 surface)
            assert body["events_committed"] >= 0
            # (d) sessions + tracks rows exist for the REST session
            sid_rows = dao.conn.execute(
                "SELECT * FROM sessions ORDER BY started_at").fetchall()
            assert sid_rows, "sessions row never written (F1)"
            n_tracks = dao.conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
            assert n_tracks > 0, "tracks rows never flushed (F1)"
            hub.unsubscribe(cid)
    finally:
        stop_active_session()
        reset_for_tests()
        db.close_all()


def test_f2_zone_id_no_collision_after_delete(client):
    """F2 regression: create 3 -> delete the middle -> create -> the new
    id is UNIQUE (200/201, no 500 from a UNIQUE violation), and ids
    across the cycle never repeat."""
    ids = []
    for i in range(3):
        r = client.post("/api/zones", json={
            "source_id": "file:clip.mp4", "name": f"z{i}",
            "kind": "polygon", "type": "WATCH", "geometry": _poly()})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    assert len(set(ids)) == 3
    # delete the middle zone
    r = client.delete(f"/api/zones/{ids[1]}")
    assert r.status_code == 200
    # create a NEW zone — count-based ids would collide (z2 reuse -> 500)
    r = client.post("/api/zones", json={
        "source_id": "file:clip.mp4", "name": "after-delete",
        "kind": "polygon", "type": "RESTRICTED", "geometry": _poly()})
    assert r.status_code == 201, f"F2 collision: {r.status_code} {r.text}"
    new_id = r.json()["id"]
    assert new_id not in ids, "id REUSED after delete (F2)"
    # list round-trip: exactly 3 zones remain, all unique
    zs = client.get("/api/zones").json()["zones"]
    assert len(zs) == 3 and len({z["id"] for z in zs}) == 3


def test_a1_zone_person_counts_thread_safe_during_mutation():
    """A1 regression: zone_person_counts() iterates a SNAPSHOT — a
    concurrent occupancy insert from another 'session thread' must not
    raise dict-changed-size (the /api/session/status 500 path)."""
    import threading
    from backend.analytics import FenceAnalytic, FrameContext, ZoneStore
    from backend.state import TrackStore
    from backend.vision import TrackedObject

    zs = ZoneStore()                       # in-memory backing (unit scope)
    zs.add("s", "z", "polygon", "RESTRICTED",
           {"points": [[0.1, 0.3], [0.9, 0.3], [0.9, 0.95], [0.1, 0.95]]})
    fence = FenceAnalytic(zs)
    fence.reset("sess")
    store = TrackStore()
    W, H = 1920, 1080
    pin = (0.5 * W, 0.6 * H)

    def c(tick):
        return FrameContext(tick=tick, wall_ts=float(tick), video_ts=0.0,
                           luminance=128.0, is_night=False, shape=(W, H))

    def obj(tid):
        return TrackedObject(track_id=tid, class_id=0, class_name="person",
                             confidence=0.9,
                             bbox=[0.5 * W - 20, 0.6 * H - 80,
                                   0.5 * W + 20, 0.6 * H])

    # mutate + poll concurrently: many NEW track keys inserted while
    # zone_person_counts() is called from the 'API thread'
    errors: list = []

    def mutator():
        for tid in range(1, 400):
            try:
                store.update([obj(tid)], tick=tid, wall_ts=float(tid))
                fence.process(c(tid), store.view())
            except Exception as e:  # pragma: no cover
                errors.append(e)

    def poller():
        for _ in range(2000):
            try:
                fence.zone_person_counts()      # the A1 read
            except Exception as e:              # RuntimeError = FAIL
                errors.append(e)

    t1 = threading.Thread(target=mutator)
    t2 = threading.Thread(target=poller)
    t1.start(); t2.start()
    t1.join(); t2.join()
    assert not errors, f"concurrent read raised: {errors[:3]}"
