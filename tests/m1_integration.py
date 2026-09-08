"""TRINETRA M1 — real integration measurement script (not a unit test).

Executes the sources end-to-end on this machine and prints MEASURED numbers:
  - FileSource: sequential read rate (decode throughput), fps metadata,
    frames-to-EOF on the MP4 and MOV fixtures
  - WebcamSource: resolution, consecutive-frame read timing on camera 0
Reference numbers only — no performance claims beyond these runs.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.sources import FileSource, WebcamSource

ASSETS = Path(__file__).parent / "assets"


def bench_file(path: Path) -> None:
    src = FileSource(path)
    src.open()
    print(f"\n[file] {path.name}  size={src.size}  fps_meta={src.fps:.1f}  "
          f"frames_meta={src.frame_count}")
    n = 0
    t0 = time.perf_counter()
    while True:
        pkt = src.read()
        if pkt is None:
            break
        n += 1
    dt = time.perf_counter() - t0
    print(f"[file] read {n} frames to EOF in {dt:.2f}s "
          f"=> {n / dt:.1f} frames/s sequential decode (REFERENCE)")
    print(f"[file] EOF state = {src.state}")
    src.release()


def bench_webcam() -> None:
    print("\n[webcam] probing camera 0 ...")
    try:
        src = WebcamSource(0)
        src.open()
    except Exception as e:
        print(f"[webcam] NOT AVAILABLE: {e}")
        return
    print(f"[webcam] opened, size={src.size}")
    n = 60
    stamps = []
    pkt = None
    for _ in range(n):
        pkt = src.read()
        if pkt is None:
            continue
        stamps.append(pkt.wall_ts)
    if len(stamps) >= 2:
        span = stamps[-1] - stamps[0]
        print(f"[webcam] read {len(stamps)} frames over {span:.2f}s "
              f"=> {len(stamps) / span:.1f} frames/s delivered (REFERENCE)")
        print(f"[webcam] frame shape={pkt.frame.shape}")
    src.release()
    print("[webcam] released")


if __name__ == "__main__":
    bench_file(ASSETS / "running_clip.mp4")
    bench_file(ASSETS / "mov_clip.mov")
    bench_webcam()
