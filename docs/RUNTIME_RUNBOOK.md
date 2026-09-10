# TRINETRA Runtime Runbook

## Boot

```bash
cd /Volumes/Vedant/vedantsecondary/Projects/SIH26/Trinetra
./venv/bin/uvicorn backend.main:app --port 8000
# health: curl -s localhost:8000/api/health   → ok:true
```
Boot is never blocked by optional capabilities (face/pose/reid/anpr/hermes/maps).
The writer, migrations, retention sweep, and zone store install in lifespan.

## Secrets (never committed — .env is gitignored)

- `GOOGLE_MAPS_API_KEY` — read at request time by /api/map/config
- `HERMES_API_KEY` — OmniRoute gateway key; Bearer on /v1/models + /chat/completions

## Full test gate (run before ANY demo)

```bash
./venv/bin/python -m pytest -q          # 363 passed expected
./venv/bin/python scripts/v35_e2e_drill.py     # 25/25
./venv/bin/python scripts/l3_runtime_probe.py   # clean exit, real metrics
./venv/bin/python scripts/phase0_upload_chain.py # upload chain regression
```

## Session operations

```bash
# file (arbitrary path, spaces/Unicode OK)
curl -X POST localhost:8000/api/session/start -H 'Content-Type: application/json' \
  -d '{"type":"file","path":"uploads/f25950_Normal_Videos.mp4"}'
# controls: /api/session/pause | resume | step | speed {"speed":2.0} | stop
curl localhost:8000/api/session/status          # canonical live state
```
EOS → status `completed` (not error). Decode corruption → honest error + SOURCE_LOST.

## Verification quick-sheet (60-second demo confidence check)

1. `/api/health` → ok:true, models present (anpr absent = honest fallback)
2. start a session → `/api/session/status` shows source_fps=30.0, frames increasing
3. `curl -m 3 localhost:8000/api/stream.mjpg -o /tmp/s.bin` → bytes > 0 (frames flow)
4. SSE: `curl -N localhost:8000/api/stream/events` → SOURCE_CONNECTED, PERSON_DETECTED…
5. `/api/events?limit=5` → persisted rows; snapshots retrievable via /api/evidence/…
6. `/api/sessions/{id}/tracks` after finalize → trajectories present
7. Hermes: `/api/hermes/status` connected:true; ask with event_id → grounded [OBSERVED] answer

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| health `ok:false` | yolov8n.pt missing | restore models/yolov8n.pt — no restart needed |
| session start 409 | one already active | `POST /api/session/stop` first |
| Hermes status 401/false | HERMES_API_KEY missing | set in .env; gateway must be running (omniroute :20128) |
| Hermes ask 503 busy/model_cooldown | gateway admission/quota | retry after retry_after_s |
| MJPEG 404 | no active session | start one |
| tracks empty on live session | rows flush at finalize | wait for stop/EOS or read live overlays |
| map shows schematic | no key or Maps unreachable | key in .env; pipeline unaffected regardless |
| events?limit page skips rows | half cursor passed | pass BOTH before+before_id |

## Restart-safety

SQLite is the durable truth: sessions/tracks/events/evidence survive uvicorn
restarts. After restart, `active_session` is null (session object is in-process);
the DB rows remain queryable for investigation.

## Desktop (legacy reference)

```bash
QT_QPA_PLATFORM=offscreen ./venv/bin/python -m backend.desktop   # CI smoke
./venv/bin/python scripts/trinetra_desktop.py                     # interactive
```
The SwiftUI app is the operator client going forward; it consumes the same
REST/SSE/MJPEG contract and requires nothing from the Qt layer.
