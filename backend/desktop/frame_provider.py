"""TRINETRA Native Desktop — Low-Latency In-Memory Frame Provider (P-DESKTOP).

Subclasses QQuickImageProvider to serve live annotated surveillance frames directly
from the in-memory LatestFrameSlot and forensic event snapshots from disk/database.
Eliminates HTTP/MJPEG network overhead and disk round-trips for the native UI.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtQuick import QQuickImageProvider

from backend.core.config import PATHS, ROOT
from backend.services.session import get_active_session

log = logging.getLogger("trinetra.desktop.frame_provider")


def _create_placeholder_image(
    width: int = 640,
    height: int = 360,
    text: str = "NO ACTIVE FEED",
    subtext: str = "TRINETRA Video Analytics Console",
    bg_color: str = "#0b1329",
    border_color: str = "#1e293b",
    text_color: str = "#64748b",
) -> QImage:
    """Generate a clean dark-themed placeholder frame."""
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(QColor(bg_color))

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Outer border
    painter.setPen(QColor(border_color))
    painter.drawRect(0, 0, width - 1, height - 1)

    # Grid / crosshair aesthetics
    painter.setPen(QColor("#1e293b"))
    cx, cy = width // 2, height // 2
    painter.drawLine(cx - 30, cy, cx + 30, cy)
    painter.drawLine(cx, cy - 30, cx, cy + 30)

    # Text
    painter.setPen(QColor(text_color))
    font = QFont("monospace", 13)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(
        QRect(0, cy - 40, width, 30),
        int(Qt.AlignmentFlag.AlignCenter),
        text,
    )

    sub_font = QFont("sans-serif", 10)
    painter.setFont(sub_font)
    painter.setPen(QColor("#475569"))
    painter.drawText(
        QRect(0, cy + 15, width, 25),
        int(Qt.AlignmentFlag.AlignCenter),
        subtext,
    )

    painter.end()
    return img


class FrameImageProvider(QQuickImageProvider):
    """QQuickImageProvider delivering live frames and forensic snapshots to QML.

    QML scheme:
      - Live video feed:  "image://trinetra/live?" + frameSeq
      - Snapshot by path: "image://trinetra/snapshot/" + relativePath
      - Snapshot by ID:   "image://trinetra/event/" + eventId
    """

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)
        self._last_valid_frame: Optional[QImage] = None
        self._placeholder = _create_placeholder_image()

    def requestImage(self, id_str: str, size: QSize, requested_size: QSize) -> QImage:
        """Called by Qt Quick QML Image elements."""
        # Strip query parameter cache-busters (e.g. ?t=123456)
        path = id_str.split("?")[0].strip("/")

        # 1. Live stream frame from LatestFrameSlot
        if path == "live" or path.startswith("live/"):
            session = get_active_session()
            if session is not None and session.status in ("running", "starting"):
                jpeg_bytes = session.slot.peek()
                if jpeg_bytes:
                    img = QImage.fromData(jpeg_bytes)
                    if not img.isNull():
                        self._last_valid_frame = img
                        if requested_size.isValid() and requested_size.width() > 0 and requested_size.height() > 0:
                            return img.scaled(
                                requested_size.width(),
                                requested_size.height(),
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        return img

            # If stopped or starting with no frame yet, show last valid frame or placeholder
            if self._last_valid_frame is not None and session is not None and session.status in ("running", "starting"):
                return self._last_valid_frame

            status_text = "SESSION STOPPED" if session is None else f"SOURCE {session.status.upper()}"
            return _create_placeholder_image(text=status_text)

        # 2. Forensic snapshot from filesystem path
        if path.startswith("snapshot/"):
            rel_path = path[len("snapshot/"):]
            resolved_path = Path(rel_path)
            if not resolved_path.is_absolute():
                resolved_path = ROOT / rel_path

            if resolved_path.exists() and resolved_path.is_file():
                img = QImage(str(resolved_path))
                if not img.isNull():
                    if requested_size.isValid() and requested_size.width() > 0 and requested_size.height() > 0:
                        return img.scaled(
                            requested_size.width(),
                            requested_size.height(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    return img

            return _create_placeholder_image(
                text="SNAPSHOT MISSING",
                subtext=str(rel_path),
                bg_color="#18181b",
                border_color="#27272a",
            )

        # 3. Direct event snapshot lookup via DAO
        if path.startswith("event/"):
            event_id = path[len("event/"):]
            try:
                from backend.core.errors import get_dao
                dao = get_dao()
                ev = dao.get_event(event_id)
                if ev and ev["snapshot_path"]:
                    snap = Path(ev["snapshot_path"])
                    if not snap.is_absolute():
                        snap = ROOT / snap
                    if snap.exists():
                        img = QImage(str(snap))
                        if not img.isNull():
                            return img
            except Exception as e:
                log.warning("Failed to load snapshot for event %s: %s", event_id, e)

            return _create_placeholder_image(
                text="EVENT SNAPSHOT UNAVAILABLE",
                subtext=f"Event {event_id}",
                bg_color="#18181b",
            )

        return self._placeholder
