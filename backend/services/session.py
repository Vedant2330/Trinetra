"""TRINETRA processing session — the one and only processing loop (M3).

Ownership (frozen architecture, one active session):
    ProcessingSession owns: VideoSource, DetectorTracker, TrackStore,
    one processing thread, one LatestFrameSlot. Nothing else does inference.

Execution model: a single daemon thread runs the synchronous loop:

    read -> detect+track -> state -> FrameContext -> analytics chain
        -> annotate(copy) -> JPEG -> slot.publish

No new threads/locks in M4 — the chain runs inline on the session thread
(§3 step 6). Drafts are collected into a bounded list (_MAX_DRAFTS,
drop-oldest) surfaced via status_payload (drafts_count, per-zone counts).

The FastAPI event loop never blocks on inference. MJPEG endpoints only
READ the slot — many readers, ONE processing loop, zero per-client inference.

Warm-up (verified safe — see tests/test_m3_session.py):
    model.predict(noise) once at session start. This warms the MPS/CIW graph
    WITHOUT touching ByteTrack: predict() bypasses the tracker entirely, so
    tracking state begins on the first real frame (identical ID sequences
    proven vs a cold tracker). A track()-based warm-up was investigated and
    REJECTED: it loses the first frame's detections (measured evidence).

EOF (files): loop ends, session status=completed, last annotated JPEG stays
served via the slot's non-consuming peek until the next session publishes.
Metrics: pipeline FPS = rolling mean of (loop start -> JPEG published);
displayed FPS uses the same numbers — one source of truth.
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from backend.analytics import FenceAnalytic, FrameContext, ZoneStore
from backend.core.config import STREAM, VISION
from backend.services.frame_slot import LatestFrameSlot
from backend.sources import FileSource, SourceError, VideoSource, WebcamSource
from backend.state import TrackStore
from backend.vision import DetectorError, DetectorTracker
from backend.vision.annotation import annotate

log = logging.getLogger("trinetra.session")

_FPS_WINDOW = 30          # rolling window for pipeline FPS (documented metric)
_MAX_CONSECUTIVE_READ_FAILS = 60   # ~3s at 20fps -> abort (webcam gone)
_IS_NIGHT_LUMA = 40.0     # §3 step 3: is_night = mean-gray < 40 (named constant)
_MAX_DRAFTS = 500         # bounded session draft list; drop-oldest (M4)


class SessionError(Exception):
    """Invalid session request or lifecycle misuse."""


class ProcessingSession:
    """One active processing session. Create via start(); stop() to end."""

    def __init__(self, source: VideoSource) -> None:
        self._source = source
        self._detector = DetectorTracker()          # policy from config (auto)
        self._store = TrackStore()
        self._slot = LatestFrameSlot()
        self._zones = ZoneStore()                   # M4 in-memory seam (M5 -> SQLite)
        self._analytics = [FenceAnalytic(self._zones)]   # MVP chain: one module (§11)
        self._analytics[0].reset(source.source_id)
        self.event_drafts: list[dict] = []          # bounded, drop-oldest
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._started_at = time.time()
        # metrics (guarded by GIL-safe simple writes; read via status())
        self.frames_processed = 0
        self.pipeline_fps: float = 0.0
        self.error: str = ""
        self.status: str = "starting"               # starting|running|completed|error|stopped
        self._durations: list[float] = []

    # ---- properties ----

    @property
    def source_id(self) -> str:
        return self._source.source_id

    @property
    def device(self) -> str:
        return self._detector.actual_device

    @property
    def slot(self) -> LatestFrameSlot:
        return self._slot

    @property
    def zones(self) -> ZoneStore:
        """Zone CRUD surface (M5 REST); validated geometry, §12 space."""
        return self._zones

    # ---- lifecycle ----

    def start(self) -> None:
        if self._thread is not None:
            raise SessionError("session already started")
        try:
            self._source.open()
        except SourceError as e:
            self.status = "error"
            self.error = str(e)
            raise
        try:
            self._detector.load()
        except DetectorError as e:
            self._source.release()
            self.status = "error"
            self.error = str(e)
            raise
        self._warmup()
        self._thread = threading.Thread(target=self._run, name="trinetra-session", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._source.release()
        if self.status in ("running", "starting"):
            self.status = "stopped"

    # ---- internals ----

    def _warmup(self) -> None:
        """One predict() call on internal noise — warms the inference graph.
        Does NOT touch ByteTrack (predict bypasses tracking; verified by
        test_warmup_does_not_contaminate_tracking)."""
        noise = np.zeros((480, 640, 3), dtype=np.uint8)
        try:
            self._detector.warmup(noise)
        except DetectorError:
            log.warning("warm-up inference failed; continuing cold")

    def _run(self) -> None:
        self.status = "running"
        tick = 0
        read_fails = 0
        try:
            while not self._stop.is_set():
                t0 = time.perf_counter()
                pkt = self._source.read()
                if pkt is None:
                    if self._source.state.value == "EOF":
                        self.status = "completed"
                        break
                    read_fails += 1
                    if read_fails >= _MAX_CONSECUTIVE_READ_FAILS:
                        raise RuntimeError("source read failed repeatedly (device gone?)")
                    continue
                read_fails = 0

                objects = self._detector.process(pkt.frame)
                self._store.update(objects, tick=tick, wall_ts=pkt.wall_ts)

                # FrameContext (§3 step 3): luminance = mean gray via cv2,
                # is_night = luminance < _IS_NIGHT_LUMA (named constant).
                h, w = pkt.frame.shape[:2]
                gray = cv2.cvtColor(pkt.frame, cv2.COLOR_BGR2GRAY)
                luminance = float(gray.mean())
                ctx = FrameContext(
                    tick=tick, wall_ts=pkt.wall_ts, video_ts=pkt.video_ts,
                    luminance=luminance, is_night=luminance < _IS_NIGHT_LUMA,
                    shape=(w, h))

                # analytics chain (§3 step 6): read-only view over the store
                view = self._store.view()
                for module in self._analytics:
                    for draft in module.process(ctx, view):
                        self.event_drafts.append({
                            "type": draft.type,
                            "track_ids": draft.track_ids,
                            "zone_id": draft.zone_id,
                            "direction": draft.direction,
                            "confidence": draft.confidence,
                            "metadata": draft.metadata,
                            "wall_ts": pkt.wall_ts,
                        })
                        if len(self.event_drafts) > _MAX_DRAFTS:
                            self.event_drafts.pop(0)   # bounded, drop-oldest

                annotated = annotate(
                    pkt.frame, objects,
                    pipeline_fps=self.pipeline_fps if self.pipeline_fps > 0 else None,
                    device=self._detector.actual_device,
                )
                ok, buf = cv2.imencode(
                    ".jpg", annotated,
                    [int(cv2.IMWRITE_JPEG_QUALITY), STREAM.mjpeg_quality],
                )
                if not ok:
                    raise RuntimeError("JPEG encoding failed")
                self._slot.publish(bytes(buf))

                dt = time.perf_counter() - t0
                self._durations.append(dt)
                if len(self._durations) > _FPS_WINDOW:
                    self._durations.pop(0)
                self.pipeline_fps = 1.0 / (sum(self._durations) / len(self._durations))
                self.frames_processed += 1
                tick += 1
        except Exception as e:  # noqa: BLE001 — session must die cleanly, server must not
            self.status = "error"
            self.error = f"{type(e).__name__}: {e}"
            log.exception("processing loop failed")
        finally:
            self._source.release()

    # ---- status ----

    def status_payload(self) -> dict:
        fence = self._analytics[0] if self._analytics else None
        return {
            "source_id": self.source_id,
            "status": self.status,
            "device": self.device,
            "frames_processed": self.frames_processed,
            "pipeline_fps": round(self.pipeline_fps, 1),
            "active_tracks": self._store.count_active(),
            "total_tracks": len(self._store.tracks),
            "drafts_count": len(self.event_drafts),
            "zone_person_counts": fence.zone_person_counts() if fence else {},
            "error": self.error or None,
            "uptime_s": round(time.time() - self._started_at, 1),
        }


# ---- one-active-session registry (module-level, minimal) ----

_active: Optional[ProcessingSession] = None
_lock = threading.Lock()


def get_active_session() -> Optional[ProcessingSession]:
    with _lock:
        return _active


def start_session(source: VideoSource) -> ProcessingSession:
    global _active
    with _lock:
        if _active is not None and _active.status in ("running", "starting"):
            raise SessionError(
                f"one active session rule: session '{_active.source_id}' is "
                f"{_active.status} — stop it first"
            )
        session = ProcessingSession(source)
        session.start()
        _active = session
        return session


def stop_active_session() -> Optional[ProcessingSession]:
    global _active
    with _lock:
        session = _active
        if session is not None:
            session.stop()
            _active = None
        return session


def make_source(spec: dict) -> VideoSource:
    """Minimal source factory for the dev-level control endpoints.

    type=webcam -> WebcamSource(index)
    type=file   -> FileSource(path)   (validated by FileSource at open)
    """
    stype = spec.get("type")
    if stype == "webcam":
        return WebcamSource(int(spec.get("index", 0)))
    if stype == "file":
        path = spec.get("path", "")
        if not path:
            raise SessionError("file session requires 'path'")
        return FileSource(path)
    raise SessionError(f"unknown source type: {stype!r} (use 'webcam' or 'file')")
