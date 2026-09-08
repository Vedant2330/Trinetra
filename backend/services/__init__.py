"""TRINETRA services — session orchestration + frame sharing (M3)."""

from backend.services.frame_slot import LatestFrameSlot
from backend.services.session import (
    ProcessingSession,
    SessionError,
    get_active_session,
    make_source,
    start_session,
    stop_active_session,
)

__all__ = [
    "LatestFrameSlot",
    "ProcessingSession",
    "SessionError",
    "get_active_session",
    "make_source",
    "start_session",
    "stop_active_session",
]
