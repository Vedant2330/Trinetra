"""M8 movement history — deterministic global-person timeline.

Records ONLY what actually happened (mandate §7/§10/§11): first_seen,
moving, stationary, prolonged_stationary, direction_change,
camera_transition (from a REAL confirmed correlation), zone_entry,
zone_exit, tripwire_crossing. The closed ALLOWED_KINDS set rejects
any invented behavioral verb ("suspicious", "intent", ...) by
construction.

Ordering: timeline() returns points sorted by (wall_ts, append seq) —
stable, testable, derived from real observations only.

Duplicate suppression: note_transition records at most ONE transition
point per (identity, camera) — re-sampled tracks (sampling policy
re-embedding the same person) never duplicate transitions (mandate
test 11).
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from typing import Iterator, Optional

from backend.reid.identity import GlobalIdentity, MovementPoint

ALLOWED_KINDS = frozenset({
    "first_seen", "moving", "stationary", "prolonged_stationary",
    "direction_change", "camera_transition", "zone_entry", "zone_exit",
    "tripwire_crossing",
})

_STATIONARY_EPS_PX = 6.0
_PROLONGED_S = 30.0
_MAX_POINTS_PER_ID = 2000


class GlobalMovementHistory:
    """Per-identity ordered movement + event timeline (thread-safe)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._points: dict[str, deque] = {}
        self._transition_seen: set[str] = set()
        self._seq = 0

    # ---- recording ----

    def record(self, pid: str, point: MovementPoint) -> None:
        """Append one point (kind must be in the closed vocabulary)."""
        if point.kind not in ALLOWED_KINDS:
            raise ValueError(
                f"movement kind {point.kind!r} not allowed — deterministic "
                f"verbs only: {sorted(ALLOWED_KINDS)}")
        with self._lock:
            dq = self._points.get(pid)
            if dq is None:
                dq = deque(maxlen=_MAX_POINTS_PER_ID)
                self._points[pid] = dq
            self._seq += 1
            dq.append((point.wall_ts, self._seq, point))

    def note_first_seen(self, ident: GlobalIdentity, camera_id: str,
                        track_id: int, wall_ts: float) -> None:
        self.record(ident.global_person_id, MovementPoint(
            wall_ts=wall_ts, camera_id=camera_id, track_id=track_id,
            kind="first_seen"))

    def note_transition(self, pid: str, camera_id: str, track_id: int,
                        from_camera: Optional[str],
                        wall_ts: float) -> bool:
        """One transition point per (identity, camera). Returns True if
        recorded, False if duplicate-suppressed."""
        with self._lock:
            seen_key = f"{pid}:cam:{camera_id}"
            if seen_key in self._transition_seen:
                return False
            self._transition_seen.add(seen_key)
            dq = self._points.get(pid)
            if dq is None:
                dq = deque(maxlen=_MAX_POINTS_PER_ID)
                self._points[pid] = dq
            self._seq += 1
            dq.append((wall_ts, self._seq, MovementPoint(
                wall_ts=wall_ts, camera_id=camera_id, track_id=track_id,
                kind="camera_transition",
                note=f"from {from_camera}" if from_camera else None)))
            return True

    def note_zone(self, pid: str, camera_id: str, track_id: int,
                  zone_id: str, kind: str, wall_ts: float,
                  note: Optional[str] = None) -> None:
        """zone_entry / zone_exit / tripwire_crossing from REAL fence
        drafts (the integration adapter calls this)."""
        if kind not in ("zone_entry", "zone_exit", "tripwire_crossing"):
            raise ValueError(f"zone kind {kind!r} not allowed")
        self.record(pid, MovementPoint(
            wall_ts=wall_ts, camera_id=camera_id, track_id=track_id,
            kind=kind, zone_id=zone_id, note=note))

    # ---- queries ----

    def timeline(self, pid: str) -> list[dict]:
        with self._lock:
            pts = sorted(self._points.get(pid, ()))
        return [p.as_dict() for (_ts, _seq, p) in pts]

    def cameras_visited(self, pid: str) -> list[str]:
        return sorted({p["camera_id"] for p in self.timeline(pid)})

    def zone_entries(self, pid: str) -> list[dict]:
        return [p for p in self.timeline(pid)
                if p["kind"] in ("zone_entry", "zone_crossing")]

    def __contains__(self, pid: str) -> bool:
        with self._lock:
            return pid in self._points

    def __len__(self) -> int:
        with self._lock:
            return len(self._points)

    def iter_pids(self) -> Iterator[str]:
        with self._lock:
            return iter(list(self._points.keys()))
