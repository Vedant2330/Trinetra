# TRINETRA Backend Integration Contract — v1

**Audience:** the native macOS SwiftUI operator application (built in parallel) and any future client.
**Authority:** Python backend (`backend.main:app`, FastAPI, uvicorn, port 8000, `workers=1` — in-process session state).
**Rule:** all intelligence shown by any client must originate from these endpoints. Clients never re-detect, re-track, re-segment, or fabricate state. `GET /openapi.json` always carries the machine-readable truth.

- Base URL: `http://127.0.0.1:8000`
- Content type: JSON everywhere except `/api/stream.mjpg` (multipart/x-mixed-replace) and `/api/frame.jpg` + `/api/evidence/*` (image/jpeg)
- Session model: **one active session at a time** (409 on a second start)
- All IDs are stable strings: `event_id`/`session_id`/`zone_id` = UUID4, `track_id` = integer from the authoritative ByteTrack layer
- No event, track, zone, or trajectory representation outside this API is authoritative

---

## 1. Health & capability discovery

### `GET /api/health`
Client boot check. `ok:false` means the detector weights are missing — sessions blocked (503) but server alive.
```json
{
  "ok": true, "app": "TRINETRA", "uptime_s": 12.3, "device_policy": "auto",
  "models": {
    "detector": {"file": "yolov8n.pt", "present": true, "size_mb": 6.5},
    "reid":    {"file": "fast-reid_mobilenetv2.onnx", "present": true, "size_mb": 8.9},
    "face":    {"file": "yunet.onnx", "present": true, "size_mb": 0.2},
    "pose":    {"file": "yolov8n-pose.pt", "present": true, "size_mb": 6.8},
    "anpr":    {"file": "yolov8n_plate.pt", "present": false, "size_mb": null,
                "mode": "heuristic_fallback"}
  },
  "db": {"ok": true, "user_version": 3},
  "writer": {"writer": "ok", "pending": 0, "dropped_batches": 0},
  "active_session": null,
  "reid_enabled": false, "face_enabled": true, "pose_enabled": true,
  "anpr_mode": "heuristic_fallback"
}
```
Honesty rules: `present:false` capabilities must render as UNAVAILABLE, never as off. `anpr.mode = heuristic_fallback` = plate localization only, no OCR read.

## 2. Session lifecycle

| Endpoint | Body | Notes |
|---|---|---|
| `POST /api/session/start` | `{"type":"file","path":"…"}` · `{"type":"webcam","index":0}` · `{"type":"rtsp","uri":"rtsp://…"}` | 409 if one is active; 400 invalid; 503 model missing |
| `POST /api/session/stop` | – | idempotent; stopped session returns its final payload |
| `GET  /api/session/status` | – | poll this for state + all metrics |
| `POST /api/session/pause` / `resume` / `step` | – | 404 when no session; `step` advances one frame while paused |
| `POST /api/session/speed` | `{"speed": 2.0}` | bounds 0.1–8.0, else 400 |
| `GET/POST /api/session/layers` | `{"trajectories": true, …}` | partial merge; unknown key → 400 |

`status.session` (the canonical live state object):
```json
{
  "source_id": "file:running_clip.mp4", "status": "running|paused|completed|stopped|error",
  "device": "mps", "frames_processed": 61, "source_fps": 30.0,
  "pipeline_fps": 26.1, "inference_fps": 45.0, "latency_ms": 22.2,
  "playback_speed": 1.0, "is_paused": false, "is_file": true,
  "active_tracks": 2, "total_tracks": 4, "people_detected": 4,
  "vehicles_detected": 0, "active_people": 2, "active_vehicles": 0,
  "events_committed": 23, "zone_person_counts": {"<zone_id>": 2},
  "error": null, "uptime_s": 15.2,
  "layers": {"boxes": true, "labels": true, "fps": true,
              "trajectories": false, "zones": true, "faces": false, "pose": false}
}
```
Status semantics: `completed` = end-of-stream (NOT an error); `error` carries `.error` text; tracks flush to SQLite at finalize (available via `/api/sessions/{id}/tracks`).

