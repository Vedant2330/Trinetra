"""TRINETRA Phase 7 — RTSP Stream Test & Benchmark Tool.

Connects to an RTSP IP camera stream using RtspSource, evaluates:
- TCP transport handshake
- Credential sanitization in telemetry & source_id
- Stream throughput (FPS), frame resolution, latency
- Frame read reliability & drop rate
- Reconnection resilience via reopen()

Run:
    ./venv/bin/python scripts/rtsp_test.py --uri "rtsp://user:pass@192.168.1.50:554/live" --frames 100
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.sources.base import SourceError, SourceState
from backend.sources.rtsp import RtspSource


def main() -> int:
    parser = argparse.ArgumentParser(description="TRINETRA RTSP Stream Benchmark")
    parser.add_argument("--uri", type=str, required=True, help="RTSP URI (e.g. rtsp://127.0.0.1:8554/live)")
    parser.add_argument("--frames", type=int, default=100, help="Number of frames to benchmark (default: 100)")
    parser.add_argument("--timeout", type=float, default=10.0, help="Timeout in seconds for stream read (default: 10.0)")
    args = parser.parse_args()

    print("=" * 65)
    print(" TRINETRA PHASE 7 — RTSP STREAM BENCHMARK")
    print("=" * 65)
    print(f" Target URI       : {args.uri}")
    print(f" Target Frame Count: {args.frames}")
    print(f" Read Timeout     : {args.timeout}s")
    print("-" * 65)

    # 1. Verification of URI parsing and credential stripping
    try:
        source = RtspSource(args.uri)
    except SourceError as e:
        print(f"[-] FAILED: Invalid RTSP source parameters: {e}")
        return 1

    print(f"[+] Initialized RtspSource:")
    print(f"    - Sanitized source_id : {source.source_id}")
    print(f"    - State               : {source.state.name}")

    if "@" in args.uri and "@" in source.source_id:
        print(f"[-] SECURITY ERROR: Credentials not sanitized from source_id: {source.source_id}")
        return 1
    print(f"[+] Security check passed: credentials properly stripped from source_id.")

    # 2. Test Stream Connection
    print("\n[*] Opening RTSP connection (enforcing TCP transport)...")
    t0 = time.time()
    try:
        source.open()
    except SourceError as e:
        print(f"[-] FAILED to open RTSP stream: {e}")
        return 1
    t_open = (time.time() - t0) * 1000
    w, h = source.size
    print(f"[+] RTSP Stream connected in {t_open:.2f}ms")
    print(f"    - Resolution : {w}x{h}")
    print(f"    - State      : {source.state.name}")

    # 3. Read Benchmark
    print(f"\n[*] Reading {args.frames} frames...")
    frames_read = 0
    read_times = []
    start_bench = time.time()
    last_frame_time = time.time()

    try:
        while frames_read < args.frames:
            if time.time() - last_frame_time > args.timeout:
                print(f"\n[-] ERROR: Read timed out after {args.timeout}s of silence.")
                break

            t_read_start = time.time()
            packet = source.read()
            t_read_dur = (time.time() - t_read_start) * 1000

            if packet is not None:
                frames_read += 1
                read_times.append(t_read_dur)
                last_frame_time = time.time()
                if frames_read % 20 == 0 or frames_read == args.frames:
                    print(f"    -> Read {frames_read}/{args.frames} frames "
                          f"(last frame read latency: {t_read_dur:.2f}ms)")
            else:
                time.sleep(0.005)

    except KeyboardInterrupt:
        print("\n[!] Benchmark interrupted by user.")
    finally:
        total_time = time.time() - start_bench

    # 4. Metrics
    print("\n" + "=" * 65)
    print(" BENCHMARK RESULTS")
    print("=" * 65)
    if frames_read > 0:
        fps = frames_read / total_time
        avg_lat = sum(read_times) / len(read_times)
        min_lat = min(read_times)
        max_lat = max(read_times)
        print(f" Frames Read      : {frames_read}/{args.frames}")
        print(f" Total Duration   : {total_time:.2f}s")
        print(f" Effective FPS    : {fps:.2f} fps")
        print(f" Read Latency     : avg={avg_lat:.2f}ms | min={min_lat:.2f}ms | max={max_lat:.2f}ms")
    else:
        print("[-] No frames could be read from the stream.")

    # 5. Test Reconnection
    print("\n[*] Testing reopen() method...")
    reopen_ok = source.reopen()
    if reopen_ok and source.state == SourceState.OPEN:
        print("[+] reopen() succeeded cleanly: state is OPEN")
    else:
        print(f"[-] reopen() failed or state not OPEN: state={source.state.name}")

    # 6. Release
    source.release()
    print(f"[+] Stream released cleanly: state={source.state.name}")
    print("=" * 65)

    return 0 if frames_read > 0 and reopen_ok else 1


if __name__ == "__main__":
    sys.exit(main())
