"""TRINETRA event engine — draft -> committed event (M5, §13, step 8).

One call per processed tick: commit(drafts, annotated_jpeg, ctx).

Layers (frozen §13):
  1. PERSON/VEHICLE_DETECTED drafts arrive from the SESSION (structural
     once-per-track via take_newly_confirmed) — they are NOT in the
     cooldown map at all (A2).
  2. Cooldown backstop per (type, track_id, zone_id) — suppress iff
     Δt < cooldown STRICTLY; Δt == 10.0s is ALLOWED (pinned A2).
  3. Severity ladder INFO<LOW<MEDIUM<HIGH, stacking CAPS at HIGH;
     reasons concatenate into severity_reason (A3):
       - ZONE_ENTRY: WATCH=MEDIUM, RESTRICTED=HIGH
       - ZONE_EXIT: LOW (no modifiers, pinned A3)
       - LINE_CROSSING: base MEDIUM; +1 if line RESTRICTED; +1 night
       - PERSON/VEHICLE_DETECTED: LOW
       - SOURCE_* / SESSION_COMPLETED: INFO (system, jpeg=None A1)
  4. Snapshot: severity >= snapshot_min_severity (MEDIUM) -> evidence
     file; bytes are the SAME annotated JPEG the slot publishes (A1:
     evidence == operator's view, no re-encode). System events: no file.

Engine state (C8): per-session cooldown map + committed counter; the
session calls reset(session_id) at start; same track_id in a NEW session
re-fires PERSON_DETECTED.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

from backend.analytics.base import EventDraft, FrameContext
from backend.core.config import EVENTS, EVIDENCE_DIR

log = logging.getLogger("trinetra.events")

_SEVERITY_ORDER = ("INFO", "LOW", "MEDIUM", "HIGH")
_SYSTEM_TYPES = frozenset({
    "SOURCE_CONNECTED", "SOURCE_LOST", "SESSION_COMPLETED"})
_DETECT_TYPES = {
    "person": "PERSON_DETECTED", "vehicle": "VEHICLE_DETECTED",
}
_VEHICLE_CLASSES = frozenset(
    {"bicycle", "car", "motorcycle", "bus", "truck"})


@dataclass(frozen=True)
class CommittedEvent:
    """A committed event — exactly the §14 events-row shape (minus id)."""
    type: str
    session_id: str
    source_id: str
    ts: str                       # ISO wall-clock
    video_ts: Optional[float]
    severity: str
    confidence: float
    track_ids: list[int]
    zone_id: Optional[str]
    direction: Optional[str]
    is_night: bool
    snapshot_path: Optional[str]
    metadata: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.metadata["_id"]

    def sse_json(self) -> dict:
        """What /api/stream/events sends (§15/§16 payload)."""
        return {
            "id": self.metadata["_id"],
            "type": self.type,
            "severity": self.severity,
            "ts": self.ts,
            "video_ts": self.video_ts,
            "session_id": self.session_id,
            "source_id": self.source_id,
            "track_ids": self.track_ids,
            "zone_id": self.zone_id,
            "direction": self.direction,
            "is_night": self.is_night,
            "confidence": round(self.confidence, 3),
            "snapshot_path": self.snapshot_path,
            "severity_reason": self.metadata.get("severity_reason", ""),
            "metadata": {k: v for k, v in self.metadata.items()
                         if not k.startswith("_")},
        }


def _clamp(sev: str) -> str:
    return sev if sev in _SEVERITY_ORDER else "LOW"


def _raise(sev: str, steps: int) -> str:
    return _SEVERITY_ORDER[
        min(_SEVERITY_ORDER.index(_clamp(sev)) + steps,
            len(_SEVERITY_ORDER) - 1)]     # CAP at HIGH (A3)


class EventEngine:
    """Per-session state machine (C8). Thread-confined to the session
    thread except hub publish (hub is thread-safe)."""

    def __init__(self, source_id: str, session_id: str,
                 writer=None, hub=None, dao=None) -> None:
        self._source_id = source_id
        self._session_id = session_id
        self._writer = writer            # enqueue(row) — may be None (tests)
        self._hub = hub                  # SseHub — may be None (tests)
        self._dao = dao                  # evidence registration (C10)
        self._cooldown: dict[tuple, float] = {}
        self._lock = threading.Lock()    # guards cooldown map only
        self.committed = 0

    # ---- state (C8) ----

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._cooldown.clear()
            self.committed = 0
        self._session_id = session_id

    # ---- pipeline step 8 (§3) ----

    def commit(self, drafts: list[EventDraft],
               annotated_jpeg: Optional[bytes],
               ctx: FrameContext) -> list[CommittedEvent]:
        """Commit this tick's drafts. Returns the committed events
        (tests + B3 counting). `annotated_jpeg` = the SAME buffer the
        slot gets (A1) — None only for system events (A1)."""
        out: list[CommittedEvent] = []
        for draft in drafts:
            ev = self._commit_one(draft, annotated_jpeg, ctx)
            if ev is not None:
                out.append(ev)
        return out

    # ---- internals ----

    def _commit_one(self, d: EventDraft, jpeg: Optional[bytes],
                    ctx: FrameContext) -> Optional[CommittedEvent]:
        is_system = d.type in _SYSTEM_TYPES
        if not is_system and not self._pass_cooldown(d, ctx.wall_ts):
            return None

        metadata = dict(d.metadata)
        metadata["is_night"] = bool(metadata.get("is_night", ctx.is_night))
        severity, reason = self._severity_for(d, metadata)
        metadata["severity_reason"] = reason
        metadata["_id"] = str(uuid.uuid4())       # committed event id

        snapshot_path: Optional[str] = None
        if not is_system and jpeg is not None and \
                _SEVERITY_ORDER.index(severity) >= \
                _SEVERITY_ORDER.index(EVENTS.snapshot_min_severity):
            snapshot_path = self._save_snapshot(jpeg, metadata)
            if snapshot_path:
                metadata["snapshot_path"] = snapshot_path
                # NOTE: the evidence ROW is registered by the WRITER after
                # the event row lands (FK order: evidence.event_id ->
                # events.id). The metadata carries the path; the writer
                # reads it from the row's metadata JSON.

        ev = CommittedEvent(
            type=d.type,
            session_id=self._session_id,
            source_id=self._source_id,
            ts=_iso(ctx.wall_ts),
            video_ts=metadata.get("video_ts", ctx.video_ts),
            severity=severity,
            confidence=float(d.confidence),
            track_ids=list(d.track_ids),
            zone_id=d.zone_id,
            direction=d.direction,
            is_night=bool(metadata["is_night"]),
            snapshot_path=snapshot_path,
            metadata=metadata)

        if self._writer is not None:
            self._writer.enqueue(self._as_row(ev))
        if self._hub is not None:
            self._hub.publish(ev.sse_json())
        self.committed += 1
        return ev

    def _pass_cooldown(self, d: EventDraft, wall_ts: float) -> bool:
        """A2: suppress IFF Δt < cooldown STRICTLY. Exactly 10.0s passes.
        PERSON/VEHICLE_DETECTED never reach here (structural once-per-track
        upstream) but if one does, its key is still type-keyed — harmless."""
        key = (d.type, d.track_ids[0] if d.track_ids else -1,
               d.zone_id or "")
        with self._lock:
            last = self._cooldown.get(key)
            if last is not None and (wall_ts - last) < EVENTS.cooldown_seconds:
                return False
            self._cooldown[key] = wall_ts
            return True

    @staticmethod
    def _severity_for(d: EventDraft,
                      metadata: dict) -> tuple[str, str]:
        """A3 severity ladder + concatenated severity_reason."""
        is_night = bool(metadata.get("is_night"))
        ztype = metadata.get("zone_type") or ""
        reasons: list[str] = []

        if d.type == "ZONE_ENTRY":
            base = "HIGH" if ztype == "RESTRICTED" else "MEDIUM"
            sev = base
            if ztype == "RESTRICTED":
                reasons.append("RESTRICTED zone entry")
            else:
                reasons.append("WATCH zone entry")
            if is_night:
                sev = _raise(sev, 1) if sev != "HIGH" else "HIGH"
                reasons.append("at night")
        elif d.type == "ZONE_EXIT":
            sev, _ = "LOW", reasons.append("zone exit")
        elif d.type == "LINE_CROSSING":
            sev = "MEDIUM"
            reasons.append("line crossing")
            if ztype == "RESTRICTED":
                sev = _raise(sev, 1)
                reasons.append("RESTRICTED line")
            if is_night:
                sev = _raise(sev, 1)
                reasons.append("at night")
        elif d.type in ("PERSON_DETECTED", "VEHICLE_DETECTED"):
            sev = "LOW"
            reasons.append(f"{d.type.split('_')[0].lower()} track confirmed")
        else:  # system events
            sev = "INFO"
            reasons.append(d.type.lower().replace("_", " "))
        return sev, " ".join(reasons)

    def _save_snapshot(self, jpeg: bytes, metadata: dict) -> Optional[str]:
        """Write the annotated JPEG to EVIDENCE_DIR/{event_id}.jpg and
        return the path. Failure => None (event commits snapshot-less —
        §20 disk-low behavior, flagged by absence)."""
        event_id = metadata["_id"]
        try:
            EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
            p = EVIDENCE_DIR / f"{event_id}.jpg"
            p.write_bytes(jpeg)
            return str(p)
        except OSError as e:
            log.warning("snapshot write failed (event commits without "
                        "evidence): %s", e)
            metadata["snapshot_flag"] = "write_failed"
            return None

    @staticmethod
    def _as_row(ev: CommittedEvent) -> tuple:
        import json
        return (
            ev.metadata["_id"], ev.session_id, ev.source_id, ev.ts,
            ev.video_ts, ev.type, ev.severity, ev.confidence,
            json.dumps(ev.track_ids), ev.zone_id, ev.direction,
            int(ev.is_night), ev.snapshot_path,
            json.dumps({k: v for k, v in ev.metadata.items()
                        if not k.startswith("_")}),
            "new",
        )


def _iso(epoch: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(
        timespec="milliseconds")
