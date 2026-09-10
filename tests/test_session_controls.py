"""Tests for TRINETRA session playback controls (pause, resume, speed, step)."""

import pytest
from fastapi.testclient import TestClient

import backend.main as main_mod
from backend.core.errors import SseHub, install
from backend.db.connection import Database
from backend.db.dao import DAO
from backend.db.migrations import MIGRATIONS
from backend.services.session import ProcessingSession, stop_active_session
from backend.sources.base import VideoSource


class _MockSource(VideoSource):
    def __init__(self):
        self.source_id = "file:mock.mp4"
        self.fps = 25.0
        self.is_live = False

    def open(self):
        return None

    def read(self):
        return None

    def release(self):
        return None


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = Database(tmp_path / "ctrl.db")
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    install(dao, SseHub())
    monkeypatch.setattr("backend.core.config.DB_PATH", db.path)
    stop_active_session()
    with TestClient(main_mod.app) as c:
        yield c
    stop_active_session()


def test_session_controls_404_when_no_session(client):
    assert client.post("/api/session/pause").status_code == 404
    assert client.post("/api/session/resume").status_code == 404
    assert client.post("/api/session/speed", json={"speed": 2.0}).status_code == 404
    assert client.post("/api/session/step").status_code == 404


def test_session_controls_with_active_session(client, monkeypatch):
    src = _MockSource()
    session = ProcessingSession(src)
    session.status = "running"
    monkeypatch.setattr("backend.main.get_active_session", lambda: session)

    # Pause
    r = client.post("/api/session/pause")
    assert r.status_code == 200
    assert r.json()["paused"] is True
    assert session.is_paused

    # Step
    r = client.post("/api/session/step")
    assert r.status_code == 200
    assert r.json()["stepped"] is True

    # Speed change
    r = client.post("/api/session/speed", json={"speed": 2.5})
    assert r.status_code == 200
    assert r.json()["speed"] == 2.5
    assert session.speed == 2.5

    # Invalid speed
    r = client.post("/api/session/speed", json={"speed": 100.0})
    assert r.status_code == 400

    # Resume
    r = client.post("/api/session/resume")
    assert r.status_code == 200
    assert r.json()["paused"] is False
    assert not session.is_paused
