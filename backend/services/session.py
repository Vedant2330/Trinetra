"""TRINETRA processing session — the one and only processing loop (M5).

Ownership (frozen architecture, one active session):
    ProcessingSession owns: VideoSource, DetectorTracker, TrackStore,
    one processing thread, one LatestFrameSlot. Nothing else does inference.

    M5: the session RECEIVES the app-scoped ZoneStore (SQLite-backed,
    C1), the EventWriter, the SseHub, and the DAO (for the sessions row
    lifecycle C4). The EventEngine (per-session, C8) is created here.

Execution model: a single daemon thread runs the synchronous loop (§3):

    read -> detect+track -> state -> FrameContext -> analytics chain
        -> annotate(copy) -> JPEG -> engine.commit(drafts, SAME jpeg)
        -> slot.publish

    §3 ordering: annotate BEFORE commit — event snapshots are the SAME
    annotated JPEG the operator sees (A1: one render, no re-encode).
    PERSON/VEHICLE_DETECTED drafts come from take_newly_confirmed()
    (structural once-per-track, A2) — NOT the cooldown map.

Source lifecycle (A5): SOURCE_CONNECTED draft after open + FIRST
successful read (emitted in-loop, not at start()); SOURCE_LOST draft
on read-fail abort, BEFORE status=error. System events: jpeg=None (A1).

EOF finalize (A6, pinned order):
    flush tracks -> DB  ->  SESSION_COMPLETED commit  ->  writer drain
    ->  status=completed   (drain MUST precede the status flip)
    Stop path: same finalize in `finally` for completed/stopped/error
    (error = best-effort flush, honest partial). Writer is catch-all
    (A6): a DB error kills neither the writer thread nor the session.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from backend.analytics import (
    ANPRAnalytic,
    CrowdDensityAnalytic,
    FenceAnalytic,
    FrameContext,
    KinematicTrajectoryAnalytic,
    ZoneStore,
)
from backend.analytics.base import EventDraft
from backend.core.config import SOURCES, STREAM, TRACKING, VISION
from backend.events import EventEngine, SseHub
from backend.db.dao import DAO
from backend.db.writer import EventWriter
from backend.services.frame_slot import LatestFrameSlot
from backend.services.playback import FrameHandoff, OverlayBoard, OverlayResult
from backend.sources import FileSource, RtspSource, SourceError, SourceState, VideoSource, WebcamSource
from backend.state import TrackStore
from backend.vision import DetectorError, DetectorTracker, FaceDetection, PoseDetection, YOLOv8PoseDetector, YuNetFaceDetector
from backend.vision.annotation import annotate

log = logging.getLogger("trinetra.session")

_FPS_WINDOW = 30          # rolling window for pipeline FPS (documented metric)
# M6 C2/C3: read-fail limits live in config [sources] (decode_fail_limit
# for files; webcam uses the backoff ladder — no fixed read-fail cap).
_IS_NIGHT_LUMA = 40.0     # §3 step 3: is_night = mean-gray < 40 (named constant)
# Decoupled playback: an overlay older than this is dropped and the
# clean current frame is displayed (bounded staleness, mandate §10B).
_OVERLAY_TOLERANCE_S = 1.0

_VEHICLE_CLASSES = frozenset(
    {"bicycle", "car", "motorcycle", "bus", "truck"})


class SessionError(Exception):
    """Invalid session request or lifecycle misuse."""


def _sys_draft(type_: str) -> EventDraft:
    """System draft (§13): SOURCE_*/SESSION_COMPLETED/SOURCE_RECONNECTED
    (M6 9th type) — INFO severity, no tracks, no zone, no snapshot
    (A1: jpeg=None). System events BYPASS the engine cooldown (verified:
    _pass_cooldown is skipped for _SYSTEM_TYPES) so SOURCE_LOST fires
    exactly once per disconnect cycle via the one-shot flag (C2)."""
    return EventDraft(
        type=type_, track_ids=[], zone_id=None, direction=None,
        confidence=1.0, metadata={"is_night": False, "system": True})


def _sys_ctx(tick: int, wall_ts: float) -> FrameContext:
    """Minimal FrameContext for system-event commits."""
    return FrameContext(tick=tick, wall_ts=wall_ts, video_ts=None,
                        luminance=128.0, is_night=False, shape=(1, 1))


class ProcessingSession:
    """One active processing session. Create via start(); stop() to end."""

    def __init__(self, source: VideoSource,
                  zones: Optional[ZoneStore] = None,
                  dao: Optional[DAO] = None,
                  writer: Optional[EventWriter] = None,
                  hub: Optional[SseHub] = None,
                  reid_service=None) -> None:
        self._source = source
        self._detector = DetectorTracker()          # policy from config (auto)
        self._store = TrackStore()
        self._slot = LatestFrameSlot()
        # C1: app-scoped SQLite-backed store RECEIVED from the app; the
        # M4 in-memory fallback only when no app context (unit tests).
        self._zones = zones if zones is not None else ZoneStore()
        self._dao = dao
        self._writer = writer
        self._hub = hub
        # Phase 2: app-scoped MultiCameraReIdService (None = capability
        # off / model absent — the honest NO-OP path). The session
        # registers its source_id as the camera id (single-session MVP,
        # R9-endorsed default); the ONNX net loads lazily on the first
        # embed (§44 — never at boot).
        self._reid = reid_service
        self._face_detector = YuNetFaceDetector()
        self._pose_detector = YOLOv8PoseDetector()
        fence = FenceAnalytic(self._zones)
        fence.reset(source.source_id)
        kinematics = KinematicTrajectoryAnalytic()
        kinematics.reset(source.source_id)
        crowd = CrowdDensityAnalytic(fence_analytic=fence)
        crowd.reset(source.source_id)
        anpr = ANPRAnalytic()
        anpr.reset(source.source_id)
        self._analytics = [fence, kinematics, crowd, anpr]
        # Calibration (audit fix): tick→seconds conversions must use the
        # ACTUAL source FPS. FileSource exposes container metadata after
        # open(); live sources without metadata fall back to the measured
        # pipeline rate (updated per-tick below).
        self._kinematics = kinematics
        self._anpr = anpr
        self._source_fps = 25.0
        # C4/C8: session row id + per-session engine state
        self._session_row_id: Optional[str] = None
        self._engine: Optional[EventEngine] = None
        self._thread: Optional[threading.Thread] = None
        self._inf_thread: Optional[threading.Thread] = None
        self._handoff = FrameHandoff()
        self._overlay_board = OverlayBoard(tolerance_s=_OVERLAY_TOLERANCE_S)
        self._stop = threading.Event()
        self._step_event = threading.Event()
        self._seek_seq = 0          # bumped on seek: overlay auto-stales
        self._last_seq = 0          # last pacing anchor's seq
        self._anchored_speed: float = 1.0   # speed the clock was anchored at
        self._paused: bool = False
        self._speed: float = 1.0
        self._started_at = time.time()
        # V3 render layers (C3): immutable dict swapped atomically under
        # a small lock — the render thread reads the reference ONCE per
        # tick; no in-place mutation, no torn half-applied frames.
        # Defaults: trajectories OFF preserves today's rendering; zones
        # ON is the intended C2/M7 completion (fence burned into stream
        # AND evidence — one render, the shared-JPEG A1 rule); faces/pose
        # OFF per Phase 3/8 V2.
        self._layers: dict = {
            "boxes": True, "labels": True, "fps": True,
            "trajectories": False, "zones": True, "faces": False, "pose": False,
        }
        self._layers_lock = threading.Lock()
        # metrics (guarded by GIL-safe simple writes; read via status())
        self.frames_processed = 0
        self.pipeline_fps: float = 0.0
        self.playback_fps: float = 0.0     # honest display rate (PLAY)
        self.error: str = ""
        self.status: str = "starting"               # starting|running|paused|completed|error|stopped
        self._durations: list[float] = []
        self._play_intervals: deque[float] = deque(maxlen=_FPS_WINDOW)
        self._last_display_ts: Optional[float] = None
        self._inference_durations: list[float] = []
        self._inference_fps: float = 0.0
        self._avg_latency_ms: float = 0.0
        self._last_shape: tuple[int, int] = (640, 480)
        self._connected_emitted = False
        self._finalized = False
        self._live_calibrated = False       # one-shot live-rate calibration

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
        """Zone CRUD surface (C1: works with no active session too)."""
        return self._zones

    @property
    def engine(self) -> Optional[EventEngine]:
        return self._engine

    @property
    def events_committed(self) -> int:
        return self._engine.committed if self._engine else 0

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
        # Calibration: after open(), FileSource knows the container FPS.
        # Feed the REAL rate into the kinematic analytic (a hardcoded 25
        # assumption skews speeds/dwell by fps/25 on 30fps sources).
        try:
            fps = float(getattr(self._source, "fps", 0.0) or 0.0)
        except Exception:  # noqa: BLE001 — metadata is best-effort
            fps = 0.0
        if fps > 0:
            self._source_fps = fps
            self._kinematics.set_fps(fps)
        try:
            self._detector.load()
        except DetectorError as e:
            self._source.release()
            self.status = "error"
            self.error = str(e)
            raise
        # C4: sessions row INSERT + sources row UPSERT (FK targets)
        if self._dao is not None:
            # §2.9: derive the DB source type from the SOURCE CLASS, not
            # the id string (an RtspSource would have registered as
            # "file" under the old substring rule). getattr default
            # keeps unknown/test sources identical to prior behavior.
            src_type = getattr(self._source, "type_name", "file")
            self._dao.upsert_source(self.source_id, src_type)
            self._session_row_id = self._dao.insert_session(self.source_id)
        # C8: per-session engine (cooldown map + counter cleared)
        self._engine = EventEngine(
            self.source_id,
            self._session_row_id or f"nosession:{id(self)}",
            writer=self._writer, hub=self._hub, dao=self._dao)
        # Phase 2: register this session's source as the (single-camera
        # MVP) camera id on the shared re-id service.
        if self._reid is not None:
            try:
                self._reid.register_camera(self.source_id)
            except Exception as e:  # noqa: BLE001 — capability must not kill sessions
                log.warning("reid register_camera failed: %s", e)
        self._warmup()
        self._thread = threading.Thread(target=self._run, name="trinetra-session", daemon=True)
        self._thread.start()
        # Decoupled inference thread — an independent consumer of the
        # media timeline (mandate: playback NEVER limited by inference).
        self._inf_thread = threading.Thread(
            target=self._inference_loop, name="trinetra-inference", daemon=True)
        self._inf_thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the session. Status-flag ordering (audit fix): the
        `stopped` flag is assigned BEFORE join() — the worker thread's
        finally-finalize (which writes the DB row) must observe the
        final status, not a stale `running`. Pre-fix, the row was
        written mid-race and stayed `running` forever (phantom live
        sessions in the Investigation list)."""
        self._stop.set()
        if self._inf_thread is not None:
            self._inf_thread.join(timeout=timeout)
        if self._thread is not None:
            if self.status in ("running", "starting"):
                self.status = "stopped"
            self._thread.join(timeout=timeout)
        self._source.release()
        if self.status in ("running", "starting"):
            self.status = "stopped"
        self._finalize()        # A6: stop path finalize (idempotent guard)

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

    def _annotate(self, frame: np.ndarray, objects: list,
                  faces: Optional[list] = None,
                  poses: Optional[list] = None,
                  trajectories: Optional[dict] = None) -> np.ndarray:
        """Display-side annotation: draw the CURRENT frame with the
        latest fresh inference overlay (never mutates the input; V3
        layer gating preserved). Trajectories/faces/poses arrive as
        snapshot data computed inside the inference thread — the
        display thread never iterates live tracking state."""
        # C3: one atomic reference read per tick
        layers = self._layers
        zones = None
        if layers.get("zones"):
            zones = [
                {"kind": z.kind, "zone_type": z.type,
                 "name": z.name, "geometry": z.geometry}
                for z in self._zones.zones(self.source_id) if z.active
            ]
        hud = {
            "src": self._source_fps if self._source_fps > 0 else None,
            "play": self.playback_fps if self.playback_fps > 0 else None,
            "inf": self._inference_fps if self._inference_fps > 0 else None,
            "lat": self._avg_latency_ms,
        }
        return annotate(
            frame, objects,
            device=self._detector.actual_device,
            zones=zones,
            layers={"boxes": layers.get("boxes", True),
                    "labels": layers.get("labels", True),
                    "fps": layers.get("fps", True),
                    "faces": layers.get("faces", False),
                    "pose": layers.get("pose", False)},
            trajectories=trajectories,
            faces=faces,
            poses=poses,
            hud=hud,
        )

    # ---- V3 render layers (C3 atomic swap; C7 route calls this) ----

    def get_layers(self) -> dict:
        """Current layer flags (a copy — callers never mutate state)."""
        with self._layers_lock:
            return dict(self._layers)

    def update_layers(self, updates: dict) -> dict:
        """Partial-merge layer updates. Returns the new dict. Unknown
        keys raise SessionError (the API maps that to 400 — a typo'd
        toggle silently ignored would be a dead control)."""
        valid = {"boxes", "labels", "fps", "trajectories", "zones", "faces", "pose"}
        bad = set(updates) - valid
        if bad:
            raise SessionError(f"unknown layer(s): {sorted(bad)}")
        with self._layers_lock:
            self._layers = {**self._layers, **updates}
            return dict(self._layers)

    # ---- Playback Controls (Play / Pause / Speed / Step / Replay) ----

    def pause(self) -> None:
        """Pause playback loop."""
        self._paused = True
        if self.status == "running":
            self.status = "paused"

    def resume(self) -> None:
        """Resume paused playback loop."""
        self._paused = False
        if self.status == "paused":
            self.status = "running"

    def set_speed(self, speed: float) -> float:
        """Set playback rate multiplier (0.1x to 8.0x)."""
        if speed < 0.1 or speed > 8.0:
            raise SessionError("speed must be between 0.1 and 8.0")
        self._speed = float(speed)
        return self._speed

    def step(self) -> None:
        """Step one single frame forward when paused."""
        if self._paused:
            self._step_event.set()

    def seek(self, video_ts: float) -> bool:
        """Seek video playback to a specific timestamp in seconds.

        Decoupled playback: a seek bumps the sequence so the display
        loop recaptures the media clock AND any overlay belonging to
        the previous timeline position is flushed (stale detections
        never render over the post-seek frame)."""
        if hasattr(self._source, "seek"):
            ok = self._source.seek(video_ts)
            if ok:
                self._seek_seq += 1
                self._handoff.clear()
                self._overlay_board.clear()
                if self._paused:
                    self._step_event.set()
                return True
        return False

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def speed(self) -> float:
        return self._speed

    def _commit(self, drafts: list[EventDraft], jpeg: Optional[bytes],
               ctx: FrameContext) -> None:
        if self._engine is not None:
            self._engine.commit(drafts, jpeg, ctx)

    def _run(self) -> None:
        """DISPLAY LOOP — the media clock (mandate §3).

        Reads frames and paces presentation by the SOURCE timeline:
        frame N presents at wall_start + N / (src_fps * speed). Inference
        NEVER gates display: an in-flight (fresh) overlay is drawn on
        the CURRENT frame; a stale/absent one means the clean frame is
        displayed. File sources are paced deterministically; LIVE
        sources display at arrival rate (no artificial slowing, §8);
        unpaced mock/test sources keep their existing fast semantics
        (drills rely on exact processed counts).
        """
        self.status = "running"
        tick = 0                      # display-loop iteration counter
        read_fails = 0
        decode_fails = 0                 # file decode-fail streak (C3)
        backoff_delay = SOURCES.backoff_base_s   # webcam ladder (C2)
        lost_emitted = False              # one-shot SOURCE_LOST flag (C2)
        # Media-clock pacing gate (§8): pace ONLY sources with real
        # container FPS metadata AND per-frame video timestamps — i.e.
        # real file sources. Mock/test sources (no fps attribute) and
        # live sources (webcam/RTSP) display at arrival rate.
        paced = (not getattr(self._source, "is_live", False)
                 and self._source_fps > 0
                 and not isinstance(self._source, RtspSource))
        media_epoch: Optional[float] = None    # perf_counter at frame 0
        try:
            while not self._stop.is_set():
                # Handle paused state (with single-frame step support)
                while self._paused and not self._stop.is_set():
                    if self._step_event.is_set():
                        self._step_event.clear()
                        break
                    if self._stop.wait(0.05):
                        break
                if self._stop.is_set():
                    break

                t_loop = time.perf_counter()
                pkt = self._source.read()
                if pkt is None:
                    st = self._source.state.value
                    if st == "EOF":
                        self.status = "completed"
                        break
                    if st == "ERROR" and getattr(self._source, "is_live",
                                                 False):
                        # ---- C2: webcam disconnect ladder ----
                        # DIVERGENCE (documented per C2): FILE sources
                        # keep the abort path (decode_fails >= limit ->
                        # error); WEBCAM sources back off and re-open.
                        # The session owns the ladder; the source owns
                        # reopen(). Delays are interruptible via the
                        # stop event — NEVER time.sleep.
                        if not lost_emitted:
                            lost_emitted = True     # one-shot; re-armed
                            self._commit(          # on reconnect
                                [_sys_draft("SOURCE_LOST")], None,
                                _sys_ctx(tick, time.time()))
                        if self._stop.wait(backoff_delay):
                            break                  # stop-during-backoff
                        if self._source.reopen():
                            lost_emitted = False   # re-arm the flag
                            backoff_delay = SOURCES.backoff_base_s
                            self._commit(
                                [_sys_draft("SOURCE_RECONNECTED")], None,
                                _sys_ctx(tick, time.time()))
                        else:
                            backoff_delay = min(backoff_delay * 2,
                                                SOURCES.backoff_cap_s)
                        continue
                    # ---- file (or non-live) read failure ----
                    read_fails += 1
                    decode_fails += 1
                    if decode_fails >= SOURCES.decode_fail_limit:
                        # C3: corrupt/truncated mid-file -> honest error
                        # (SOURCE_LOST fires first — the source is gone)
                        if not lost_emitted:
                            lost_emitted = True
                            self._commit(
                                [_sys_draft("SOURCE_LOST")], None,
                                _sys_ctx(tick, time.time()))
                        raise RuntimeError(
                            f"file decode failed {decode_fails} consecutive "
                            f"reads (corrupt/truncated?)")
                    continue                     # skip + count (§20)
                read_fails = 0
                decode_fails = 0

                # A5: SOURCE_CONNECTED after open + FIRST successful read
                if not self._connected_emitted:
                    self._connected_emitted = True
                    sys_ctx = FrameContext(
                        tick=tick, wall_ts=pkt.wall_ts,
                        video_ts=pkt.video_ts, luminance=128.0,
                        is_night=False, shape=(1, 1))
                    self._commit([_sys_draft("SOURCE_CONNECTED")], None,
                                 sys_ctx)

                # ---- media clock pacing (files only; §3/§8) ----
                if paced and pkt.video_ts is not None:
                    # Re-anchor on seek OR speed change: the current
                    # frame presents NOW; subsequent frames pace from
                    # this anchor at the new rate (seamless §7 changes).
                    if (media_epoch is None
                            or self._seek_seq_changed(tick)
                            or self._anchored_speed != self._speed):
                        media_epoch = (time.perf_counter()
                                       - float(pkt.video_ts) / max(0.1, self._speed))
                        self._last_seq = self._seek_seq
                        self._anchored_speed = self._speed
                    target = media_epoch + float(pkt.video_ts) / max(0.1, self._speed)
                    sleep_dt = target - time.perf_counter()
                    # Safety valve: if we're somehow far behind (decode
                    # hiccup), re-anchor instead of bursting (no catch-up
                    # burst — the operator sees steady rate).
                    if sleep_dt < -0.25:
                        media_epoch = (time.perf_counter()
                                       - float(pkt.video_ts) / max(0.1, self._speed))
                        sleep_dt = 0.0
                    if sleep_dt > 0.001:
                        if self._stop.wait(sleep_dt):
                            break

                # ---- offer the frame to inference (latest-frame
                # sampling: no queue, no backlog — §9) ----
                self._handoff.offer(pkt.frame, {
                    "frame_index": pkt.frame_index,
                    "video_ts": pkt.video_ts,
                    "wall_ts": pkt.wall_ts,
                    "shape": (int(pkt.frame.shape[1]), int(pkt.frame.shape[0])),
                })

                # ---- display: annotate with the latest FRESH overlay
                # (clean frame when none — never freeze, §10) ----
                overlay = self._overlay_board.peek_fresh()
                annotated = self._annotate(
                    pkt.frame,
                    overlay.objects if overlay is not None else [],
                    faces=overlay.faces if overlay is not None else None,
                    poses=overlay.poses if overlay is not None else None,
                    trajectories=overlay.trajectories
                    if overlay is not None else None,
                )
                ok, buf = cv2.imencode(
                    ".jpg", annotated,
                    [int(cv2.IMWRITE_JPEG_QUALITY), STREAM.mjpeg_quality],
                )
                if not ok:
                    raise RuntimeError("JPEG encoding failed")
                # §3 step 9: publish at SOURCE rate
                self._slot.publish(bytes(buf))

                # honest PLAY metric: wall-clock presentation rate
                now = time.perf_counter()
                if self._last_display_ts is not None:
                    dt = now - self._last_display_ts
                    if dt > 0:
                        self._play_intervals.append(dt)
                        if len(self._play_intervals) >= 2:
                            self.playback_fps = 1.0 / (
                                sum(self._play_intervals) /
                                len(self._play_intervals))
                self._last_display_ts = now

                dt = time.perf_counter() - t_loop
                self._durations.append(dt)
                if len(self._durations) > _FPS_WINDOW:
                    self._durations.pop(0)
                self.pipeline_fps = 1.0 / (sum(self._durations) / len(self._durations))
                self.frames_processed += 1
                tick += 1
        except Exception as e:  # noqa: BLE001 — session must die cleanly, server must not
            self._final_status = "error"
            self.error = f"{type(e).__name__}: {e}"
            log.exception("processing loop failed")
            # SOURCE_LOST was already emitted in-loop (one-shot flag,
            # C2) for both the ladder and file-abort paths — nothing to
            # do here; the flag guarantees exactly-once per cycle.
        else:
            self._final_status = "completed"
        finally:
            self._source.release()
            # The display loop exiting means the session is OVER (EOF,
            # stop, or error): close the handoff (parked inference
            # takers wake NOW) then stop — the finalize join must not
            # wait out a full take() poll (the M5 mock-source race:
            # row read by the test between status-flip and finalize).
            self._stop.set()
            self._handoff.close()
            # EOF/stop: inference must finish BEFORE finalize so its
            # last drafts are committed+drained into the session row
            # (same pinned A6 order: flush -> commit -> drain -> flip).
            if self._inf_thread is not None:
                self._inf_thread.join(timeout=5.0)
            self._finalize()

    def _seek_seq_changed(self, _tick: int) -> bool:
        """True when a seek bumped the sequence since the last anchor."""
        return getattr(self, "_last_seq", 0) != self._seek_seq

    # ---- independent inference loop (mandate §4/§9) ----

    def _inference_loop(self) -> None:
        """INDEPENDENT INFERENCE LOOP — consumer of the media timeline.

        Takes the LATEST offered frame (never a backlog), runs
        detection+tracking+analytics+event-commit, and posts an
        OverlayResult for the display loop. Detection/tracking state
        (ByteTrack persist, TrackStore) is confined to THIS thread —
        the display thread never touches it. When inference is slower
        than playback, frames are skipped by sampling (bounded latency,
        no memory growth)."""
        try:
            while not self._stop.is_set():
                got = self._handoff.take(timeout=0.25)
                if got is None:
                    continue
                frame, meta = got
                if self._stop.is_set():
                    break
                self._process_one_frame(frame, meta)
        except Exception as e:  # noqa: BLE001 — must never kill display
            log.exception("inference loop failed: %s", e)
        finally:
            # M6 churn discipline: this thread's per-thread SQLite conn
            # (zones reads happen here) must not outlive the thread.
            if self._dao is not None:
                try:
                    self._dao.db.close()
                except Exception:  # noqa: BLE001 — teardown is best-effort
                    pass

    def _process_one_frame(self, frame: np.ndarray, meta: dict) -> None:
        """One analyzed frame: detect -> track -> analytics -> commit ->
        post overlay. Temporal integrity: tick = the frame's REAL index
        and video_ts (ByteTrack sees a monotonic, timestamp-true stream
        even when frames are sampled, mandate §5)."""
        t0 = time.perf_counter()
        tick = int(meta.get("frame_index", 0))
        video_ts = meta.get("video_ts")
        wall_ts = meta.get("wall_ts", time.time())
        w, h = meta.get("shape", (frame.shape[1], frame.shape[0]))

        objects = self._detector.process(frame)
        self._store.update(objects, tick=tick, wall_ts=wall_ts)
        h, w = frame.shape[:2]
        self._last_shape = (w, h)

        # FrameContext (§3 step 3): luminance = mean gray via cv2,
        # is_night = luminance < _IS_NIGHT_LUMA (named constant).
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        luminance = float(gray.mean())
        ctx = FrameContext(
            tick=tick, wall_ts=wall_ts, video_ts=video_ts,
            luminance=luminance, is_night=luminance < _IS_NIGHT_LUMA,
            shape=(w, h))

        # analytics chain (§3 step 6) + confirm-edge drafts (A2)
        view = self._store.view()
        # Shape-B pixel seam: the ANPR analytic consumes the current
        # frame via set_frame (never fabricates a read; model/OCR
        # absent => honest PLATE_DETECTED fallback).
        self._anpr.set_frame(frame)
        drafts: list[EventDraft] = []
        for t in self._store.take_newly_confirmed():
            dtype = "VEHICLE_DETECTED" \
                if t.class_name in _VEHICLE_CLASSES \
                else "PERSON_DETECTED"
            drafts.append(EventDraft(
                type=dtype, track_ids=[t.track_id], zone_id=None,
                direction=None, confidence=t.max_conf,
                metadata={"is_night": ctx.is_night,
                          "track_class": t.class_name,
                          "video_ts": ctx.video_ts,
                          "tick": ctx.tick}))
        for module in self._analytics:
            drafts += module.process(ctx, view)

        # Phase 2 (shape B, handoff §3.1-B): frame-consuming re-id
        # service — AFTER the analytics chain. Sampling policy inside;
        # unavailable embedder = honest NO-OP ([]).
        if self._reid is not None:
            try:
                drafts += self._reid.process_tick(
                    self.source_id, ctx, view, frame)
                drafts = self._reid.enrich_drafts(
                    self.source_id, drafts)
            except Exception as e:  # noqa: BLE001 — capability must not kill the tick
                log.warning("reid process_tick failed: %s", e)

        # Phase 3: Face detection on confirmed person tracks (V2)
        faces = []
        if self._face_detector.available:
            try:
                faces, face_draft_metas = self._face_detector.detect_in_person_tracks(
                    frame, self._store.active_tracks, wall_ts=wall_ts)
                for meta_fd in face_draft_metas:
                    drafts.append(EventDraft(
                        type="FACE_DETECTED",
                        track_ids=[meta_fd["track_id"]],
                        zone_id=None,
                        direction=None,
                        confidence=float(meta_fd["confidence"]),
                        metadata={
                            "is_night": ctx.is_night,
                            "face_bbox": meta_fd["face_bbox"],
                            "landmarks": meta_fd["landmarks"],
                            "video_ts": ctx.video_ts,
                            "tick": ctx.tick,
                        },
                    ))
            except Exception as e:  # noqa: BLE001 — capability must not kill tick
                log.warning("face detection failed: %s", e)

        # Phase 8: Pose detection when the layer is enabled (V1)
        poses = []
        if self._layers.get("pose") and self._pose_detector.available:
            try:
                poses = self._pose_detector.detect(frame)
            except Exception as e:  # noqa: BLE001 — capability must not kill tick
                log.warning("pose detection failed: %s", e)

        # Post the overlay FIRST (display never waits on the commit
        # path): trajectories/faces/poses are SNAPSHOTTED here in the
        # inference thread (cross-thread live iteration is banned).
        lay = self._layers
        trajs = None
        if lay.get("trajectories"):
            trajs = {
                t.track_id: [(x, y) for x, y, _tk in t.positions]
                for t in list(self._store.tracks.values())
                if t.positions
            }
        self._overlay_board.post(OverlayResult(
            objects=objects, trajectories=trajs, faces=faces,
            poses=poses, frame_index=tick, video_ts=video_ts,
            analyzed_at=time.perf_counter()))
        self._commit(drafts, self._latest_jpeg(), ctx)

        # Measure pure inference latency (INF + LAT metrics)
        t_proc = time.perf_counter() - t0
        self._inference_durations.append(t_proc)
        if len(self._inference_durations) > _FPS_WINDOW:
            self._inference_durations.pop(0)
        avg_proc = sum(self._inference_durations) / len(self._inference_durations)
        self._inference_fps = 1.0 / avg_proc if avg_proc > 0 else 0.0
        self._avg_latency_ms = avg_proc * 1000.0

        # Live-source calibration (audit fix, decoupled variant): live
        # sources have no container FPS — once the DISPLAY rate (the
        # camera's true delivery rate) stabilizes, tick→seconds
        # conversions adopt it. Live-sampled ticks span real delivery
        # intervals, so playback rate (not inference rate) is the
        # honest clock here.
        if (getattr(self._source, "is_live", False)
                and not self._live_calibrated
                and self.frames_processed >= _FPS_WINDOW
                and self.playback_fps > 0):
            self._live_calibrated = True
            try:
                self._kinematics.set_fps(self.playback_fps)
            except Exception:  # noqa: BLE001 — calibration is best-effort
                pass

    def _latest_jpeg(self) -> Optional[bytes]:
        """Snapshot seam (A1): the slot's latest published JPEG — the
        SAME image the operator sees. Read non-consuming for the commit
        path (evidence == operator's view, one render)."""
        return self._slot.peek()

    # ---- A6 finalize (pinned order) ----

    def _finalize(self) -> None:
        """flush tracks -> DB -> SESSION_COMPLETED -> writer drain ->
        status flip. Runs exactly once (idempotent guard); error path =
        best-effort flush (honest partial). M6 churn: closes THIS
        thread's DB connection at the end — session threads are
        per-session and their sqlite connections must not outlive them
        (fd-leak guard; Database reaps dead-thread conns lazily, but the
        session owning its own teardown is deterministic)."""
        if self._finalized:
            return
        self._finalized = True
        # Phase 2: unregister this camera from the shared re-id service
        # (single-session MVP; the identities/gallery persist app-wide
        # for the investigation endpoints).
        if self._reid is not None:
            try:
                self._reid.unregister_camera(self.source_id)
            except Exception:  # noqa: BLE001 — best-effort teardown
                pass
        try:
            target_status = getattr(self, "_final_status", self.status)
            if self._dao is not None and self._session_row_id is not None:
                # 1. flush tracks -> DB (§14 aggregates + V5 downsampled trajectory)
                w, h = getattr(self, "_last_shape", (640, 480))
                rows = []
                for t in self._store.tracks.values():
                    traj_json = None
                    if t.positions:
                        pts = list(t.positions)
                        if len(pts) > 60:
                            indices = [int(round(i * (len(pts) - 1) / 59)) for i in range(60)]
                            pts = [pts[idx] for idx in indices]
                        traj_list = [
                            {
                                "x": round(min(1.0, max(0.0, float(p[0]) / max(1.0, float(w)))), 4),
                                "y": round(min(1.0, max(0.0, float(p[1]) / max(1.0, float(h)))), 4),
                                "t": int(p[2]),
                            }
                            for p in pts
                        ]
                        traj_json = json.dumps(traj_list)

                    rows.append((
                        t.track_id, t.class_name,
                        _iso(t.first_seen), _iso(t.last_seen),
                        t.frames_seen, t.max_conf, traj_json))
                if rows:
                    self._dao.flush_tracks(self._session_row_id, rows)
                # 2. SESSION_COMPLETED commit (EOF path only — stopped/
                #    error paths update the row without the system event)
                if target_status == "completed":
                    sys_ctx = FrameContext(
                        tick=self.frames_processed, wall_ts=time.time(),
                        video_ts=None, luminance=128.0, is_night=False,
                        shape=(1, 1))
                    self._commit([_sys_draft("SESSION_COMPLETED")], None,
                                 sys_ctx)
                # 3. writer drain MUST precede the status row update
                if self._writer is not None:
                    self._writer.drain(timeout=5.0)
                self._dao.update_session(
                    self._session_row_id, target_status,
                    stats=self._stats_payload())
            elif self._writer is not None:
                self._writer.drain(timeout=5.0)
            self.status = target_status
        except Exception as e:  # noqa: BLE001 — finalize is best-effort
            log.error("session finalize failed (best-effort partial): %s", e)
        finally:
            if self._dao is not None:
                self._dao.db.close()   # THIS thread's conn only

    def _stats_payload(self) -> dict:
        fence = self._analytics[0] if self._analytics else None
        # C5 discipline applies here too — snapshot, never live-iterate
        snap = dict(self._store.tracks)
        return {
            "frames_processed": self.frames_processed,
            "source_fps": round(self._source_fps, 2) if self._source_fps > 0 else None,
            "playback_fps": round(self.playback_fps, 1) if self.playback_fps > 0 else None,
            "inference_fps": round(self._inference_fps, 1) if self._inference_fps > 0 else None,
            "avg_latency_ms": round(self._avg_latency_ms, 1),
            "pipeline_fps": round(self.pipeline_fps, 1),
            "events_committed": self.events_committed,
            "tracks_total": len(snap),
            "faces_total": self._face_detector.total_detections
            if hasattr(self._face_detector, "total_detections") else None,
            "zone_person_counts": fence.zone_person_counts() if fence else {},
        }

    # ---- status ----

    def status_payload(self) -> dict:
        fence = self._analytics[0] if self._analytics else None
        # V3/C5: ONE atomic snapshot of the tracks dict (C-level copy is
        # GIL-atomic) — kills the API-thread dict-changed-size race; all
        # per-class counts computed from it. people/vehicles_detected =
        # CUMULATIVE unique tracks by CURRENT class_name; active_* via
        # the same snapshot (no live iteration anywhere).
        snap = dict(self._store.tracks)
        people = sum(1 for t in snap.values() if t.class_name == "person")
        vehicles = sum(
            1 for t in snap.values() if t.class_name in _VEHICLE_CLASSES)
        active_people = sum(
            1 for t in snap.values()
            if t.active and t.class_name == "person")
        active_vehicles = sum(
            1 for t in snap.values()
            if t.active and t.class_name in _VEHICLE_CLASSES)
        source_fps = getattr(self._source, "fps", 25.0) or 25.0
        return {
            "source_id": self.source_id,
            "status": self.status,
            "device": self.device,
            "frames_processed": self.frames_processed,
            "source_fps": round(source_fps, 1),
            "playback_fps": round(self.playback_fps, 1),
            "pipeline_fps": round(self.pipeline_fps, 1),
            "inference_fps": round(self._inference_fps if self._inference_fps > 0 else self.pipeline_fps, 1),
            "latency_ms": round(self._avg_latency_ms, 1),
            "playback_speed": self._speed,
            "is_paused": self._paused,
            "is_file": isinstance(self._source, FileSource),
            "active_tracks": self._store.count_active(),
            "total_tracks": len(snap),
            "people_detected": people,
            "vehicles_detected": vehicles,
            "active_people": active_people,
            "active_vehicles": active_vehicles,
            "events_committed": self.events_committed,   # C9 rename
            "zone_person_counts": fence.zone_person_counts() if fence else {},
            "error": self.error or None,
            "uptime_s": round(time.time() - self._started_at, 1),
            "layers": self.get_layers(),
        }


