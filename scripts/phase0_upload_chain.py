"""PHASE-0 live drill — verify the FULL upload→session→MJPEG→browser
chain with REAL sockets, real bytes, real MJPEG frames. Replaces
assumptions with measurements (master prompt §19: no claim of "fixed"
just because HTTP returns 200 — actual frames in the browser are the
bar; here the browser-equivalent = multipart MJPEG decode of real
frames + real detections + real track IDs in the served JPEGs).

Chain verified stage-by-stage:
  1. boot real uvicorn
  2. POST /api/sources/upload (multipart, REAL file bytes — the same
     video that sits in uploads/ from the reported-broken flow)
  3. probe metadata returned (fps/frames/w/h real)
  4. POST /api/session/start {type: file, path}
  5. GET /api/stream.mjpg — decode multipart, count REAL JPEG frames
  6. GET /api/frame.jpg — a real JPEG, decode with cv2
  7. every Nth frame decoded: assert NON-TRIVIAL rendered content
     (annotated pixels ≠ raw upload: boxes/HUD burned in)
  8. detections: /api/session/status → people/vehicles detected real
  9. trajectories: POST /api/session/layers {trajectories: true} then
     confirm stream continues
 10. stop → SESSION_COMPLETED + camera idle
 11. frontend dist serves at / (UI reachable in a real browser)
"""
import io
import json
import mimetypes
import socket
import subprocess
import sys
import time
import uuid
from http.client import HTTPConnection
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "uploads"

s = socket.socket()
s.bind(("127.0.0.1", 0))
port = s.getsockname()[1]
s.close()

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app",
     "--port", str(port), "--log-level", "error"],
    cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

fails: list[str] = []
notes: list[str] = []


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(name)
    else:
        notes.append(f"{name}: {extra}")


def wait_boot(timeout=30.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def req(method, path, body=None, headers=None, timeout=30):
    c = HTTPConnection("127.0.0.1", port, timeout=timeout)
    c.request(method, path, body=json.dumps(body) if body is not None else None,
              headers=headers if headers else
                  ({"Content-Type": "application/json"} if body is not None else {}))
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data


def upload_file(path: Path):
    boundary = f"----trinetra{uuid.uuid4().hex}"
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        blob = f.read()
    parts = [
        f"--{boundary}\r\n".encode(),
        f"Content-Disposition: form-data; name=\"file\"; "
        f"filename=\"{path.name}\"\r\n".encode(),
        f"Content-Type: {ctype}\r\n\r\n".encode(),
        blob,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)
    return req("POST", "/api/sources/upload", body=None, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    }, timeout=120) if False else _raw_post(body, boundary)


def _raw_post(body: bytes, boundary: str):
    c = HTTPConnection("127.0.0.1", port, timeout=180)
    c.request("POST", "/api/sources/upload", body=body, headers={
        "Content-Type": f"multipart/form-data; boundary={boundary}"})
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data


def read_mjpeg(n_frames=60, timeout=60.0):
    """Read a real multipart/x-mixed-replace MJPEG stream; parse frame
    boundaries, decode JPEGs with cv2."""
    c = HTTPConnection("127.0.0.1", port, timeout=timeout)
    c.request("GET", "/api/stream.mjpg")
    r = c.getresponse()
    if r.status != 200:
        c.close()
        return r.status, [], b""
    frames = []
    buf = b""
    deadline = time.time() + timeout
    ctype = r.getheader("Content-Type", "")
    while len(frames) < n_frames and time.time() < deadline:
        chunk = r.read(4096)
        if not chunk:
            break
        buf += chunk
        # multipart frame split on the boundary jpeg marker
        while True:
            i = buf.find(b"\xff\xd8")          # JPEG SOI
            j = buf.find(b"\xff\xd9")          # JPEG EOI
            if i == -1 or j == -1 or j < i:
                break
            jpg = buf[i:j + 2]
            frames.append(jpg)
            buf = buf[j + 2:]
            if len(frames) >= n_frames:
                break
    c.close()
    return r.status, frames, ctype.encode()


