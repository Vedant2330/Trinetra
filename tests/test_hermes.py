"""Tests for TRINETRA Hermes reasoning service and API endpoints (P-HERMES)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.core.errors import install as api_install
from backend.db import DAO, Database
from backend.db.migrations import MIGRATIONS
from backend.events.sse import SseHub
from backend.main import app
from backend.services.hermes import (
    HermesService,
    HermesUnavailableError,
    build_hermes_context,
)


@pytest.fixture
def test_db(tmp_path):
    db_file = tmp_path / "test_hermes.db"
    database = Database(db_file)
    database.migrate(MIGRATIONS)
    dao = DAO(database)
    hub = SseHub()
    api_install(dao, hub)
    return dao


def test_build_hermes_context_empty(test_db):
    ctx = build_hermes_context(test_db, question="What is happening?")
    assert ctx["question"] == "What is happening?"
    assert ctx["event"] is None
    assert ctx["tracks"] == []
    assert ctx["zone"] is None
    assert ctx["source"] is None


def test_build_hermes_context_with_event(test_db):
    # Insert source
    test_db.upsert_source("cam-north", type_="rtsp", name="North Gate")
    test_db.set_source_geo("cam-north", latitude=28.6139, longitude=77.2090, label="North Gate")

    # Insert zone
    test_db.insert_zone(
        "z1",
        "cam-north",
        "Restricted Area",
        "polygon",
        "RESTRICTED",
        json.dumps([[10, 10], [100, 10], [100, 100], [10, 100]]),
        True,
    )

    # Insert session
    test_db.insert_session("cam-north", session_id="sess-1", started_at="2026-09-10T12:00:00Z")

    # Insert track
    traj = [{"x": 50, "y": 50, "t": 12.0}, {"x": 60, "y": 60, "t": 12.5}]
    test_db.flush_tracks(
        "sess-1",
        [(
            4,
            "person",
            "2026-09-10T12:00:00Z",
            "2026-09-10T12:00:10Z",
            30,
            0.92,
            json.dumps(traj),
        )],
    )

    # Insert event
    event_id = "ev-1001"
    meta = {
        "velocity": 12.5,
        "acceleration": 1.2,
        "straightness": 0.88,
        "global_person_id": "PID-9921",
        "identity_cameras": ["cam-north", "cam-south"],
    }
    test_db.insert_events([(
        event_id,
        "sess-1",
        "cam-north",
        "2026-09-10T12:00:05Z",
        5.0,
        "PERIMETER_BREACH",
        "CRITICAL",
        0.95,
        json.dumps([4]),
        "z1",
        "INBOUND",
        0,
        "data/evidence/test_snap.jpg",
        json.dumps(meta),
        "new",
    )])

    ctx = build_hermes_context(test_db, question="Who breached the perimeter?", event_id=event_id)

    assert ctx["event"]["id"] == event_id
    assert ctx["event"]["type"] == "PERIMETER_BREACH"
    assert ctx["event"]["severity"] == "CRITICAL"
    assert ctx["zone"]["name"] == "Restricted Area"
    assert ctx["zone"]["zone_type"] == "RESTRICTED"
    assert ctx["source"]["label"] == "North Gate"
    assert ctx["source"]["lat"] == pytest.approx(28.6139)
    assert len(ctx["tracks"]) == 1
    assert ctx["tracks"][0]["track_id"] == 4
    assert ctx["tracks"][0]["class_name"] == "person"
    assert ctx["metadata"]["global_person_id"] == "PID-9921"
    assert ctx["structured_summary"] is not None
    assert ctx["session_summary"] is not None


def test_hermes_check_status_online():
    svc = HermesService(base_url="http://mock-gateway:20128/v1")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": [{"id": "auto/glm"}, {"id": "auto/best-fast"}]}

    with patch("httpx.Client.get", return_value=mock_resp):
        status = svc.check_status(force_refresh=True)
        assert status["connected"] is True
        assert status["available_models_count"] == 2
        assert status["error"] is None


def test_hermes_check_status_offline():
    svc = HermesService(base_url="http://mock-gateway:20128/v1")
    with patch("httpx.Client.get", side_effect=httpx.ConnectError("Connection refused")):
        status = svc.check_status(force_refresh=True)
        assert status["connected"] is False
        assert "gateway_down" in status["error"]


def test_hermes_ask_success(test_db):
    svc = HermesService(base_url="http://mock-gateway:20128/v1", model="auto/glm")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "model": "z-ai/glm-5.1",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "[OBSERVED] Track #4 was detected entering zone 'Restricted Area' at 12:00:05. [DERIVED] Movement speed was 12.5 px/s.",
                }
            }
        ],
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = svc.ask(test_db, question="Summarize breach", event_id=None)
        assert "[OBSERVED]" in res["answer"]
        assert res["model"] == "z-ai/glm-5.1"
        assert "elapsed_ms" in res
        assert "context" in res


def test_hermes_ask_honest_unavailability(test_db):
    svc = HermesService(base_url="http://mock-gateway:20128/v1", model="auto/glm")

    # Connect error
    with patch("httpx.Client.post", side_effect=httpx.ConnectError("Connection refused")):
        with pytest.raises(HermesUnavailableError) as exc:
            svc.ask(test_db, question="Test")
        assert exc.value.reason == "gateway_down"

    # Timeout
    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Timed out")):
        with pytest.raises(HermesUnavailableError) as exc:
            svc.ask(test_db, question="Test")
        assert exc.value.reason == "timeout"

    # 503 Admission Busy
    mock_busy = MagicMock(status_code=503, text="chat_admission_busy")
    with patch("httpx.Client.post", return_value=mock_busy):
        with pytest.raises(HermesUnavailableError) as exc:
            svc.ask(test_db, question="Test")
        assert exc.value.reason == "busy"

    # 503 Model Cooldown
    mock_cooldown = MagicMock(
        status_code=503,
        text=json.dumps({"code": "model_cooldown", "reset_seconds": 45}),
    )
    mock_cooldown.json.return_value = {"code": "model_cooldown", "reset_seconds": 45}
    with patch("httpx.Client.post", return_value=mock_cooldown):
        with pytest.raises(HermesUnavailableError) as exc:
            svc.ask(test_db, question="Test")
        assert exc.value.reason == "model_cooldown"
        assert exc.value.retry_after_s == 45

    # 400 Bad Model
    mock_bad_model = MagicMock(status_code=400, text="Model is unavailable upstream")
    with patch("httpx.Client.post", return_value=mock_bad_model):
        with pytest.raises(HermesUnavailableError) as exc:
            svc.ask(test_db, question="Test")
        assert exc.value.reason == "bad_model"


def test_hermes_api_endpoints(test_db):
    client = TestClient(app)

    # 1. GET /api/hermes/status
    with patch("backend.api.hermes._hermes_svc.check_status", return_value={"connected": True, "model": "auto/glm", "error": None}):
        r = client.get("/api/hermes/status?force_refresh=true")
        assert r.status_code == 200
        assert r.json()["connected"] is True

    # 2. GET /api/hermes/context
    r = client.get("/api/hermes/context")
    assert r.status_code == 200
    assert "question" in r.json()

    # 3. POST /api/hermes/ask (empty question -> 400)
    r = client.post("/api/hermes/ask", json={"question": ""})
    assert r.status_code == 400

    # 4. POST /api/hermes/ask (503 when gateway is down without fallback)
    with patch("backend.api.hermes._hermes_svc.ask", side_effect=HermesUnavailableError("gateway_down", "down")):
        r = client.post("/api/hermes/ask", json={"question": "What happened?"})
        assert r.status_code == 503
        data = r.json()
        assert data["detail"]["error"] == "hermes_unavailable"
        assert data["detail"]["reason"] == "gateway_down"

    # 5. POST /api/hermes/ask (deterministic fallback when gateway is down and requested)
    with patch("backend.api.hermes._hermes_svc.ask", side_effect=HermesUnavailableError("gateway_down", "down")):
        r = client.post("/api/hermes/ask", json={"question": "Summarize this clip", "allow_deterministic_fallback": True})
        assert r.status_code == 200
        body = r.json()
        assert "[OBSERVED]" in body["answer"]
        assert body["model"] == "deterministic-sqlite-grounding"
        assert body["is_fallback"] is True
