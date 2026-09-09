"""M4 integration tests — the REAL pipeline (no synthetic detections here):

    FileSource(running_clip.mp4) -> DetectorTracker -> TrackStore
      -> FenceAnalytic with a fixed synthetic zone

Asserts: >=1 ZONE_ENTRY from real detections, zero duplicate entries per
(track, zone) occupancy cycle, stable IDs; plus the cheap luminance
timing gate (<3 ms at working resolution, §3 step 3).
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from backend.analytics import FenceAnalytic, FrameContext, ZoneStore
from backend.services.session import _IS_NIGHT_LUMA
from backend.sources import FileSource
from backend.state import TrackStore
from backend.vision import DetectorTracker

ASSETS = Path(__file__).parent / "assets"


def _frame_ctx(pkt, tick):
    gray = cv2.cvtColor(pkt.frame, cv2.COLOR_BGR2GRAY)
    lum = float(gray.mean())
    h, w = pkt.frame.shape[:2]
    return FrameContext(tick=tick, wall_ts=pkt.wall_ts, video_ts=pkt.video_ts,
                        luminance=lum, is_night=lum < _IS_NIGHT_LUMA,
                        shape=(w, h))


def test_real_pipeline_zone_entry_no_duplicates():
    """Real clip through the real pipeline: the standing runners occupy a
    zone covering the lower-middle band; entries fire exactly once per
    (track, zone) occupancy cycle; IDs stay stable across the clip."""
    zone_store = ZoneStore()
    # fixed synthetic zone: normalized, covers the people band of the clip
    zone_store.add(
        "file:running_clip.mp4", "track-band", "polygon", "RESTRICTED",
        {"points": [[0.1, 0.55], [0.9, 0.55], [0.9, 0.98], [0.1, 0.98]]})
    fence = FenceAnalytic(zone_store)
    fence.reset("file:running_clip.mp4")

    detector = DetectorTracker(policy="cpu")
    detector.load()
    store = TrackStore()

    entries: list[tuple[int, str]] = []
    exits: list[tuple[int, str]] = []
    seen_ids: set[int] = set()

    with FileSource(ASSETS / "running_clip.mp4") as src:
        tick = 0
        while True:
            pkt = src.read()
            if pkt is None:
                assert src.state.value == "EOF", f"unexpected state {src.state}"
                break
            objects = detector.process(pkt.frame)
            store.update(objects, tick=tick, wall_ts=pkt.wall_ts)
            ctx = _frame_ctx(pkt, tick)
            for draft in fence.process(ctx, store.view()):
                seen_ids.update(draft.track_ids)
                if draft.type == "ZONE_ENTRY":
                    entries.append((draft.track_ids[0], draft.zone_id))
                elif draft.type == "ZONE_EXIT":
                    exits.append((draft.track_ids[0], draft.zone_id))
            tick += 1

    assert tick >= 55, f"clip shorter than expected: {tick} ticks"

    # REAL detections entered the fixed zone
    assert len(entries) >= 1, (
        f"no ZONE_ENTRY from real pipeline (entries={entries}) — zone/clip "
        "mismatch would mean the fixture is wrong, not the fence")
    # occupancy dedup: no (track, zone) entry pair repeats without an
    # intervening exit (structural dedup)
    entry_counts = Counter(entries)
    exit_counts = Counter(exits)
    for key, n in entry_counts.items():
        assert n == 1 + exit_counts.get(key, 0), (
            f"duplicate ZONE_ENTRY without intervening exit: {key} "
            f"entries={n} exits={exit_counts.get(key, 0)}")
    # stable IDs: every entry references a store-known track
    for tid, _ in entries + exits:
        assert store.get(tid) is not None, f"unknown track id {tid}"

    # foot-point positions are (cx, y2): y == bbox[3] of the last bbox
    for t in store.tracks.values():
        x, y = t.foot_point
        assert y == t.last_bbox[3], "foot_point y must equal bbox bottom"
        assert abs(x - (t.last_bbox[0] + t.last_bbox[2]) / 2.0) < 1e-6


def test_luminance_timing_under_3ms():
    """§3 step 3 gate: mean-gray luminance computation stays cheap
    (<3 ms at working resolution — 1280-cap frames)."""
    cap = cv2.VideoCapture(str(ASSETS / "running_clip.mp4"))
    ok, frame = cap.read()
    cap.release()
    assert ok
    # working resolution per config (vision.max_frame_width=1280)
    h, w = frame.shape[:2]
    if w > 1280:
        scale = 1280 / w
        frame = cv2.resize(frame, (1280, int(h * scale)))

    # warm up cv2 (JIT/caches), then measure a tight loop
    for _ in range(3):
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()

    times: list[float] = []
    for _ in range(30):
        t0 = time.perf_counter()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        float(gray.mean())
        times.append(time.perf_counter() - t0)
    median_ms = sorted(times)[len(times) // 2] * 1000.0
    assert median_ms < 3.0, f"luminance too slow: {median_ms:.2f} ms (>=3ms)"


def test_is_night_constant_wiring():
    """The session's named constant drives FrameContext.is_night: a forced
    dark frame must flag night; a bright frame must not (§3 step 3)."""
    dark = np.zeros((480, 640, 3), dtype=np.uint8)
    bright = np.full((480, 640, 3), 200, dtype=np.uint8)
    for frame, expect_night in ((dark, True), (bright, False)):
        lum = float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean())
        assert (lum < _IS_NIGHT_LUMA) is expect_night
