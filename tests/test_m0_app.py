"""TRINETRA M0 — app boot + config + health contract test (executes the real app)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from backend.core.config import DB_PATH, MODELS_DIR, VISION
from backend.main import app


def test_health() -> None:
    client = TestClient(app)
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["models"]["detector"]["present"] is True


def test_config_loads() -> None:
    assert VISION.model == "yolov8n.pt"
    assert VISION.conf == 0.35
    assert VISION.classes == [0, 1, 2, 3, 5, 7]
    assert (MODELS_DIR / VISION.model).exists()
    assert str(DB_PATH).endswith("data/trinetra.db")
