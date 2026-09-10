"""Shared API state — the app-scoped holders wired by lifespan (C1).

The FastAPI lifespan creates: Database, DAO, EventWriter, SseHub,
ZoneStore(SQLite-backed). Routers fetch them via get_dao()/get_hub();
the session-start endpoint passes the WHOLE stack into ProcessingSession
(F1 fix — the REST product path must see the M5 machinery, not the
in-memory defaults). No module-level globals initialized at import time —
the lifespan is the single composition root (testable: tests call
install() with their own DAO/hub; production main.py installs the real
ones at startup).
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException

from backend.analytics.zones import ZoneStore
from backend.db.dao import DAO
from backend.events.sse import SseHub


class ApiState:
    """Mutable holder installed once by lifespan (or per-test)."""

    def __init__(self) -> None:
        self.dao: Optional[DAO] = None
        self.hub: Optional[SseHub] = None
        self.zone_store: Optional[ZoneStore] = None
        self.reid_service: Optional[object] = None   # Phase 2 (lazy type)

    def install(self, dao: DAO, hub: Optional[SseHub] = None,
                zone_store: Optional[ZoneStore] = None) -> None:
        self.dao = dao
        self.hub = hub or SseHub()
        self.zone_store = zone_store if zone_store is not None \
            else ZoneStore(dao=dao)

    def clear(self) -> None:
        self.dao = None
        self.hub = None
        self.zone_store = None
        self.reid_service = None


_state = ApiState()


def get_dao() -> DAO:
    if _state.dao is None:
        raise HTTPException(
            503, "database not initialized (lifespan not run)")
    return _state.dao


def get_hub() -> SseHub:
    if _state.hub is None:
        raise HTTPException(
            503, "SSE hub not initialized (lifespan not run)")
    return _state.hub


def get_zone_store() -> ZoneStore:
    if _state.zone_store is None:
        raise HTTPException(
            503, "zone store not initialized (lifespan not run)")
    return _state.zone_store


def get_reid_service():
    """Phase 2: the app-scoped MultiCameraReIdService (None when the
    capability is disabled or not yet initialized — honest absence)."""
    return _state.reid_service


def install(dao: DAO, hub: Optional[SseHub] = None,
            zone_store: Optional[ZoneStore] = None) -> None:
    """Composition hook for main.lifespan AND tests."""
    _state.install(dao, hub, zone_store)


def reset_for_tests() -> None:
    _state.clear()


def zone_not_found(row, zone_id: str) -> None:
    if row is None:
        raise HTTPException(404, f"zone {zone_id} not found")