# ---- app-scoped writer holder (installed by main lifespan) ----

_module_writer: Optional[EventWriter] = None


def set_writer(writer: Optional[EventWriter]) -> None:
    global _module_writer
    _module_writer = writer


def get_writer() -> Optional[EventWriter]:
    return _module_writer


# ---- one-active-session registry (module-level, minimal) ----

_active: Optional[ProcessingSession] = None
_lock = threading.Lock()


def get_active_session() -> Optional[ProcessingSession]:
    with _lock:
        return _active


def start_session(source: VideoSource,
                  zones: Optional[ZoneStore] = None,
                  dao: Optional[DAO] = None,
                  writer: Optional[EventWriter] = None,
                  hub: Optional[SseHub] = None,
                  reid_service=None) -> ProcessingSession:
    global _active
    with _lock:
        if _active is not None and _active.status in ("running", "starting"):
            raise SessionError(
                f"one active session rule: session '{_active.source_id}' is "
                f"{_active.status} — stop it first"
            )
        session = ProcessingSession(source, zones=zones, dao=dao,
                                    writer=writer, hub=hub,
                                    reid_service=reid_service)
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
    type=rtsp   -> RtspSource(uri)    (validated by RtspSource at open)
    """
    stype = spec.get("type")
    if stype == "webcam":
        return WebcamSource(int(spec.get("index", 0)))
    if stype == "file":
        path = spec.get("path", "")
        if not path:
            raise SessionError("file session requires 'path'")
        return FileSource(path)
    if stype == "rtsp":
        uri = spec.get("uri", "")
        if not uri:
            raise SessionError("rtsp session requires 'uri'")
        try:
            return RtspSource(uri)
        except SourceError as e:
            raise SessionError(str(e)) from e
    raise SessionError(f"unknown source type: {stype!r} (use 'webcam', 'file', or 'rtsp')")


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(
        timespec="milliseconds")
