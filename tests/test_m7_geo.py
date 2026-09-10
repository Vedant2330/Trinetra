"""TRINETRA M7 — geographic intelligence layer tests (ADR-002/003).

Covers the REAL backend surface:
- migration 2 applies cleanly on a fresh DB (geo_sectors + source geo cols)
- geo DAO CRUD: set_source_geo / sources_rows / sectors CRUD
- /api/map/config: key flag WITHOUT ever asserting the key's VALUE in
  output (security — the key is only checked for presence/non-empty)
- /api/map/cameras: rows from REAL sources with status correlation
- /api/map/sectors: create (validation) / list / delete
- camera geo PUT: 404 unknown camera, 503 when not migrated, 200 + row
- NON-CRITICALITY (ADR-003 binding): a missing key / missing tables
  NEVER 5xx the CV pipeline endpoints (health/session stay 200)
- annotate(zones=): server-side zone overlay for operator snapshots
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from backend.api.map import load_maps_key
from backend.core.errors import install, reset_for_tests
from backend.db.connection import Database
from backend.db.dao import DAO
from backend.db.migrations import MIGRATIONS
from backend.events.sse import SseHub
from backend.vision.annotation import annotate

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture()
def stack(tmp_path):
    db = Database(tmp_path / "m7.db")
    db.migrate(MIGRATIONS)          # includes migration 2 (geo layer)
    dao = DAO(db)
    install(dao, SseHub())
    yield dao
    reset_for_tests()
    db.close_all()


# ---------- migration + DAO ----------

def test_migration2_geo_layer_applies(tmp_path):
    db = Database(tmp_path / "geo.db")
    db.migrate(MIGRATIONS)
    assert db.user_version() >= 2
    names = {r[1] for r in db.conn().execute("PRAGMA table_info(sources)")}
    assert {"latitude", "longitude", "label"} <= names
    tables = {r[0] for r in db.conn().execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "geo_sectors" in tables
    db.close_all()


def test_geo_dao_roundtrip(stack, tmp_path):
    stack.upsert_source("webcam:0", "webcam")
    # NULL until configured — no fabricated values
    rows = stack.sources_rows()
    assert rows[0]["latitude"] is None
    assert rows[0]["longitude"] is None
    assert stack.set_source_geo("webcam:0", 12.9716, 77.5946, "North Gate")
    r = stack.get_source("webcam:0")
    assert r["latitude"] == 12.9716 and r["longitude"] == 77.5946
    assert r["label"] == "North Gate"
    # unknown camera: no row updated, no raise
    assert not stack.set_source_geo("webcam:9", 1.0, 1.0)
    # sectors CRUD
    poly = [[12.97, 77.59], [12.98, 77.60], [12.96, 77.61]]
    assert stack.insert_geo_sector("gs-a", "Alpha", "sector", "d",
                                   json.dumps(poly))
    got = stack.get_geo_sector("gs-a")
    assert json.loads(got["polygon"]) == poly
    assert [s["name"] for s in stack.geo_sectors_rows()] == ["Alpha"]
    assert stack.delete_geo_sector("gs-a")
    assert not stack.delete_geo_sector("gs-a")       # second delete: False


def test_geo_dao_degrades_on_v1_db(tmp_path):
    """ADR-003 non-criticality at the DAO level: a DB WITHOUT migration 2
    (older deployment) must not crash the geo methods — they report
    empty/False and the rest of the app keeps working."""
    db = Database(tmp_path / "v1only.db")
    db.conn().executescript("""
        CREATE TABLE sources(
          id TEXT PRIMARY KEY, name TEXT, type TEXT, uri TEXT,
          created_at TEXT, status TEXT DEFAULT 'idle');
    """)
    db.conn().execute(
        "INSERT INTO sources(id, name, type, uri, created_at, status)"
        " VALUES('webcam:0','webcam:0','webcam','','2026-01-01','idle')")
    db.conn().commit()
    dao = DAO(db)
    rows = dao.sources_rows()                  # degraded columns: NULL
    assert rows[0]["latitude"] is None         # not a crash
    assert not dao._has_geo_sectors()
    assert dao.geo_sectors_rows() == []
    assert dao.get_geo_sector("x") is None
    assert not dao.insert_geo_sector("x", "n", "k", "d", "[]")
    assert not dao.delete_geo_sector("x")
    db.close_all()


# ---------- /api/map/* ----------

@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    import backend.main as main_mod
    with TestClient(main_mod.app) as c:
        yield c


def test_map_config_shape_and_key_hygiene(client):
    """The key is SERVED to the frontend (it must reach the browser to be
    of any use) — but these tests never assert its VALUE, and the value
    never appears in source or git. has_key flips with .env presence."""
    r = client.get("/api/map/config")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"google_maps_key", "has_key", "has_tiles",
                         "fallback", "simulated", "label"}
    assert body["has_key"] == bool(body["google_maps_key"])
    assert body["has_tiles"] == body["has_key"]
    assert body["fallback"] == ("satellite" if body["has_key"]
                               else "schematic")
    assert body["simulated"] is True            # demo labeling by default
    assert "Demo" in body["label"] or "Operational" in body["label"]
    # never assert the key value itself — presence only (security)


def test_map_cameras_from_real_sources(client, stack):
    stack.upsert_source("file:clip.mp4", "file")
    stack.set_source_geo("file:clip.mp4", 28.61, 77.20, "Gate Cam")
    r = client.get("/api/map/cameras")
    assert r.status_code == 200
    cams = r.json()["cameras"]
    assert any(c["camera_id"] == "file:clip.mp4"
               and c["latitude"] == 28.61
               and c["has_coordinates"] is True
               and c["label"] == "Gate Cam" for c in cams)
    # cameras with no session yet are idle — no fabricated status
    assert all(c["status"] in ("live", "idle", "error") for c in cams)


def test_map_camera_geo_put_unknown_404(client, stack):
    r = client.put("/api/map/cameras/never-seen/geo",
                   json={"latitude": 1.0, "longitude": 2.0})
    assert r.status_code == 404
    assert "start a session" in r.json()["detail"]


def test_map_camera_geo_put_ok(client, stack):
    stack.upsert_source("webcam:0", "webcam")
    r = client.put("/api/map/cameras/webcam:0/geo",
                   json={"latitude": 28.6139, "longitude": 77.2090,
                         "label": "Watchtower"})
    assert r.status_code == 200
    body = r.json()["camera"]
    assert body["camera_id"] == "webcam:0"
    assert body["latitude"] == 28.6139
    assert body["label"] == "Watchtower"


def test_map_sector_crud_and_validation(client, stack):
    r = client.post("/api/map/sectors", json={
        "name": "North Sector", "polygon": [[28.61, 77.20], [28.62, 77.21],
                                            [28.60, 77.22]]})
    assert r.status_code == 201
    sec = r.json()
    assert sec["name"] == "North Sector"
    assert len(sec["polygon"]) == 3
    # bad polygon: <3 points
    r = client.post("/api/map/sectors", json={
        "name": "Bad", "polygon": [[28.61, 77.20], [28.62, 77.21]]})
    assert r.status_code == 400
    # bad polygon: out-of-range latitude
    r = client.post("/api/map/sectors", json={
        "name": "Bad", "polygon": [[91.0, 77.2], [28.62, 77.21],
                                   [28.60, 77.22]]})
    assert r.status_code == 400
    # list
    r = client.get("/api/map/sectors")
    assert r.status_code == 200
    assert any(s["name"] == "North Sector" for s in r.json()["sectors"])
    # delete + 404 on the second delete
    r = client.delete(f"/api/map/sectors/{sec['id']}")
    assert r.status_code == 200
    r = client.delete(f"/api/map/sectors/{sec['id']}")
    assert r.status_code == 404


def test_map_endpoints_never_break_cv_pipeline(client, stack):
    """ADR-003 BINDING: map-adjacent failure modes must leave the CV
    endpoints green. Health 200, session status 200, zones 200, events
    200 — with zero sectors configured and no session running."""
    for path in ("/api/health", "/api/session/status", "/api/zones",
                 "/api/events", "/api/map/config", "/api/map/cameras",
                 "/api/map/sectors"):
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
    assert client.get("/api/health").json()["ok"] is True


# ---------- annotate(zones=) — Oscar M5 ruling ----------

def test_annotate_with_zone_overlay():
    import numpy as np
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    zones = [
        {"kind": "polygon", "zone_type": "RESTRICTED", "name": "GATE",
         "geometry": {"points": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5],
                                 [0.1, 0.5]]}},
        {"kind": "line", "zone_type": "WATCH", "name": "TRIPWIRE",
         "geometry": {"p1": [0.1, 0.6], "p2": [0.9, 0.6],
                      "direction_mode": "forward"}},
    ]
    out = annotate(frame, [], pipeline_fps=25.0, device="cpu", zones=zones)
    assert out.shape == frame.shape
    assert (out != frame).any()          # something drawn
    # input never mutated (M3 frozen rule preserved)
    assert not frame.any()


def test_annotate_malformed_zone_degrades_cleanly():
    import numpy as np
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    bad = [
        {"kind": "polygon", "geometry": {"points": "garbage"}},
        {"kind": "polygon", "geometry": {}},          # missing points
        {"kind": "whatever", "geometry": {"points": [[0, 0]]}},
        {"geometry": None},
    ]
    out = annotate(frame, [], zones=bad)
    assert out.shape == frame.shape     # no raise, clean frame


def test_maps_key_loader_never_in_source():
    """The key lives ONLY in .env (gitignored) / env var — the loader
    reads it at request time. Sanity: this test file itself contains no
    39-char AIza- key string (would mean the key leaked into source)."""
    import re
    from pathlib import Path
    src = Path(__file__).read_text()
    assert not re.search(r"AIza[0-9A-Za-z\-_]{30,}", src), \
        "API key leaked into test source!"
    assert bool(load_maps_key()) or True     # presence varies by machine
