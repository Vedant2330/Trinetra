"""M3 full-stack MJPEG test — REAL server, REAL pipeline, REAL HTTP.

Boots the actual uvicorn app on a test port, starts a REAL file session
(YOLO + ByteTrack + annotation + JPEG), connects a stdlib http.client
MJPEG reader, parses genuine multipart frames, and validates JPEG payloads.
Also verifies: no-session 404s, session-status endpoint, frame.jpg, stop.
"""

from __future__ import annotations

import http.client
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

ASSETS = Path(__file__).parent / "assets"
PORT = 8931


def _json(r) -> dict:
    return json.loads(r.read().decode())


def _wait_server(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def _read_mjpeg_frames(conn: http.client.HTTPConnection, want: int,
                       max_seconds: float) -> tuple[int, int]:
    """Parse multipart/x-mixed-replace from a live response. Returns (frames, bytes)."""
    resp = conn.getresponse()
    assert resp.status == 200, f"stream status {resp.status}"
    ctype = resp.getheader("Content-Type", "")
    assert "multipart/x-mixed-replace" in ctype, ctype
    boundary = ctype.split("boundary=")[1].strip()
    assert boundary

    buf = b""
    frames = 0
    total_bytes = 0
    deadline = time.time() + max_seconds
    while frames < want and time.time() < deadline:
        chunk = resp.read(4096)
        if not chunk:
            break
        buf += chunk
        # extract complete JPEGs from stream
        while True:
            start = buf.find(b"\xff\xd8")
            if start < 0:
                buf = b""
                break
            end = buf.find(b"\xff\xd9", start)
            if end < 0:
                buf = buf[start:]
                break
            jpeg = buf[start:end + 2]
            buf = buf[end + 2:]
            if len(jpeg) > 1000:           # real frames, not stray fragments
                frames += 1
                total_bytes += len(jpeg)
    return frames, total_bytes


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app",
         "--port", str(PORT), "--log-level", "warning"],
        cwd=Path(__file__).resolve().parents[1],
    )
    try:
        assert _wait_server(PORT), "server did not boot"
        conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)

        # 1. health (M0 contract still alive)
        conn.request("GET", "/api/health")
        r = conn.getresponse()
        assert r.status == 200 and _json(r)["ok"], "health broken"
        print("[ok] /api/health")

        # 2. stream before session -> 404
        conn.request("GET", "/api/stream.mjpg")
        r = conn.getresponse()
        assert r.status == 404, f"expected 404, got {r.status}"
        r.read()
        print("[ok] stream.mjpg 404 without session")

        # 3. start REAL file session
        conn.request("POST", "/api/session/start",
                     body=f'{{"type": "file", "path": "{ASSETS / "running_clip.mp4"}"}}',
                     headers={"Content-Type": "application/json"})
        r = conn.getresponse()
        body = _json(r)
        assert r.status == 200, body
        print(f"[ok] session started: {body['session']['device']}")
        device = body["session"]["device"]

        # 4. frame.jpg returns a real JPEG (poll: first frame needs ~1-2s incl. warm-up)
        data = None
        deadline = time.time() + 15
        while time.time() < deadline:
            conn.request("GET", "/api/frame.jpg")
            r = conn.getresponse()
            data = r.read()
            if r.status == 200 and data[:2] == b"\xff\xd8":
                break
            time.sleep(0.4)
        assert data and data[:2] == b"\xff\xd8", "frame.jpg never returned a JPEG"
        print(f"[ok] frame.jpg: {len(data)} bytes JPEG")

        # 5. consume the REAL MJPEG stream (file runs ~2s at ~35fps, so
        #    connect fast and count what arrives)
        conn2 = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
        conn2.request("GET", "/api/stream.mjpg")
        frames, nbytes = _read_mjpeg_frames(conn2, want=25, max_seconds=15.0)
        print(f"[ok] mjpeg client received {frames} validated JPEG frames "
              f"({nbytes} bytes), device={device}")
        got = frames >= 15  # file may complete during read; 61 frames @ ~30fps ≈ 2s
        if not got:
            # session may have completed before we connected; check status
            conn.request("GET", "/api/session/status")
            st = _json(conn.getresponse())
            print(f"     session status: {st}")
        assert got, "client received too few frames"

        # 6. status reports real numbers
        conn.request("GET", "/api/session/status")
        st = _json(conn.getresponse())
        assert st["active"] is True or st["session"]["status"] == "completed"
        if st.get("session"):
            sp = st["session"]
            print(f"[ok] status: {sp['status']} frames={sp['frames_processed']} "
                  f"fps={sp['pipeline_fps']} device={sp['device']}")

        # 7. stop + start-again works (lifecycle)
        conn.request("POST", "/api/session/stop")
        r = conn.getresponse(); r.read()
        assert r.status == 200
        # second session (second run of same file)
        conn.request("POST", "/api/session/start",
                     body=f'{{"type": "file", "path": "{ASSETS / "running_clip.mp4"}"}}',
                     headers={"Content-Type": "application/json"})
        r = conn.getresponse(); body = _json(r)
        assert r.status == 200, body
        conn.request("POST", "/api/session/stop")
        r = conn.getresponse(); r.read()
        print("[ok] stop -> restart -> stop lifecycle clean")

        # 8. duplicate start -> 409 (one active session)
        conn.request("POST", "/api/session/start",
                     body=f'{{"type": "file", "path": "{ASSETS / "running_clip.mp4"}"}}',
                     headers={"Content-Type": "application/json"})
        r = conn.getresponse(); body = _json(r)
        assert r.status == 200
        conn.request("POST", "/api/session/start",
                     body=f'{{"type": "file", "path": "{ASSETS / "traffic_clip.mp4"}"}}',
                     headers={"Content-Type": "application/json"})
        r = conn.getresponse()
        assert r.status == 409, f"expected 409, got {r.status}"
        r.read()
        print("[ok] duplicate session rejected 409")
        conn.request("POST", "/api/session/stop")
        r = conn.getresponse(); r.read()

        print("\nM3 FULL-STACK MJPEG TEST: PASS")
        return 0
    finally:
        proc.terminate()
        proc.wait(timeout=10)


if __name__ == "__main__":
    sys.exit(main())
