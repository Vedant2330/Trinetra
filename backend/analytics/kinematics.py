"""TRINETRA Kinematic & Trajectory Analytics — Clean-Room Implementation.

Calculates kinematic heuristics (velocity, acceleration, directional
straightness, dwell time) directly from TrackState.positions.
Zero AGPL imports or third-party code.

Detectors:
- SUSPECTED_RUNNING: velocity and displacement sustained across >= 3 ticks.
- SUSPECTED_ABNORMAL_MOVEMENT: erratic directional thrashing at high speed.
- LOITERING: track confirmed >= loiter_dwell_sec with spatial radius < 80px.
- NIGHT_MOVEMENT: track active in night context (luminance < 40) >= 5 ticks.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Any, Optional
import numpy as np

from backend.analytics.base import AnalyticModule, EventDraft, FrameContext


class KinematicTrajectoryAnalytic(AnalyticModule):
    """Clean-room kinematic behavior analyzer operating on TrackState positions."""

    id = "kinematics"

    def __init__(
        self,
        fps: float = 25.0,
        velocity_thresh: float = 150.0,
        loiter_dwell_sec: float = 15.0,
    ) -> None:
        self._fps = max(1.0, float(fps))
        self._velocity_thresh = float(velocity_thresh)
        self._loiter_dwell_sec = float(loiter_dwell_sec)
        self._session_id = ""

        # Per-track consecutive tick counters
        self._consecutive_running: dict[int, int] = {}
        self._consecutive_abnormal: dict[int, int] = {}
        self._consecutive_night: dict[int, int] = {}

        # Per-track cooldown timestamps (wall_ts)
        self._last_running_ts: dict[int, float] = {}
        self._last_abnormal_ts: dict[int, float] = {}
        self._last_loiter_ts: dict[int, float] = {}
        self._last_night_ts: dict[int, float] = {}

        # Rolling speed observations for baseline
        self._speed_samples: deque[float] = deque(maxlen=100)

    def set_fps(self, fps: float) -> None:
        """Calibrate the tick→seconds conversion to the ACTUAL source
        FPS (container metadata). The session calls this after open();
        the analytic must not assume 25 for a 30fps file (a 1.2× time
        skew mis-calibrates running speeds and loiter dwell). Live
        sources without metadata keep the constructed default (the
        session falls back to the measured pipeline rate)."""
        fps = float(fps)
        if fps > 0:
            self._fps = max(1.0, fps)

    def reset(self, session_id: str) -> None:
        """Clear all per-track kinematic states."""
        self._session_id = session_id
        self._consecutive_running.clear()
        self._consecutive_abnormal.clear()
        self._consecutive_night.clear()
        self._last_running_ts.clear()
        self._last_abnormal_ts.clear()
        self._last_loiter_ts.clear()
        self._last_night_ts.clear()
        self._speed_samples.clear()

    def process(self, ctx: FrameContext, tracks: Any) -> list[EventDraft]:
        """Evaluate kinematic heuristics on active tracks for the current tick."""
        drafts: list[EventDraft] = []
        wall_ts = ctx.wall_ts
        active = getattr(tracks, "active_tracks", [])
        active_ids = set()

        for track in active:
            tid = track.track_id
            active_ids.add(tid)
            positions = list(track.positions)  # list of (x, y, tick)
            if len(positions) < 2:
                continue

            # 1. Kinematic calculations over window W=10
            window = positions[-10:]
            num_pts = len(window)
            if num_pts < 2:
                continue

            first_pt, last_pt = window[0], window[-1]
            dt_ticks = max(1, last_pt[2] - first_pt[2])
            dt_sec = dt_ticks / self._fps

            # Segment lengths (path length L) and net displacement (D)
            seg_lengths = []
            for i in range(1, num_pts):
                dx = window[i][0] - window[i - 1][0]
                dy = window[i][1] - window[i - 1][1]
                seg_lengths.append(math.hypot(dx, dy))

            path_len = sum(seg_lengths)
            net_disp = math.hypot(last_pt[0] - first_pt[0], last_pt[1] - first_pt[1])
            speed_px_s = path_len / dt_sec if dt_sec > 0 else 0.0
            self._speed_samples.append(speed_px_s)

            dir_ratio = net_disp / (path_len + 1e-5)  # 1.0 = straight, ~0.0 = thrashing

            # --- Heuristic 1: SUSPECTED_RUNNING ---
            # Speed score (normalized to 80px/s), disp score (150px), direction score
            speed_score = min(1.0, speed_px_s / 80.0)
            disp_score = min(1.0, net_disp / 150.0)
            dir_score = min(1.0, dir_ratio)
            run_conf = 0.5 * speed_score + 0.3 * disp_score + 0.2 * dir_score

            if run_conf >= 0.50 and speed_px_s >= 80.0:
                self._consecutive_running[tid] = self._consecutive_running.get(tid, 0) + 1
            else:
                self._consecutive_running[tid] = 0

            if self._consecutive_running.get(tid, 0) >= 3:
                if tid not in self._last_running_ts or (wall_ts - self._last_running_ts[tid]) >= 5.0:
                    self._last_running_ts[tid] = wall_ts
                    drafts.append(
                        EventDraft(
                            type="SUSPECTED_RUNNING",
                            track_ids=[tid],
                            zone_id=None,
                            direction=None,
                            confidence=float(round(run_conf, 2)),
                            metadata={
                                "is_night": ctx.is_night,
                                "speed_px_s": round(speed_px_s, 2),
                                "displacement_px": round(net_disp, 2),
                                "confidence": round(run_conf, 2),
                                "consecutive_ticks": self._consecutive_running[tid],
                                "video_ts": ctx.video_ts,
                                "tick": ctx.tick,
                            },
                        )
                    )

            # --- Heuristic 2: SUSPECTED_ABNORMAL_MOVEMENT ---
            # Baseline speed from rolling samples
            baseline = (
                float(np.median(list(self._speed_samples)))
                if self._speed_samples
                else 40.0
            )
            abnormal_speed_thresh = max(2.0 * baseline, 120.0)

            if speed_px_s > abnormal_speed_thresh and dir_ratio < 0.30 and path_len >= 30.0:
                self._consecutive_abnormal[tid] = self._consecutive_abnormal.get(tid, 0) + 1
            else:
                self._consecutive_abnormal[tid] = 0

            if self._consecutive_abnormal.get(tid, 0) >= 3:
                if tid not in self._last_abnormal_ts or (wall_ts - self._last_abnormal_ts[tid]) >= 5.0:
                    self._last_abnormal_ts[tid] = wall_ts
                    drafts.append(
                        EventDraft(
                            type="SUSPECTED_ABNORMAL_MOVEMENT",
                            track_ids=[tid],
                            zone_id=None,
                            direction=None,
                            confidence=0.85,
                            metadata={
                                "is_night": ctx.is_night,
                                "speed_px_s": round(speed_px_s, 2),
                                "dir_score": round(dir_ratio, 2),
                                "consecutive_ticks": self._consecutive_abnormal[tid],
                                "video_ts": ctx.video_ts,
                                "tick": ctx.tick,
                            },
                        )
                    )

            # --- Heuristic 3: LOITERING ---
            dwell_duration = max(
                (track.last_tick - track.first_tick) / self._fps,
                track.last_seen - track.first_seen if hasattr(track, "first_seen") else 0.0,
            )
            if dwell_duration >= self._loiter_dwell_sec:
                xs = [p[0] for p in positions]
                ys = [p[1] for p in positions]
                cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
                max_radius = max(math.hypot(x - cx, y - cy) for x, y in zip(xs, ys))

                if max_radius < 80.0:
                    if tid not in self._last_loiter_ts or (wall_ts - self._last_loiter_ts[tid]) >= 15.0:
                        self._last_loiter_ts[tid] = wall_ts
                        drafts.append(
                            EventDraft(
                                type="LOITERING",
                                track_ids=[tid],
                                zone_id=None,
                                direction=None,
                                confidence=0.90,
                                metadata={
                                    "is_night": ctx.is_night,
                                    "dwell_seconds": round(dwell_duration, 1),
                                    "bounding_radius": round(max_radius, 1),
                                    "video_ts": ctx.video_ts,
                                    "tick": ctx.tick,
                                },
                            )
                        )

            # --- Heuristic 4: NIGHT_MOVEMENT ---
            if ctx.is_night:
                self._consecutive_night[tid] = self._consecutive_night.get(tid, 0) + 1
                if self._consecutive_night[tid] >= 5:
                    if tid not in self._last_night_ts or (wall_ts - self._last_night_ts[tid]) >= 10.0:
                        self._last_night_ts[tid] = wall_ts
                        drafts.append(
                            EventDraft(
                                type="NIGHT_MOVEMENT",
                                track_ids=[tid],
                                zone_id=None,
                                direction=None,
                                confidence=0.80,
                                metadata={
                                    "is_night": True,
                                    "luminance": round(ctx.luminance, 2),
                                    "consecutive_ticks": self._consecutive_night[tid],
                                    "video_ts": ctx.video_ts,
                                    "tick": ctx.tick,
                                },
                            )
                        )
            else:
                self._consecutive_night[tid] = 0

        # Purge tracking state for stale/disappeared tracks
        for tid in list(self._consecutive_running):
            if tid not in active_ids:
                self._consecutive_running.pop(tid, None)
                self._consecutive_abnormal.pop(tid, None)
                self._consecutive_night.pop(tid, None)

        return drafts

    def update(
        self,
        tracks: list[Any],
        frame: np.ndarray,
        video_ts: float = 0.0,
    ) -> list[EventDraft]:
        """Direct update method for standalone callers and unit testing."""
        h, w = frame.shape[:2]
        gray = frame if len(frame.shape) == 2 else np.mean(frame, axis=2)
        luma = float(np.mean(gray))
        ctx = FrameContext(
            tick=0,
            wall_ts=video_ts,
            video_ts=video_ts,
            luminance=luma,
            is_night=(luma < 40.0),
            shape=(w, h),
        )

        class _SimpleTrackView:
            def __init__(self, t_list: list[Any]) -> None:
                self.active_tracks = t_list

        return self.process(ctx, _SimpleTrackView(tracks))
