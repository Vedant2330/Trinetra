"""M7 E2E drill — REAL uvicorn boot + real file session + full map/UI
surface over the real socket. Verifies: /api/map/config (key PRESENCE
only — the value is never printed), cameras, camera geo PUT, sectors
CRUD, health, session start/status, MJPEG frames, SSE events, and the
built UI bundle served at / by the StaticFiles mount. Map/tile failures
must never break any of it (ADR-003).
"""
import http.client
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

s = socket.socket()
s.bind(("127.0.0.1", 0))
port = s.getsockname()[1]
s.close()

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app",
     "--port", str(port), "--log-level", "error"],
    cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

fails = []


def check(name, cond, extra=""):
    tag = "PASS" if cond else "FAIL"
    print(f"[{tag}] {name}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(name)


def req(method, path, body=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    headers = {"Content-Type": "application/json"} if body else {}
    c.request(method, path, body=json.dumps(body) if body else None,
              headers=headers)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data


try:
    up = False
    deadline = time.time() + 30
    while time.time() < deadline and not up:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                up = True
        except OSError:
            time.sleep(0.2)
    check("server booted", up)

    # 1. health
    st, body = req("GET", "/api/health")
    check("health 200", st == 200)
    health = json.loads(body)
    check("health ok:true", health.get("ok") is True)
    check("writer ok", health.get("writer", {}).get("writer") == "ok")
    check("phase M6/M7 surface", health.get("phase") in ("M6", "M7"))

    # 2. map config — KEY PRESENCE ONLY (never print the value)
    st, body = req("GET", "/api/map/config")
    check("map config 200", st == 200)
    cfg = json.loads(body)
    check("map has_key consistent", cfg["has_key"] == bool(cfg["google_maps_key"]))
    check("map simulated labeling", cfg["simulated"] is True)
    check("map demo label honest", "Demo" in cfg["label"])
    print(f"       (key present: {cfg['has_key']}; fallback={cfg['fallback']})")

    # 3. UI bundle served at / (built by god)
    st, body = req("GET", "/")
    check("UI served at / (StaticFiles mount)", st == 200
          and b"TRINETRA" in body and b"<div id=\"root\">" in body)

    # 4. start a REAL file session
    st, body = req("POST", "/api/session/start", {
        "type": "file", "path": str(ROOT / "tests/assets/running_clip.mp4")})
    check("session start 200", st == 200, body[:120])

    # 5. cameras reflect the live session source
    st, body = req("GET", "/api/map/cameras")
    check("cameras 200", st == 200)
    cams = json.loads(body)["cameras"]
    live = [c for c in cams if c["status"] == "live"]
    check("one LIVE camera (the running session)", len(live) == 1,
          live[0]["camera_id"] if live else "none")

    # 6. geo-locate the camera + sector CRUD
    st, body = req("PUT", f"/api/map/cameras/{live[0]['camera_id']}/geo",
                   {"latitude": 28.6139, "longitude": 77.2090,
                    "label": "Demo Gate Cam"})
    check("camera geo PUT 200", st == 200, body[:120])
    st, body = req("POST", "/api/map/sectors", {
        "name": "E2E Test Sector",
        "polygon": [[28.61, 77.20], [28.62, 77.21], [28.60, 77.22]]})
    check("sector create 201", st == 201, body[:120])
    sector = json.loads(body)
    st, body = req("GET", "/api/map/sectors")
    check("sector list contains it",
          any(x["id"] == sector["id"] for x in json.loads(body)["sectors"]))
    st, _ = req("DELETE", f"/api/map/sectors/{sector['id']}")
    check("sector delete 200", st == 200)

    # 7. MJPEG real frames
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    c.request("GET", "/api/stream.mjpg")
    r = c.getresponse()
    n, buf = 0, b""
    t0 = time.time()
    while time.time() - t0 < 3.0:
        chunk = r.read1(65536)
        if not chunk:
            break
        buf += chunk
        n += buf.count(b"--frame\r\n")
        buf = buf[-8:]
    c.close()
    check("MJPEG frames served", r.status == 200 and n > 0, f"{n} frames")

    # 8. SSE real events
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    c.request("GET", "/api/stream/events")
    r = c.getresponse()
    got_event, buf = False, b""
    t0 = time.time()
    while time.time() - t0 < 5.0:
        chunk = r.read1(65536)
        if not chunk:
            break
        buf += chunk
        if b"data:" in buf:
            got_event = True
            break
    c.close()
    check("SSE live events (data: frames)", r.status == 200 and got_event)

    # 9. events persisted (real SQLite rows)
    st, body = req("GET", "/api/events?limit=10")
    evs = json.loads(body)["events"]
    check("events persisted", len(evs) > 0,
          f"{len(evs)} rows, types={sorted({e['type'] for e in evs})[:4]}")

    # 10. session completes + camera returns to idle
    time.sleep(2)
    st, body = req("POST", "/api/session/stop")
    check("session stop 200", st == 200)
    st, body = req("GET", "/api/map/cameras")
    cams = json.loads(body)["cameras"]
    check("camera idle after stop", all(c["status"] != "live" for c in cams))

    # 11. NON-CRITICALITY: map-adjacent state never broke the pipeline
    st, body = req("GET", "/api/health")
    check("health still green at end", st == 200
          and json.loads(body)["ok"] is True)

finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

print()
if fails:
    print(f"E2E: {len(fails)} FAILURES: {fails}")
    raise SystemExit(1)
print("E2E: ALL CHECKS PASS")
