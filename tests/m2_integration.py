"""TRINETRA M2 — real integration + benchmark (not a unit test).

Executes the actual M2 pipeline on this machine:

  VideoSource -> FramePacket -> DetectorTracker -> TrackedObject[] -> TrackStore

Runs on BOTH fixtures (persons: running_clip.mp4; vehicles: traffic_clip.mp4)
and the real webcam, then benchmarks with documented methodology:

Methodology:
  - time.perf_counter() everywhere.
  - Warm-up: 5 inference calls before measured window (MPS lazy init excluded
    from warm numbers; cold first-inference reported separately).
  - MPS honesty: torch.mps.synchronize() BEFORE starting and AFTER finishing
    each measured inference interval (CPU queue must be empty) — MPS is
    asynchronous; unsynchronized timing would understate true cost.
  - Reported: median + p10/p90 of per-frame times over >=60 frames, and
    full pipeline (read -> detect+track -> state update) for the file path.
  - Config used: conf=0.35, imgsz=640, classes=person/bicycle/car/motorcycle/
    bus/truck, tracker=bytetrack.yaml (all defaults — no tuning yet, per rules).
"""

from __future__ import annotations

import statistics
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2

from backend.sources import FileSource, WebcamSource
from backend.state import TrackStore
from backend.vision import DetectorTracker, TrackedObject

ASSETS = Path(__file__).parent / "assets"


def pct(vals: list[float], p: float) -> float:
    s = sorted(vals)
    return s[min(len(s) - 1, int(len(s) * p))]


def sync_if_mps(device: str) -> None:
    if device == "mps":
        import torch
        torch.mps.synchronize()


def run_file(video: Path, policy: str) -> None:
    print(f"\n=== FILE: {video.name}  (policy={policy}) ===")
    det = DetectorTracker(policy=policy)
    det.load()
    print(f"model load: {det.load_seconds*1000:.0f} ms | device: {det.actual_device}")

    src = FileSource(video)
    src.open()
    store = TrackStore()

    frames = 0
    det_counts: Counter[str] = Counter()
    id_frames: dict[int, int] = Counter()          # id -> frames it appeared with
    id_switches_observed = 0
    prev_ids: set[int] = set()

    # --- cold inference (first call incl. lazy init) ---
    first = src.read()
    assert first is not None
    sync_if_mps(det.actual_device)
    t0 = time.perf_counter()
    objs = det.process(first.frame)
    sync_if_mps(det.actual_device)
    cold_ms = (time.perf_counter() - t0) * 1000
    print(f"first (cold) inference: {cold_ms:.0f} ms, objects={len(objs)}")

    store.update(objs, tick=0, wall_ts=first.wall_ts)
    frames = 1
    for o in objs:
        det_counts[o.class_name] += 1

    # --- warm measured window ---
    infer_times: list[float] = []
    e2e_times: list[float] = []
    WARMUP = 5
    idx = 0
    while True:
        pkt = src.read()
        if pkt is None:
            break
        t_read0 = time.perf_counter()
        sync_if_mps(det.actual_device)
        t0 = time.perf_counter()
        objs = det.process(pkt.frame)
        sync_if_mps(det.actual_device)
        t1 = time.perf_counter()
        store.update(objs, tick=frames, wall_ts=pkt.wall_ts)
        t2 = time.perf_counter()
        infer_ms = (t1 - t0) * 1000
        e2e_ms = (t2 - t_read0) * 1000
        if idx >= WARMUP:
            infer_times.append(infer_ms)
            e2e_times.append(e2e_ms)
        else:
            print(f"warm-up frame {idx}: {infer_ms:.0f} ms")
        frames += 1
        idx += 1
        for o in objs:
            det_counts[o.class_name] += 1
            if o.track_id is not None:
                id_frames[o.track_id] += 1
        cur_ids = {o.track_id for o in objs if o.track_id is not None}
        if prev_ids and cur_ids and not (cur_ids & prev_ids):
            id_switches_observed += 1  # whole-set change (all objects re-IDed)
        prev_ids = cur_ids

    src.release()

    if infer_times:
        med = statistics.median(infer_times)
        print(f"\nframes processed: {frames}")
        print(f"measured frames (post-warmup): {len(infer_times)}")
        print(f"inference+track  median {med:.1f} ms  p10 {pct(infer_times,0.1):.1f}  p90 {pct(infer_times,0.9):.1f}")
        print(f"pipeline e2e     median {statistics.median(e2e_times):.1f} ms  "
              f"=> {1000/statistics.median(e2e_times):.1f} FPS (read+infer+state)")
        print(f"class distribution (per-frame objects): {dict(det_counts)}")
        track_ids = {k: v for k, v in sorted(id_frames.items())}
        print(f"distinct track IDs: {len(track_ids)} | per-ID frame counts: {track_ids}")
        print(f"full-ID-set changes between consecutive frames: {id_switches_observed}")
        act = store.count_active("person"), store.count_active("car"), store.count_active("motorcycle")
        print(f"store end-state active (person,car,moto): {act} | total tracks: {len(store.tracks)}")
        for tid, st in list(store.tracks.items())[:6]:
            print(f"  {st!r} first@tick={st.first_tick} last@tick={st.last_tick} frames={st.frames_seen}")
    return


def run_webcam(policy: str, n_frames: int = 60) -> None:
    print(f"\n=== WEBCAM: camera 0 (policy={policy}) ===")
    try:
        src = WebcamSource(0)
        src.open()
    except Exception as e:
        print(f"WEBCAM NOT AVAILABLE: {e}")
        return
    det = DetectorTracker(policy=policy)
    det.load()
    print(f"model load: {det.load_seconds*1000:.0f} ms | device: {det.actual_device} | cam {src.size}")

    store = TrackStore()
    times: list[float] = []
    counts: Counter[str] = Counter()
    ids_seen: set[int] = set()
    got = 0
    try:
        for i in range(n_frames + 5):
            pkt = src.read()
            if pkt is None:
                continue
            t0 = time.perf_counter()
            objs = det.process(pkt.frame)
            sync_if_mps(det.actual_device)
            times.append((time.perf_counter() - t0) * 1000)
            store.update(objs, tick=i, wall_ts=pkt.wall_ts)
            got += 1
            for o in objs:
                counts[o.class_name] += 1
                if o.track_id is not None:
                    ids_seen.add(o.track_id)
    finally:
        src.release()
    if times:
        warm = times[5:]
        print(f"frames processed: {got}")
        print(f"warm inference+track: median {statistics.median(warm):.1f} ms "
              f"p90 {pct(warm, 0.9):.1f} over {len(warm)} frames")
        print(f"detections by class: {dict(counts) or 'NONE (scene had no detectable objects)'}")
        print(f"distinct track IDs seen: {len(ids_seen)} {sorted(ids_seen)[:10]}")
        print(f"store: total tracks={len(store.tracks)} active={store.count_active()}")
        print("release: OK")


if __name__ == "__main__":
    print("ultralytics defaults: tracker=bytetrack.yaml, conf=0.35, imgsz=640 "
          "(no custom tuning — measuring defaults first, per M2 rules)")
    # MPS primary (target config auto->mps); CPU comparison once, briefly
    run_file(ASSETS / "running_clip.mp4", policy="mps")
    run_file(ASSETS / "traffic_clip.mp4", policy="mps")
    run_file(ASSETS / "running_clip.mp4", policy="cpu")
    run_webcam(policy="auto")
