# TRINETRA Demo Runbook (SIH rehearsal)

Verified sequence — every step below was executed against the live backend on 2026-09-10 (post-audit-fix). Honest labels are binding: never present a capability as working if its gate is OFF.

## Pre-demo (5 min)

1. `./venv/bin/python -m pytest -q` → 363 passed
2. `./venv/bin/uvicorn backend.main:app --port 8000`
3. `curl -s localhost:8000/api/health` → GREEN (ok:true; anpr absent is honest — say "plate localization active, OCR gated")
4. Confirm omniroute gateway is up (Hermes status connected:true)
5. Load `uploads/f25950_Normal_Videos.mp4` + running.mp4 paths ready

## Demo script

| # | Action | Expected (verified values) |
|---|---|---|
| 1 | Start file session (f25950 clip) | status running, source_fps 30.0, device mps |
| 2 | Live video | MJPEG ~28 FPS pipeline, boxes + track IDs burned in |
| 3 | Toggle layers (trajectories ON) | POST /api/session/layers → visible path trails, <5ms round-trip |
| 4 | Detections | PERSON_DETECTED events via SSE within seconds; stable track IDs |
| 5 | Zones | draw RESTRICTED polygon → ZONE_ENTRY HIGH fires w/ snapshot |
| 6 | Zone counts | status_payload zone_person_counts live per zone |
| 7 | Faces | faces layer ON → FACE_DETECTED (conf ≥0.6) events + cyan boxes |
| 8 | Behavior | running.mp4 session → SUSPECTED_RUNNING MEDIUM (speeds 93–231 px/s, calibrated) |
| 9 | Crowd | ≥4 persons in a zone sustained → CROWD_DENSITY_MEDIUM (≥8 → HIGH) |
| 10 | Pause/Resume/Speed | status flips paused/running; speed bounds enforced |
| 11 | EOS | clip ends → status `completed` + SESSION_COMPLETED event |
| 12 | Investigation | /api/sessions → pick → /tracks (trajectory waypoints) → event summary (7-W) |
| 13 | Evidence | snapshot JPEG retrievable (200, real bytes) |
| 14 | Hermes | ask "Why did this event fire?" with event_id → [OBSERVED] grounded answer naming the real zone/track/reason |
| 15 | Hermes adversarial | ask about nonexistent event → honest "no answerable data" refusal |
| 16 | Map | key present, cameras placeable, LIVE marker matches active session |
| 17 | Stop → restart backend → investigate same session | rows persist (SQLite truth) |
| 18 | Adversarial quick-fire | bad path 400 · bogus type 400 · dup session 409 · unicode path runs |

## Talking points (honesty ledger)

- VERIFIED live: detection, tracking, zones/tripwires, trajectories, evidence, events, summaries, Hermes grounding, map API, persistence, playback timing
- HEURISTIC: behavior analytics (SUSPECTED-* prefixes stay), ANPR plate localization
- GATED OFF: ANPR OCR (no model — never a fabricated read), Re-ID cross-camera (config-off by default; say "experimental possible-match semantics")
- UNTESTED: real-camera RTSP auth (loopback verified only), night footage in drills

## Failure choreography (shows engineering maturity)

1. Delete/restore yolov8n.pt → health RED → session 503 → restore → next start recovers (no restart)
2. Kill Hermes gateway → ask returns 503 taxonomy; pipeline unaffected
3. Corrupt upload → 422, file deleted, nothing stored
