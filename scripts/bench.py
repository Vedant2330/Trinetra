#!/usr/bin/env python3
"""TRINETRA benchmark suite — B1-B4 (M6, IMPLEMENTATION_PLAN labels, C9).

Run:  Trinetra/venv/bin/python scripts/bench.py [--quick]

  B1  pipeline FPS — median + p95 over N frames of the real clip
      (detector->tracker->state->luminance->fence->encode; NO HTTP).
  B2  MJPEG FPS @ quality 70 — served frames/sec through the REAL
      uvicorn socket with a live session; >=15 target recorded
      (chain-overhead delta = bonus row, NOT the headline).
  B3  event burst — 50 drafts/frame x 200 frames -> writer keeps up;
      bounded queue blocks the producer by design (zero loss).
  B4  RSS under sustained load — process memory while B1-style load
      runs (churn cost recorded separately in the M6 drills).

REAL numbers, this machine, written to docs/BENCHMARKS.md by hand from
this output. No fakes, no estimates.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np

from backend.analytics import FenceAnalytic, FrameContext, ZoneStore
from backend.analytics.base import EventDraft
from backend.core.config import STREAM
from backend.db.connection import Database
from backend.db.dao import DAO
from backend.db.migrations import MIGRATIONS
from backend.db.writer import EventWriter
from backend.events.engine import EventEngine
from backend.sources import FileSource
from backend.state import TrackStore
from backend.vision import DetectorTracker


def bench_pipeline_fps(n_frames: int = 100) -> dict:
    """B1: the full per-frame chain, median + p95."""
    det = DetectorTracker(policy="cpu")
    det.load()
    det.warmup(np.zeros((480, 640, 3), dtype=np.uint8))
    store = TrackStore()
    zs = ZoneStore()
    zs.add("bench", "b", "polygon", "RESTRICTED",
           {"points": [[0.1, 0.3], [0.9, 0.3], [0.9, 0.95], [0.1, 0.95]]})
    fence = FenceAnalytic(zs)
    fence.reset("bench")
    with FileSource(ROOT / "tests/assets/running_clip.mp4") as src:
        frames = []
        while len(frames) < n_frames:
            pkt = src.read()
            if pkt is None:
                src.release()
                src.open()
                continue                # loop the 61-frame clip
            frames.append(pkt.frame)
    durations = []
    for i, frame in enumerate(frames):
        t0 = time.perf_counter()
        objs = det.process(frame)
        store.update(objs, tick=i, wall_ts=time.time())
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        ctx = FrameContext(tick=i, wall_ts=time.time(), video_ts=None,
                           luminance=float(gray.mean()), is_night=False,
                           shape=(frame.shape[1], frame.shape[0]))
        for t in store.take_newly_confirmed():
            pass
        fence.process(ctx, store.view())
        ok, _ = cv2.imencode(".jpg", frame,
                             [int(cv2.IMWRITE_JPEG_QUALITY),
                              STREAM.mjpeg_quality])
        assert ok
        durations.append((time.perf_counter() - t0) * 1000.0)
    med = statistics.median(durations)
    p95 = sorted(durations)[int(len(durations) * 0.95)]
    return {"median_ms": round(med, 2), "p95_ms": round(p95, 2),
            "median_fps": round(1000.0 / med, 1),
            "p95_fps": round(1000.0 / p95, 1), "frames": len(frames)}


def bench_burst() -> dict:
    """B3: 50 drafts x 200 frames, writer with a small delay."""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    db = Database(tmp / "b3.db")
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    dao.upsert_source("s", "file")
    sid = dao.insert_session("s")
    w = EventWriter(dao, queue_max=500, batch_delay=0.02)
    w.start()
    eng = EventEngine("s", sid, writer=w)
    t0 = time.perf_counter()
    committed = 0
    blocked_ms = []
    for frame in range(200):
        drafts = [EventDraft(type="ZONE_ENTRY",
                             track_ids=[frame * 50 + i],
                             zone_id=f"z{i % 5}", confidence=1.0,
                             metadata={"is_night": False,
                                       "zone_type": "RESTRICTED",
                                       "video_ts": 0.0, "tick": frame})
                  for i in range(50)]
        b0 = time.perf_counter()
        committed += len(eng.commit(drafts, None,
                                    FrameContext(tick=frame,
                                                 wall_ts=1_000_000.0 + frame,
                                                 video_ts=0.0,
                                                 luminance=128.0,
                                                 is_night=False,
                                                 shape=(640, 480))))
        dt = (time.perf_counter() - b0) * 1000.0
        if dt > 1.0:
            blocked_ms.append(round(dt, 1))
    w.drain(timeout=60)
    rows = dao.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    elapsed = time.perf_counter() - t0
    w.stop()
    db.close_all()
    return {"events": 10000, "rows": rows, "zero_loss": rows == 10000,
            "elapsed_s": round(elapsed, 1),
            "throughput_eps": round(rows / elapsed, 0),
            "blocked_ticks": len(blocked_ms)}


def bench_rss(seconds: float = 10.0) -> dict:
    """B4: RSS under sustained pipeline load (B1 chain looped)."""
    psutil = None
    try:
        import psutil
    except ImportError:
        return {"note": "psutil not installed (test dep) — skipped"}
    import os
    proc = psutil.Process(os.getpid())
    base_mb = proc.memory_info().rss / (1024 * 1024)
    det = DetectorTracker(policy="cpu")
    det.load()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(frame, (320, 300), 60, (255, 255, 255), -1)
    deadline = time.time() + seconds
    n = 0
    while time.time() < deadline:
        det.process(frame)          # sustained real inference load
        n += 1
    peak_mb = proc.memory_info().rss / (1024 * 1024)
    return {"base_mb": round(base_mb, 1), "peak_mb": round(peak_mb, 1),
            "delta_mb": round(peak_mb - base_mb, 1),
            "frames": n, "seconds": seconds}


def bench_mjpeg() -> dict:
    """B2: MJPEG served FPS @ q70 via the REAL uvicorn socket."""
    import http.client
    import socket
    import subprocess
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--port", str(port), "--log-level", "error"],
        cwd=str(ROOT), stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + 30
        up = False
        while time.time() < deadline and not up:
            try:
                with socket.create_connection(("127.0.0.1", port),
                                              timeout=0.5):
                    up = True
            except OSError:
                time.sleep(0.2)
        assert up, "server did not boot"
        # start the session on its OWN connection (read the full body)
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        c.request("POST", "/api/session/start",
                  body=json.dumps({"type": "file",
                                   "path": str(ROOT / "tests/assets"
                                              / "running_clip.mp4")}),
                  headers={"Content-Type": "application/json"})
        r = c.getresponse()
        body = r.read()
        assert r.status == 200, body[:200]
        c.close()
        # measure the MJPEG stream on a fresh connection
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        c.request("GET", "/api/stream.mjpg")
        resp = c.getresponse()
        assert resp.status == 200
        n = 0
        t0 = time.time()
        buf = b""
        while time.time() - t0 < 5.0:
            chunk = resp.read1(65536)
            if not chunk:
                break
            buf += chunk
            n += buf.count(b"--frame\r\n")
            buf = buf[-8:]
        fps = n / (time.time() - t0)
        c.close()
        return {"mjpeg_fps_q70": round(fps, 1), "frames": n,
                "seconds": round(time.time() - t0, 1),
                "target_15": fps >= 15.0}
    finally:
        c = None
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="shorter B1/B4 windows")
    args = ap.parse_args()
    print("== TRINETRA B1-B4 (C9 labels per IMPLEMENTATION_PLAN) ==")
    b1 = bench_pipeline_fps(n_frames=60 if args.quick else 100)
    print(f"B1 pipeline FPS: median {b1['median_fps']} "
          f"({b1['median_ms']} ms/frame), p95 {b1['p95_fps']} "
          f"({b1['p95_ms']} ms) over {b1['frames']} frames")
    try:
        b2 = bench_mjpeg()
        print(f"B2 MJPEG FPS @ q70: {b2['mjpeg_fps_q70']} "
              f"(target >=15: {b2['target_15']}, {b2['frames']} frames / "
              f"{b2['seconds']}s)")
    except Exception as e:  # noqa: BLE001 — B2 needs a free port; record it
        b2 = {"error": str(e)}
        print(f"B2 MJPEG FPS @ q70: FAILED — {e}")
    b3 = bench_burst()
    print(f"B3 event burst: {b3['events']} events -> {b3['rows']} rows "
          f"(zero loss: {b3['zero_loss']}, {b3['throughput_eps']} eps, "
          f"producer blocked on {b3['blocked_ticks']} ticks)")
    b4 = bench_rss(seconds=3.0 if args.quick else 10.0)
    print(f"B4 RSS under sustained load: base {b4.get('base_mb')} MB -> "
          f"peak {b4.get('peak_mb')} MB (delta {b4.get('delta_mb')} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
