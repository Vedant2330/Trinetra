"""M8 IdentityGallery — the single home of global identity state.

Owns:
  - id minting: P-0001, P-0002, ... (zero-padded, monotonic counter)
  - live identities: dict pid -> GlobalIdentity
  - exemplar retention: bounded per camera (reid.exemplars_per_camera),
    newest kept
  - eviction of stale identities: not auto-deleted in MVP (an identity
    is historical record); `prune_older_than` is the explicit sweep.

Thread model: one lock; camera threads call observe-time lookups only
via the correlator, which serializes gallery mutations. get_snapshot()
copies references for read-only iteration (identities are treated as
immutable by readers under the correlator's discipline).
"""

from __future__ import annotations

import threading
from typing import Iterator, Optional

import numpy as np

from backend.core.config import REID
from backend.reid.identity import GlobalIdentity, MatchState


class IdentityGallery:
    """Where global identities live. The only id minter."""

    def __init__(self, exemplars_per_camera: Optional[int] = None) -> None:
        self._lock = threading.RLock()
        self._next_id = 1
        self._identities: dict[str, GlobalIdentity] = {}
        self._exemplars_per_camera = (exemplars_per_camera
                                      if exemplars_per_camera is not None
                                      else REID.exemplars_per_camera)

    # ---- minting / lifecycle ----

    def mint(self, first_seen_ts: float,
             class_name: str = "person") -> GlobalIdentity:
        """Create a NEW global identity (used when a track has no
        confirmed home). Ids are stable strings: P-0001..."""
        with self._lock:
            pid = f"P-{self._next_id:04d}"
            self._next_id += 1
            ident = GlobalIdentity(
                global_person_id=pid,
                created_ts=first_seen_ts,
                first_seen_ts=first_seen_ts,
                last_seen_ts=first_seen_ts,
                class_name=class_name)
            self._identities[pid] = ident
            return ident

    # ---- exemplar retention ----

    def add_exemplar(self, ident: GlobalIdentity, camera_id: str,
                     embedding: np.ndarray) -> None:
        """Bounded, newest-kept exemplar retention per camera."""
        with self._lock:
            bucket = ident.exemplars.setdefault(camera_id, [])
            bucket.append(np.asarray(embedding, dtype=np.float32))
            if len(bucket) > self._exemplars_per_camera:
                del bucket[:-self._exemplars_per_camera]

    # ---- queries ----

    def get(self, pid: str) -> Optional[GlobalIdentity]:
        with self._lock:
            return self._identities.get(pid)

    def all_identities(self) -> list[GlobalIdentity]:
        with self._lock:
            return list(self._identities.values())

    def identity_for_track(self, camera_id: str,
                           track_id: int) -> Optional[GlobalIdentity]:
        """The identity a local track is CONFIRMED bound to, if any."""
        with self._lock:
            for ident in self._identities.values():
                meta = ident.track_bindings.get((camera_id, track_id))
                if meta is not None and meta.get("state") is MatchState.CONFIRMED:
                    return ident
            return None

    def snapshot(self) -> dict[str, GlobalIdentity]:
        with self._lock:
            return dict(self._identities)

    def __len__(self) -> int:
        with self._lock:
            return len(self._identities)

    def __iter__(self) -> Iterator[GlobalIdentity]:
        return iter(self.all_identities())

    # ---- maintenance ----

    def prune_older_than(self, epoch_s: float) -> int:
        """Remove identities whose last_seen predates epoch. Returns
        count pruned. Identities bound to a still-live track are kept
        (a bound track means an active camera still claims it)."""
        with self._lock:
            dead = [pid for pid, ident in self._identities.items()
                    if ident.last_seen_ts < epoch_s
                    and not ident.track_bindings]
            for pid in dead:
                del self._identities[pid]
            return len(dead)
