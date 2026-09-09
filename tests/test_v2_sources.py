"""TRINETRA V2 UI integration tests — source APIs (upload/scan/list) and
session-history endpoints.

Real-workflow guarantees (V2 dispatch: 'File must reach the backend
through a REAL API — no faked completion'):
- upload of the REAL asset clip -> 200, honest fps/frame/resolution
  metadata, file stored under uploads/, path usable by session start
- upload of a text file renamed .mp4 -> 422, NOTHING kept on disk
- upload of a wrong extension -> 415 before any storage
- webcam scan never fabricates: returns only what probe_webcams opens
  (monkeypatched to a deterministic list for the test)
- GET /api/sources reflects DB rows + the live session flag
- GET /api/sessions lists real session rows newest-first
- GET /api/sessions/{id}/tracks returns the flushed §14 aggregates
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.core.errors import install, reset_for_tests
from backend.db.connection import Database
from backend.db.dao import DAO
from backend.db.migrations import MIGRATIONS
from backend.events.sse import SseHub

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

ASSETS = Path(__file__).parent / "assets"


@pytest.fixture()
def stack(tmp_path):
    db = Database(tmp_path / "v2.db")
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    install(dao, SseHub())
    yield dao
    reset_for_tests()
    db.close_all()


@pytest.fixture()
def client(tmp_path, monkeypatch, stack):
    """Lifespan-composed app on the SAME temp DB (F1 lesson: enter via
    the PRODUCT entrypoint, not a hand-built stack)."""
    from backend.core import config as cfg
    monkeypatch.setattr(cfg, "DB_PATH", stack.db.path)
    monkeypatch.setattr(cfg, "PATHS",
                        cfg.PathsCfg(uploads=str(tmp_path / "uploads"),
                                     data=str(stack.db.path.parent),
                                     retention_days=cfg.PATHS.retention_days,
                                     min_free_mb=cfg.PATHS.min_free_mb))
    import backend.main as main_mod
    from fastapi.testclient import TestClient
    from backend.services.session import stop_active_session
    stop_active_session()
    with TestClient(main_mod.app) as c:
        yield c
    stop_active_session()
    reset_for_tests()


# ---- upload ----

def test_upload_real_clip_probes_and_stores(client):
    data = open(ASSETS / "running_clip.mp4", "rb").read()
    r = client.post("/api/sources/upload",
                    files={"file": ("running_clip.mp4", data,
                                    "video/mp4")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["frame_count"] > 0 and body["fps"] > 0
    assert body["width"] > 0 and body["height"] > 0
    p = Path(body["path"])
    assert p.is_file() and p.parent.name == "uploads"
    assert p.stat().st_size == len(data)


def test_upload_text_renamed_mp4_rejected_and_deleted(client):
    r = client.post("/api/sources/upload",
                    files={"file": ("fake.mp4", b"this is not a video" * 10,
                                    "video/mp4")})
    assert r.status_code == 422, r.text
    assert "not a decodable video" in r.json()["detail"].lower()
    # nothing kept on disk
    from backend.core import config as cfg
    ups = cfg.PATHS.uploads_dir
    leftovers = [p for p in ups.iterdir() if p.name.endswith(".mp4")] \
        if ups.is_dir() else []
    assert not leftovers, f"rejected upload leaked: {leftovers}"


def test_upload_wrong_extension_415(client):
    r = client.post("/api/sources/upload",
                    files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 415, r.text


# ---- webcam scan ----

def test_webcam_scan_reports_only_real_openings(client, monkeypatch):
    import backend.api.sources as api_sources
    monkeypatch.setattr(api_sources, "_probe_indices",
                        lambda max_index=2: [0])
    r = client.post("/api/sources/webcam/scan")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"cameras": [{"index": 0, "id": "webcam:0",
                                  "status": "available"}], "count": 1}


def test_webcam_scan_no_cameras_honest_empty(client, monkeypatch):
    import backend.api.sources as api_sources
    monkeypatch.setattr(api_sources, "_probe_indices",
                        lambda max_index=2: [])
    r = client.post("/api/sources/webcam/scan")
    assert r.status_code == 200 and r.json()["count"] == 0


# ---- sources list ----

def test_list_sources_db_rows_plus_live_flag(client, stack):
    stack.upsert_source("file:running_clip.mp4", "file")
    stack.upsert_source("webcam:0", "webcam")
    r = client.get("/api/sources")
    assert r.status_code == 200, r.text
    srcs = r.json()["sources"]
    ids = {s["id"] for s in srcs}
    assert ids == {"file:running_clip.mp4", "webcam:0"}
    for s in srcs:
        assert s["live"] is False          # no active session in the test


# ---- session history ----

def test_sessions_listed_newest_first_with_stats(client, stack):
    stack.upsert_source("file:running_clip.mp4", "file")   # FK target
    s1 = stack.insert_session("file:running_clip.mp4",
                              started_at="2026-09-09T10:00:00")
    stack.update_session(s1, "completed",
                         stats={"frames_processed": 61, "pipeline_fps": 40.0})
    s2 = stack.insert_session("file:running_clip.mp4",
                              started_at="2026-09-09T11:00:00")
    r = client.get("/api/sessions")
    assert r.status_code == 200, r.text
    sessions = r.json()["sessions"]
    assert len(sessions) == 2
    assert sessions[0]["id"] == s2            # newest first
    assert sessions[1]["stats"]["frames_processed"] == 61


def test_session_tracks_returns_flushed_aggregates(client, stack):
    stack.upsert_source("file:running_clip.mp4", "file")   # FK target
    sid = stack.insert_session("file:running_clip.mp4")
    stack.flush_tracks(sid, [
        (1, "person", "2026-09-09T01:00:00", "2026-09-09T01:00:02",
         39, 0.9),
        (2, "car", "2026-09-09T01:00:00", "2026-09-09T01:00:01",
         15, 0.8),
    ])
    r = client.get(f"/api/sessions/{sid}/tracks")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == 2
    assert body["tracks"][0] == {
        "track_id": 1, "class_name": "person",
        "first_seen": "2026-09-09T01:00:00",
        "last_seen": "2026-09-09T01:00:02",
        "frames": 39, "max_conf": 0.9}
    r404 = client.get("/api/sessions/nope/tracks")
    assert r404.status_code == 404
