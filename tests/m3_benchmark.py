"""TRINETRA M3 — sustained webcam benchmark (real run, not a unit test).

Measures over a ~30s REAL webcam session served by the REAL uvicorn app:
  - session-side: frames processed, pipeline FPS (loop start -> JPEG published)
  - client-side: MJPEG frames delivered, delivery rate, JPEG validation
  - startup: model load + warm-up + first-visible-frame latency
  - memory: process RSS at start / mid / end (stdlib resource module)

Methodology: perf_counter everywhere; MPS numbers ride on the session's
own rolling FPS (sync'd pipeline path — encode+publish included, which is
CPU-side, so no MPS sync skew in the displayed metric).
"""

from __future__ import annotations

import http.client
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8932
DURATION = 30.0


def rss_kb(pid: int) -> int:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)],
                         capture_output=True, text=True)
    return int(out.stdout.strip() or 0)


def _wait_server(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def main() -> int:
    t_boot = time.time()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--port", str(PORT), "--log-level", "warning"],
        cwd=ROOT,
    )
    try:
        assert _wait_server(PORT), "server did not boot"
        boot_s = time.time() - t_boot
        conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=15)

        print(f"server boot: {boot_s:.1f}s (uvicorn+imports)")
        rss0 = rss_kb(proc.pid)

        # start webcam session
        t0 = time.perf_counter()
        conn.request("POST", "/api/session/start",
                     body='{"type": "webcam", "index": 0}',
                     headers={"Content-Type": "application/json"})
        r = conn.getresponse(); body = json.loads(r.read().decode())
        assert r.status == 200, body
        start_s = time.perf_counter() - t0
        print(f"session start (load+warmup): {start_s:.2f}s | device={body['session']['device']}")

        # first visible frame (single clock: perf_counter everywhere)
        t_first = None
        deadline_pc = time.perf_counter() + 15
        while time.perf_counter() < deadline_pc and t_first is None:
            conn.request("GET", "/api/frame.jpg")
            rr = conn.getresponse(); d = rr.read()
            if rr.status == 200 and d[:2] == b"\xff\xd8":
                t_first = time.perf_counter() - t0
            else:
                time.sleep(0.1)
        assert t_first is not None, "no frame within 15s"
        print(f"first visible frame: {t_first:.2f}s after start request")

        # sustained MJPEG consumption for DURATION seconds
        conn2 = http.client.HTTPConnection("127.0.0.1", PORT, timeout=20)
        conn2.request("GET", "/api/stream.mjpg")
        resp = conn2.getresponse()
        assert resp.status == 200
        frames = 0
        nbytes = 0
        buf = b""
        t_end_pc = time.perf_counter() + DURATION
        while time.perf_counter() < t_end_pc:
            chunk = resp.read(65536)
            if not chunk:
                break
            buf += chunk
            while True:
                s = buf.find(b"\xff\xd8")
                if s < 0:
                    buf = b""
                    break
                e = buf.find(b"\xff\xd9", s)
                if e < 0:
                    buf = buf[s:]
                    break
                jpeg = buf[s:e+2]
                buf = buf[e+2:]
                if len(jpeg) > 1000:
                    frames += 1
                    nbytes += len(jpeg)
        mid_rss = rss_kb(proc.pid)

        # session-side numbers (fresh connection — the streaming conn2 and the
        # long-idle `conn` cannot be trusted after 30s of streaming)
        conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=15)
        conn.request("GET", "/api/session/status")
        st = json.loads(conn.getresponse().read().decode())["session"]
        elapsed = DURATION
        print(f"\nclient delivered: {frames} frames in {elapsed:.0f}s "
              f"=> {frames/elapsed:.1f} FPS delivered | {nbytes/1e6:.1f} MB JPEG")
        print(f"session-side: processed={st['frames_processed']} pipeline_fps={st['pipeline_fps']} "
              f"active_tracks={st['active_tracks']} device={st['device']}")
        print(f"RSS: start={rss0/1024:.0f} MB -> during={mid_rss/1024:.0f} MB")

        conn.request("POST", "/api/session/stop")
        conn.getresponse().read()
        time.sleep(0.5)
        rss_end = rss_kb(proc.pid)
        print(f"RSS after stop: {rss_end/1024:.0f} MB")

        # honesty checks
        assert st["frames_processed"] > 100, "pipeline suspiciously slow"
        assert frames > 100, "delivery suspiciously slow"
        assert st["device"] in ("mps", "cpu", "cpu (fallback from mps)")
        print("\nM3 SUSTAINED WEBCAM BENCHMARK: COMPLETE")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
