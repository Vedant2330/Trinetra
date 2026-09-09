"""TRINETRA API routers (M5, §15).

Ownership (§15): serialization + validation ONLY — logic lives in
session/db modules. Routers mount into the ONE app (backend.main).
"""

from backend.api import events, evidence, stream, zones

__all__ = ["events", "evidence", "stream", "zones"]