## 3. Live frame streams

- **`GET /api/stream.mjpg`** — annotated live video: YOLO boxes + track IDs + FPS overlay + (layer-gated) zone polygons, trajectories, face boxes, pose skeletons. multipart boundary `frame`. 404 when no session. Use for live operator video; boxes are already burned in.
- **`GET /api/frame.jpg`** — the single latest annotated frame (polling fallback / thumbnails). 404 when no frame yet.
- **`GET /api/stream/events`** — SSE (`text/event-stream`): one `data: {event JSON}` per committed event + `: keepalive` comments every ~5 s. Bounded per-client queue (100); slow readers get events dropped, never backpressure the engine. Client reconnect is standard EventSource semantics.

**Coordinate convention (single source of truth):** all pixel coordinates are in decoded source-frame space (BGR, origin top-left, y down, `(x1,y1,x2,y2)` boxes). Trajectories are exposed **normalized** (see §5). The MJPEG frame is the same render the engine commits as evidence — a box on screen is the same box in the DB snapshot.

## 4. Events

### `GET /api/events?session_id=&type=&severity=&limit=&before=&before_id=`
Paginated DESC. Cursor is the **pair** `(before, before_id)` — pass exactly one half → 400. Response carries `next_before`/`next_before_id` for the next page.
Event shape: `{id, session_id, source_id, ts, video_ts, type, severity, confidence, track_ids:[], zone_id, direction, is_night, snapshot_path, metadata:{}, status}`
Event types (all real, all explainable): `PERSON_DETECTED, VEHICLE_DETECTED, ZONE_ENTRY, ZONE_EXIT, LINE_CROSSING, SUSPECTED_RUNNING, SUSPECTED_ABNORMAL_MOVEMENT, LOITERING, NIGHT_MOVEMENT, CROWD_DENSITY_MEDIUM, CROWD_DENSITY_HIGH, FACE_DETECTED, ANPR_PLATE_DETECTED, ANPR_READ, OCR_UNCERTAIN, SOURCE_CONNECTED, SOURCE_LOST, SOURCE_RECONNECTED, SESSION_COMPLETED, PERSON_IDENTITY_MATCHED (reid on)`.
Severity ladder: `INFO < LOW < MEDIUM < HIGH`. Behavior events are always SUSPECTED-labeled by policy — clients must preserve the prefix.

### `POST /api/events/{id}/ack` → `{"acked": bool}` (idempotent; 404 unknown)
### `GET /api/events/{id}/summary` — deterministic 7-W forensic summary (what/who/where/when/movement/why/evidence + narrative) built only from DB rows.
### `GET /api/events/{id}/snapshot` — the evidence JPEG.
### `GET /api/evidence/{event_id}/{file}` — evidence retrieval (row-checked; 200 image/jpeg).

## 5. Tracks & trajectories

### `GET /api/sessions/{id}/tracks` (404 unknown session)
```json
{"session_id": "…", "count": 7, "tracks": [
  {"track_id": 1, "class_name": "person", "first_seen": "ISO", "last_seen": "ISO",
   "frames": 104, "max_conf": 0.732,
   "trajectory": [{"x": 0.8353, "y": 0.5375, "t": 44}, …]}]}
```
- Track rows flush at session finalize (live trajectories render from the MJPEG `trajectories` layer instead)
- `trajectory` is a deterministic ≤60-point downsample of the foot-point history (ground-contact point), **normalized to [0,1] frame space** (origin top-left), `t` = tick index; absent when a track never moved — never fabricated
- `track_id` values here are the same IDs in events, snapshots, Hermes answers, and the MJPEG overlay

### `GET /api/sessions/{id}/summary` — deterministic session audit summary.
### `GET /api/sessions?limit=50` — session history (Investigation picker).