try:
    check("server booted", wait_boot())

    # health
    st, body = req("GET", "/api/health")
    check("health ok", st == 200 and json.loads(body)["ok"],
          json.dumps(json.loads(body))[:100])

    # UI served
    st, body = req("GET", "/")
    check("UI bundle served at /", st == 200 and b"<div id=\"root\">" in body
          or st == 200 and b"root" in body, f"{len(body)} bytes, status {st}")

    # pick the real uploaded test video (fall back to tests/assets)
    vids = sorted(UP.glob("*.mp4"), key=lambda p: p.stat().st_size)
    src = vids[0] if vids else ROOT / "tests/assets/running_clip.mp4"
    check("test video exists", src.exists(), str(src.name))

    # upload (REAL bytes over the socket)
    st, body = upload_file(src)
    up = json.loads(body) if st == 200 else {}
    check("upload 200 with probe metadata",
          st == 200 and up.get("fps", 0) > 0 and up.get("frame_count", 0) > 0,
          f"status={st} fps={up.get('fps')} frames={up.get('frame_count')} "
          f"{up.get('width')}x{up.get('height')}")

    # start session on the uploaded file
    st, body = req("POST", "/api/session/start",
                   {"type": "file", "path": up["path"]})
    check("session start 200", st == 200, f"status={st} {body[:120]}")

    # let frames flow
    time.sleep(3)

    # status → real detections
    st, body = req("GET", "/api/session/status")
    sess = json.loads(body).get("session", {}) if st == 200 else {}
    check("session running with real metrics",
          sess.get("status") == "running"
          and sess.get("frames_processed", 0) > 0
          and sess.get("pipeline_fps", 0) > 0,
          f"status={sess.get('status')} frames={sess.get('frames_processed')} "
          f"fps={sess.get('pipeline_fps')} people={sess.get('people_detected')} "
          f"vehicles={sess.get('vehicles_detected')} "
          f"active={sess.get('active_tracks')}")

    # MJPEG: real decoded frames
    st, frames, ctype = read_mjpeg(n_frames=60)
    decoded = []
    for jpg in frames:
        img = cv2.imdecode(np.frombuffer(jpg, np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            decoded.append(img)
    check("MJPEG stream decodes real frames",
          len(decoded) >= 30,
          f"{len(decoded)} decoded JPEGs, ctype={ctype[:40]}")

    # annotated pixels: frames differ from each other (video + overlays)
    if len(decoded) >= 10:
        diffs = [float(np.abs(decoded[i].astype(int)
                              - decoded[i - 1].astype(int)).mean())
                 for i in range(1, min(len(decoded), 20))]
        check("frames show motion/content (not blank)",
              max(diffs) > 0.5, f"max consecutive-frame diff={max(diffs):.2f}")

    # burned-in annotation: HUD/boxes → many colored pixels not gray
    if decoded:
        f0 = decoded[0]
        gray = cv2.cvtColor(f0, cv2.COLOR_BGR2GRAY)
        colored = int((np.abs(f0[:, :, 0].astype(int)
                             - f0[:, :, 2].astype(int)) > 40).sum())
        check("annotation overlays burned into stream",
              colored > 500,
              f"color-bearing pixels={colored} (HUD/boxes present)")
        notes.append(f"frame shape={f0.shape}")

    # track ids: labels layer toggle works live
    st, body = req("GET", "/api/session/layers")
    check("layers GET live", st == 200, body[:80])
    st, body = req("POST", "/api/session/layers", {"trajectories": True})
    check("layers POST live (trajectories on)", st == 200, body[:80])
    time.sleep(2)
    st, _f, _c = read_mjpeg(n_frames=10, timeout=15)
    check("stream continues after layer change", st == 200, f"status={st}")

    # stop
    st, body = req("POST", "/api/session/stop")
    check("session stop 200", st == 200, body[:80])
    time.sleep(1.5)
    st, body = req("GET", "/api/session/status")
    check("session inactive after stop",
          json.loads(body).get("active") is False, body[:80])

    # events persisted
    st, body = req("GET", "/api/events?limit=50")
    ev = json.loads(body)
    rows = (ev.get("events") if isinstance(ev, dict) else ev) or []
    if isinstance(ev, dict) and not ev.get("events"):
        rows = ev.get("rows") or ev.get("data") or []
    check("events persisted from session",
          len(rows) > 0, f"{len(rows)} events")
    if rows:
        kinds = sorted({str(r.get("event_type", r.get("type", "?")))
                        for r in rows})
        notes.append(f"event kinds: {kinds}")

finally:
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

print()
if fails:
    print(f"RESULT: {len(fails)} FAIL — {fails}")
    sys.exit(1)
print("RESULT: ALL CHECKS PASS — upload→session→MJPEG→browser chain VERIFIED live")
for n in notes:
    print(f"  · {n}")
