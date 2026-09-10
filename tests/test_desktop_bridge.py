from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QCoreApplication, QSize
from PySide6.QtGui import QImage, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from backend.db.connection import Database
from backend.db.dao import DAO
from backend.db.migrations import MIGRATIONS
from backend.desktop.bridge import TrinetraBridge
from backend.desktop.frame_provider import FrameImageProvider
from backend.services.hermes import HermesService, HermesUnavailableError


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QGuiApplication exists for Qt Quick / PySide6 tests."""
    app = QGuiApplication.instance()
    if app is None:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QGuiApplication([])
    return app


@pytest.fixture
def temp_db(tmp_path):
    db = Database(tmp_path / "test_bridge.db")
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    yield dao, db
    db.close_all()


def test_frame_image_provider_placeholder(qapp):
    provider = FrameImageProvider()
    img = provider.requestImage("live", QSize(), QSize())
    assert isinstance(img, QImage)
    assert not img.isNull()
    assert img.width() > 0
    assert img.height() > 0


def test_frame_image_provider_snapshot_missing(qapp):
    provider = FrameImageProvider()
    img = provider.requestImage("snapshot/non_existent_path.jpg", QSize(), QSize())
    assert isinstance(img, QImage)
    assert not img.isNull()


def test_frame_image_provider_snapshot_existing(qapp, tmp_path):
    img_file = tmp_path / "test_snap.jpg"
    test_qimg = QImage(100, 100, QImage.Format.Format_RGB32)
    test_qimg.fill(0xFF00FF)
    test_qimg.save(str(img_file))

    provider = FrameImageProvider()
    img = provider.requestImage(f"snapshot/{img_file}", QSize(), QSize())
    assert isinstance(img, QImage)
    assert not img.isNull()
    assert img.width() == 100
    assert img.height() == 100


def test_bridge_layers_management(qapp):
    bridge = TrinetraBridge()
    layers = bridge.getLayers()
    assert isinstance(layers, dict)
    assert "boxes" in layers
    assert layers["boxes"] is True

    # Test toggle
    bridge.toggleLayer("boxes")
    assert bridge.getLayers()["boxes"] is False
    bridge.toggleLayer("boxes")
    assert bridge.getLayers()["boxes"] is True


def test_bridge_zone_management(qapp, temp_db):
    dao, db = temp_db
    dao.upsert_source(
        source_id="cam_desk_1",
        type_="file",
        uri="test.mp4",
        name="Desk Camera",
        status="active",
    )
    with patch("backend.desktop.bridge.get_dao", return_value=dao):
        bridge = TrinetraBridge()
        initial_count = len(bridge.loadZones())

        # Add zone
        z_id = "test_zone_01"
        saved = bridge.savePolygonZone(
            zone_id=z_id,
            source_id="cam_desk_1",
            name="Test Restricted Zone",
            zone_type="RESTRICTED",
            coords_json=json.dumps([[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]]),
            active=True,
        )
        assert saved is True
        zones = bridge.loadZones()
        assert len(zones) == initial_count + 1

        # Delete zone
        deleted = bridge.deleteZone(z_id)
        assert deleted is True
        assert len(bridge.loadZones()) == initial_count


def test_bridge_event_operations(qapp, temp_db):
    dao, db = temp_db
    dao.upsert_source(
        source_id="cam_desk_1",
        type_="file",
        uri="test.mp4",
        name="Desk Camera",
        status="active",
    )
    dao.insert_session(source_id="cam_desk_1", session_id="session_01")

    ev_id = "ev_desktop_test_01"
    # id, session_id, source_id, ts, video_ts, type, severity, confidence, track_ids, zone_id, direction, is_night, snapshot_path, metadata, status
    dao.insert_events([
        (
            ev_id,
            "session_01",
            "cam_desk_1",
            "2026-09-10T12:00:00Z",
            12.5,
            "TRIPWIRE",
            "HIGH",
            0.95,
            "[1, 2]",
            "zone_gate",
            "entering",
            0,
            None,
            '{"rule": "line_cross", "reason": "Perimeter crossed"}',
            "new",
        )
    ])

    bridge = TrinetraBridge()
    with patch("backend.desktop.bridge.get_dao", return_value=dao):
        events = bridge.loadEvents(limit=10, offset=0)
        assert len(events) >= 1
        found = [e for e in events if e.get("id") == ev_id]
        assert len(found) == 1
        assert found[0]["type"] == "TRIPWIRE"

        detail = bridge.getEventDetail(ev_id)
        assert detail.get("id") == ev_id

        # Update status
        bridge.updateEventStatus(ev_id, "reviewed")
        detail_after = bridge.getEventDetail(ev_id)
        assert detail_after.get("status") == "reviewed"

        # 7-W Summary
        summary = bridge.generate7WSummary(ev_id)
        assert "event_id" in summary
        assert "structured" in summary
        assert summary["structured"]["what"]["type"] == "TRIPWIRE"


def test_bridge_system_health(qapp, temp_db):
    dao, db = temp_db
    with patch("backend.desktop.bridge.get_dao", return_value=dao):
        bridge = TrinetraBridge()
        health = bridge.getSystemHealth()
        assert isinstance(health, dict)
        assert "ok" in health
        assert "detector_present" in health
        assert "db_ok" in health
        assert "device_policy" in health


def test_bridge_hermes_offline_dispatch(qapp, temp_db):
    dao, db = temp_db
    with patch("backend.desktop.bridge.get_dao", return_value=dao):
        bridge = TrinetraBridge()
        hermes_svc = HermesService(base_url="http://127.0.0.1:20128/v1", model="auto/glm")
        bridge.set_hermes_service(hermes_svc)

        received_err = []
        bridge.hermesErrorOccurred.connect(lambda err: received_err.append(err))

        with patch.object(
            hermes_svc,
            "ask",
            side_effect=HermesUnavailableError(
                reason="HERMES_GATEWAY_OFFLINE", message="Gateway offline"
            ),
        ):
            bridge.askHermes(
                question="Is there an intrusion?",
                event_id="",
                session_id="",
                model="",
            )
            # Allow thread pool execution
            for _ in range(25):
                QCoreApplication.processEvents()
                if received_err:
                    break
                time.sleep(0.05)

        assert len(received_err) == 1
        assert received_err[0]["reason"] == "HERMES_GATEWAY_OFFLINE"


def test_qml_engine_load_main(qapp):
    """Verify QML files can be loaded by QQmlApplicationEngine without syntax/import errors."""
    engine = QQmlApplicationEngine()
    qml_dir = Path(__file__).resolve().parent.parent / "qml"
    engine.addImportPath(str(qml_dir))

    provider = FrameImageProvider()
    engine.addImageProvider("trinetra", provider)

    bridge = TrinetraBridge()
    engine.rootContext().setContextProperty("bridge", bridge)

    main_qml = qml_dir / "main.qml"
    engine.load(str(main_qml))

    root_objs = engine.rootObjects()
    assert len(root_objs) > 0, "Failed to instantiate root objects from main.qml"