## 6. Zones (video-frame virtual fences)

- `GET /api/zones?source_id=` — list; `POST /api/zones` create; `PUT /api/zones/{id}` update; `DELETE /api/zones/{id}`
- Geometry is **normalized** `[{"x":0.1,"y":0.2}, …]` — polygons ≥3 points, lines (tripwires) exactly 2
- `kind`: `polygon|line`; `zone_type`: `WATCH|RESTRICTED` (drives severity: RESTRICTED entry = HIGH)
- Deleting a zone keeps old events honest — clients render a raw zone_id, never a fabricated name

## 7. Sources & upload

- `POST /api/sources/webcam/scan` → cameras that ACTUALLY open (honest enumeration)
- `POST /api/sources/upload` (multipart) → probe-validated (same FileSource check a session start runs), returns `{filename, path, size_bytes, fps, frame_count, width, height}`; invalid → 4xx, file deleted. Accepted: `.mp4 .mov .m4v`, ≤500MB. Arbitrary filesystem paths with spaces/Unicode work via `/api/session/start` too.
- `GET /api/sources` — DB registry + `live:true` flag matching the active session

## 8. Re-ID (capability-gated; OFF by default)

- `GET /api/reid/persons` → all clustered identities (honest `[]` + note when disabled)
- `GET /api/reid/persons/{pid}` → sightings timeline, cameras, match scores
- Wording rule (binding): single-video re-entry = "match"; cross-camera = "POSSIBLE MATCH (score)"; never "same person"

## 9. Geography / map

- `GET /api/map/config` → `{google_maps_key, has_key, has_tiles, fallback, simulated, label}` — key handed over the local socket, read from `.env` at request time; **never log or commit it**
- `GET /api/map/cameras`, `PUT /api/map/cameras/{source_id}/geo {latitude, longitude, label}` — camera placement; NULL when unplaced (no fabricated coordinates)
- `GET/POST /api/map/sectors`, `DELETE /api/map/sectors/{id}` — geo sector polygons (distinct from video zones)
- `simulated:true` = demo labeling (ADR-002); the CV pipeline NEVER depends on Maps — map outage degrades the map panel only

## 10. Hermes (investigation copilot)

- `GET /api/hermes/status` → `{connected, enabled, model, gateway, available_models_count, error}` (cached 60s; auth from `.env`, never logged)
- `POST /api/hermes/ask` `{"question": str, "event_id"?, "session_id"?, "model"?}` → `{answer, model, elapsed_ms, grounded_event_id, grounded_session_id, context}` — **field is `question`, not `query`**
- Grounding: `answer` is computed from the machine-verified context (event row, tracks, trajectory, zone, source, evidence, deterministic summaries) with `[OBSERVED]/[DERIVED]/[INFERRED]` tags. Unanswerable → explicit "data missing" refusal (correct behavior). Non-200 → 503 with `{reason, message, retry_after_s?}` taxonomy (busy / model_cooldown / gateway_* / timeout).
- `GET /api/hermes/context?event_id=&session_id=` — inspect the exact context JSON (debugging surface)
- Credential rule: the OmniRoute gateway key lives in `.env` (`HERMES_API_KEY`), is sent only as a Bearer header, and must never appear in logs, events, UI, or Hermes context

## 11. Error contract (uniform)

- 400 invalid input (actionable message; half-cursor, unknown layer, bad speed, missing path)
- 404 not found / no active session
- 409 duplicate session start
- 413/415/422 upload rejects (size / extension / undecodable)
- 503 capability gate (detector model missing; Hermes gateway down) — server stays up

## 12. Versioning

- Contract version: **v1** (this document, 2026-09-10). Additive changes only within v1; any breaking change bumps to v2 with a migration note here.
- The OpenAPI schema at `/openapi.json` is generated from the same code — treat divergence between this doc and the schema as a bug to file against the backend.
