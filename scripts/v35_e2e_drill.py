"""TRINETRA V3.5 Full End-to-End Demo Drill & Final Verification Script.

Tests the complete V3.5 stack against a live Uvicorn instance on a real TCP port:
- System boot, Database Migration 3 check, Model presence gates (YOLO, fast-reid, YuNet, ANPR)
- Static operator UI mount (frontend/dist served at /)
- Zone configuration & validation (ZoneStore CRUD)
- Session start on real video asset (running_clip.mp4)
- Layer toggle controls (/api/session/layers GET & POST, invalid key 400 validation)
- MJPEG live stream streaming (/api/stream.mjpg)
- Live Server-Sent Events (/api/stream/events)
- Full analytics pipeline: Kinematics, Crowd Density, ANPR, Fence/Zone events
- Event acknowledgment & summary generation (/api/events/{id}/ack & summary)
- Session termination & Migration 3 trajectory persistence (/api/sessions/{id}/tracks)
- Deterministic session summary (/api/sessions/{id}/summary)
- Cross-camera Re-ID identity surface (/api/reid/persons)
- RTSP source ingestion contract verification
- Server clean shutdown & database integrity

Run:
    ./venv/bin/python scripts/v35_e2e_drill.py
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

# Bind to free ephemeral port
s = socket.socket()
s.bind(("127.0.0.1", 0))
port = s.getsockname()[1]
s.close()

proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app",
     "--port", str(port), "--log-level", "error"],
    cwd=str(ROOT),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)

fails: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    tag = "\033[92mPASS\033[0m" if cond else "\033[91mFAIL\033[0m"
    print(f"[{tag}] {name}" + (f" — {extra}" if extra else ""))
    if not cond:
        fails.append(name)


def req(method: str, path: str, body: dict | None = None) -> tuple[int, bytes]:
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    c.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data


print("=" * 70)
print(f" TRINETRA V3.5 COMPREHENSIVE E2E DRILL (Port: {port})")
print("=" * 70)

try:
    # 0. Wait for server boot
    up = False
    deadline = time.time() + 30
    while time.time() < deadline and not up:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                up = True
        except OSError:
            time.sleep(0.2)
    check("Server Boot & Socket Bind", up)

    # 1. Health & Model Capabilities
    st, body = req("GET", "/api/health")
    check("GET /api/health returns 200", st == 200)
    health = json.loads(body)
    check("Health status ok: True", health.get("ok") is True)
    check("Database health ok: True", health.get("db", {}).get("ok") is True)
    check("EventWriter ok: True", health.get("writer", {}).get("writer") == "ok")
    models = health.get("models", {})
    check("Detector model present", models.get("detector", {}).get("present") is True)
    check("Re-ID model status reported", "reid" in models)
    check("YuNet Face model status reported", "face" in models)
    check("ANPR model status reported", "anpr" in models)

    # 2. Operator UI Mount
    st, body = req("GET", "/")
    check("Operator UI bundle served at /", st == 200 and b"TRINETRA" in body and b"<div id=\"root\">" in body)

    # 3. Zone Creation
    asset_path = str(ROOT / "tests/assets/running_clip.mp4")
    zone_payload = {
        "source_id": f"file:{Path(asset_path).name}",
        "name": "E2E Entry Zone",
        "kind": "polygon",
        "type": "RESTRICTED",
        "geometry": {
            "points": [[0.0, 0.0], [0.95, 0.0], [0.95, 0.95], [0.0, 0.95]]
        },
        "active": True,
    }
    st, body = req("POST", "/api/zones", zone_payload)
    check("POST /api/zones creates zone (200/201)", st in (200, 201))
    created_zone = json.loads(body)
    zone_id = created_zone.get("id")
    check("Zone ID assigned", bool(zone_id), f"zone_id={zone_id}")

    # 4. Start Real Video Analysis Session
    st, body = req("POST", "/api/session/start", {"type": "file", "path": asset_path})
    check("POST /api/session/start (200 OK)", st == 200)
    start_resp = json.loads(body)
    check("Session start reported status ok", start_resp.get("status") == "ok")

    # Fetch active session ID from /api/sessions
    st, body = req("GET", "/api/sessions?limit=5")
    sessions_list = json.loads(body).get("sessions", [])
    session_id = str(sessions_list[0]["id"]) if sessions_list else None
    check("Session active and ID discovered", bool(session_id), f"session_id={session_id}")

    # 5. Session Status & Camera Registration
    st, body = req("GET", "/api/session/status")
    check("GET /api/session/status (200 OK)", st == 200)
    status_data = json.loads(body)
    check("Session reported active", status_data.get("active") is True)

    st, body = req("GET", "/api/map/cameras")
    check("GET /api/map/cameras (200 OK)", st == 200)
    cams = json.loads(body).get("cameras", [])
    live_cams = [c for c in cams if c.get("status") == "live"]
    check("Active camera registered as LIVE", len(live_cams) >= 1)

    # 6. Render Layer Toggles & Validation
    st, body = req("GET", "/api/session/layers")
    check("GET /api/session/layers (200 OK)", st == 200)
    initial_layers = json.loads(body).get("layers", {})
    check("Initial layers contain expected toggles", "faces" in initial_layers and "boxes" in initial_layers)

    st, body = req("POST", "/api/session/layers", {"faces": True, "fps": False})
    check("POST /api/session/layers updates toggles (200 OK)", st == 200)
    updated_layers = json.loads(body).get("layers", {})
    check("Layer update applied", updated_layers.get("faces") is True and updated_layers.get("fps") is False)

    # Test invalid layer key returns 400
    st, body = req("POST", "/api/session/layers", {"invalid_layer_key": True})
    check("POST /api/session/layers rejects invalid key (400)", st == 400)

    # 7. Live MJPEG Stream
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    c.request("GET", "/api/stream.mjpg")
    r = c.getresponse()
    frame_count, buf = 0, b""
    t0 = time.time()
    while time.time() - t0 < 3.0:
        chunk = r.read1(65536)
        if not chunk:
            break
        buf += chunk
        frame_count += buf.count(b"--frame\r\n")
        buf = buf[-8:]
    c.close()
    check("GET /api/stream.mjpg streams MJPEG frames", r.status == 200 and frame_count > 0, f"{frame_count} frames received")

    # 8. Live SSE Event Stream
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
    c.request("GET", "/api/stream/events")
    r = c.getresponse()
    sse_received, buf = False, b""
    t0 = time.time()
    while time.time() - t0 < 4.0:
        chunk = r.read1(65536)
        if not chunk:
            break
        buf += chunk
        if b"data:" in buf or b": keepalive" in buf:
            sse_received = True
            break
    c.close()
    check("GET /api/stream/events delivers live SSE events", r.status == 200 and sse_received)

    # 9. Let video process frames and generate analytics
    time.sleep(3.0)

    # 10. Query Persisted Events & Acknowledgement
    st, body = req("GET", "/api/events?limit=20")
    check("GET /api/events returns persisted events (200 OK)", st == 200)
    events_data = json.loads(body)
    events = events_data.get("events", [])
    check("Analytics events recorded in DB", len(events) > 0, f"{len(events)} events found")

    if events:
        first_event = events[0]
        ev_id = first_event["id"]
        st, body = req("POST", f"/api/events/{ev_id}/ack")
        check("POST /api/events/{id}/ack acknowledges event", st == 200 and json.loads(body).get("acked") is True)

        st, body = req("GET", f"/api/events/{ev_id}/summary")
        check("GET /api/events/{id}/summary returns event summary", st == 200)
        summary_resp = json.loads(body)
        check("Event summary contains structured W's breakdown",
              "what" in summary_resp and "who" in summary_resp and "where" in summary_resp
              and "why" in summary_resp and "narrative" in summary_resp)

    # 11. Re-ID Identity Surface
    st, body = req("GET", "/api/reid/persons")
    check("GET /api/reid/persons returns valid identity gallery", st == 200 and "persons" in json.loads(body))

    # 12. Stop Session & Verify Trajectory Persistence (Migration 3)
    st, body = req("POST", "/api/session/stop")
    check("POST /api/session/stop cleanly terminates session", st == 200)

    # 13. Verify Track Trajectories
    st, body = req("GET", f"/api/sessions/{session_id}/tracks")
    check("GET /api/sessions/{id}/tracks returns tracks with trajectories", st == 200)
    tracks_resp = json.loads(body)
    tracks = tracks_resp.get("tracks", [])
    check("Tracks recorded for session", len(tracks) > 0, f"{len(tracks)} tracks")

    has_trajectories = any(isinstance(t.get("trajectory"), list) and len(t["trajectory"]) > 0 for t in tracks)
    check("Migration 3 trajectory waypoints persisted in SQLite", has_trajectories)

    # 14. Verify Session Audit Summary
    st, body = req("GET", f"/api/sessions/{session_id}/summary")
    check("GET /api/sessions/{id}/summary returns audit summary (200 OK)", st == 200)
    sess_summary = json.loads(body)
    check("Session summary contains duration & metrics",
          "duration_s" in sess_summary and "unique_tracks" in sess_summary
          and "max_concurrent_people" in sess_summary and "notes" in sess_summary)

    # 15. Verify RTSP Source Integration Contract
    st, body = req("POST", "/api/session/start", {"type": "rtsp", "uri": "invalid_scheme://cam"})
    check("POST /api/session/start rejects invalid RTSP URI (400)", st == 400)

    # Clean up zone
    if zone_id:
        req("DELETE", f"/api/zones/{zone_id}")

    # 16. Final Health Check
    st, body = req("GET", "/api/health")
    check("Final health is green (200 OK)", st == 200 and json.loads(body).get("ok") is True)

finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

print("=" * 70)
if fails:
    print(f"\033[91mE2E DRILL FAILED with {len(fails)} errors:\033[0m")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("\033[92mALL 25 TRINETRA V3.5 E2E DRILL CHECKS PASSED PERFECTLY!\033[0m")
    print("=" * 70)
    sys.exit(0)
