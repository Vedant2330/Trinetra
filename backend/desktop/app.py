"""TRINETRA PySide6 Desktop Application Bootstrapper (P-DESKTOP).

Initializes core database engine, migrations, writer, SSE hub, Re-ID service,
registers the QQuickImageProvider, and starts the native Qt Quick UI.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from backend.analytics import ZoneStore
from backend.core import config as cfg
from backend.core.config import DB_PATH, PATHS, ROOT
from backend.core.errors import _state, install
from backend.db import DAO, Database
from backend.db.migrations import MIGRATIONS
from backend.db.writer import EventWriter
from backend.desktop.bridge import TrinetraBridge
from backend.desktop.frame_provider import FrameImageProvider
from backend.events.sse import SseHub
from backend.services.session import get_writer, set_writer, stop_active_session

log = logging.getLogger("trinetra.desktop.app")


def setup_backend_services() -> tuple[DAO, SseHub, EventWriter]:
    """Bootstrap in-process SQLite database, writer, and services."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    PATHS.data_dir.mkdir(parents=True, exist_ok=True)
    (PATHS.data_dir / "evidence").mkdir(parents=True, exist_ok=True)

    database = Database(DB_PATH)
    database.migrate(MIGRATIONS)
    dao = DAO(database)
    hub = SseHub()

    writer = EventWriter(dao)
    writer.start()
    set_writer(writer)

    install(dao, hub, zone_store=ZoneStore(dao=dao))

    if cfg.REID.enabled:
        try:
            from backend.reid import MultiCameraReIdService
            _state.reid_service = MultiCameraReIdService()
            log.info("Re-ID service initialized for desktop")
        except Exception as e:
            log.warning("Re-ID service init error: %s", e)

    return dao, hub, writer


def run_desktop_app(
    argv: Optional[list[str] | str] = None, qml_path: Optional[str] = None
) -> int:
    """Main desktop application entry point."""
    if isinstance(argv, str):
        qml_path = argv
        argv = sys.argv
    elif argv is None:
        argv = sys.argv
    elif isinstance(argv, list) and len(argv) > 1 and qml_path is None:
        for arg in argv[1:]:
            if arg.endswith(".qml"):
                qml_path = arg
                break

    # Ensure high DPI scaling
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    QQuickStyle.setStyle("Basic")

    # Use QApplication because QFileDialog is used in bridge
    app = QApplication(argv)
    app.setApplicationName("TRINETRA")
    app.setOrganizationName("TRINETRA")
    app.setApplicationVersion("0.8.0-desktop")

    # Bootstrap backend services
    dao, hub, writer = setup_backend_services()

    # Create Bridge & Image Provider
    bridge = TrinetraBridge()
    frame_provider = FrameImageProvider()

    # Setup QML Application Engine
    engine = QQmlApplicationEngine()
    engine.addImageProvider("trinetra", frame_provider)

    # Expose bridge to QML root context
    root_context = engine.rootContext()
    root_context.setContextProperty("bridge", bridge)
    root_context.setContextProperty("APP_VERSION", "0.8.0-desktop")

    # Resolve main QML entry point
    if qml_path is None:
        default_qml = ROOT / "qml" / "main.qml"
        qml_path = str(default_qml)

    resolved_qml = Path(qml_path).resolve()
    if not resolved_qml.exists():
        log.error("QML entry point not found: %s", resolved_qml)
        print(f"Error: QML entry point not found at {resolved_qml}", file=sys.stderr)
        return 1

    # Load QML
    engine.load(str(resolved_qml))

    if not engine.rootObjects():
        log.error("Failed to load QML root objects")
        return 1

    # Handle OS interrupts (Ctrl+C)
    def _sigint_handler(*_):
        log.info("SIGINT received — exiting desktop app")
        bridge.shutdown()
        app.quit()

    signal.signal(signal.SIGINT, _sigint_handler)

    # Run Qt Event Loop
    exit_code = app.exec()

    # Teardown
    log.info("Desktop app exiting, cleaning up...")
    bridge.shutdown()
    stop_active_session()
    if writer:
        writer.stop()

    return exit_code
