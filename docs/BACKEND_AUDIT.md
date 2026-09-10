# TRINETRA Backend Audit — 2026-09-10

Auditor: backend/intelligence agent. Everything below was **verified by execution on this machine** (suite runs, live uvicorn boot, real video sessions, SSE/MJPEG capture, DB queries, gateway probes). No claims are taken from prior milestone reports.

## A. What actually works (runtime-verified)

| Capability | Evidence |
|---|---|
| Full test suite | **350 passed / 0 failed / 0 skipped** in 98.7s (`./venv/bin/python -m pytest -q`) |
| Backend boot + health | uvicorn on :8000; `GET /api/health` → `ok:true`, db `user_version 3`, writer ok |
| Models present | yolov8n.pt (6.5MB), fast-reid ONNX (8.9MB), yunet.onnx (0.2MB), yolov8n-pose.pt (6.8MB); ANPR plate model absent → honest `heuristic_fallback` mode |
| File session (real video) | `POST /api/session/start` on `uploads/f25950_Normal_Videos.mp4` → 308 frames @ 28 FPS pipeline / 45 FPS inference on MPS, 4 people, 23 events, zone counts live |
| Real detections + tracking | YOLO → ByteTrack → TrackStore → events → SSE → SQLite all live (PERSON_DETECTED, ZONE_ENTRY/EXIT with real track ids) |
| MJPEG stream | 114 real frames captured from `/api/stream.mjpg` during an active session |
| SSE stream | `/api/stream/events` delivered SOURCE_CONNECTED, FACE_DETECTED, ZONE_* live (140 lines captured) |
| Playback controls | pause/resume verified live; speed bounds (0.1–8.0) enforced with 400s; step endpoint present |
| EOS semantics | File completion → status `completed` + `SESSION_COMPLETED` INFO event (verified twice) |
| Trajectory round-trip | Track rows flushed with ≤60-point normalized `{x,y,t}` trajectories; `GET /api/sessions/{id}/tracks` returns them (V3.5 drill check passes) |
| Evidence chain | 128/200 events carry real snapshot JPEGs; `GET /api/evidence/{id}/{file}` returns 200 + valid JPEG bytes |
| Event summaries | `GET /api/events/{id}/summary` → deterministic 7-W structured breakdown from DB rows only |
| Session summaries | `GET /api/sessions/{id}/summary` works, numbers traceable |
| Hermes grounding | `POST /api/hermes/ask` with event_id returns `[OBSERVED]/[DERIVED]`-tagged answers computed from real event/track/trajectory rows (dwell_seconds 48.5, trajectory positions). Nonexistent event → honest "no answerable data" refusal |
| Hermes config | `ask` works via OmniRoute gateway (model ~z-ai/glm-flash-latest, ~4.5–7s latency) |
| Map API | `GET /api/map/config` returns real key from `.env` (simulated-honest labeling), cameras/sectors CRUD works |
| Geographic state | `PUT /api/map/cameras/{id}/geo`, sectors CRUD; camera lat/lng NULL when unplaced (no fabrication) |
| Adversarial input handling | missing file → 400; `not_a_video.mp4` → 422-ish clean 400; bogus type → 400; duplicate session → 409; double-stop idempotent; unicode+space path (`வீடியோ dir/vidéo clip.mp4`) → session runs; speed out-of-range → 400 |
| V3.5 E2E drill | `scripts/v35_e2e_drill.py` — **25/25 PASS** (session, layers, MJPEG, SSE, ack, summaries, reid gallery, tracks+trajectories, RTSP rejection, health) |
| L3 runtime probe | 26.5 FPS avg pipeline, layer-toggle round-trips 1–3ms, 60 waypoints served, ANPR 0 false positives on normal footage |
| Desktop (Qt/QML) app | boots clean under offscreen QT platform (full event loop runs); 9 bridge tests pass; SSE listener + frame provider + Hermes worker wired |

## B. What fails / is broken (found in this audit)

1. **Hermes `/status` reports `connected:false — gateway returned HTTP 401`** while `/ask` succeeds. Root cause: the OmniRoute gateway requires an API key (`sk-…` in `~/.omniroute/storage.sqlite`); `HERMES_API_KEY` is unset in Trinetra's `.env`/config, so `check_status()` probes `/v1/models` unauthenticated → 401. BUT `/chat/completions` evidently tolerates missing auth on this gateway build (ask works). The status endpoint is therefore **misleading**: UI shows Hermes as down while it actually answers. Fix: load `HERMES_API_KEY` (from `.env` — key already exists in the omniroute store) and send `Authorization: Bearer` on both paths.
2. **KinematicTrajectoryAnalytic assumes fps=25** (`KinematicTrajectoryAnalytic()` default) while demo sources are 30fps. Effects at 30fps real: `dt_sec = ticks/25` over-estimates elapsed time by 1.2× → speeds under-estimated by 17%, loiter dwell over-estimated by 20% (LOITERING fires ~4s early on a 20s threshold). Real bug affecting SUSPECTED_RUNNING/LOITERING calibration. Fix: pass the source FPS (or measured pipeline FPS) into the analytic.
3. **ANPR never receives pixels on the session path.** `ANPRAnalytic.process(ctx, view)` is invoked via the analytics chain without the frame, so the model branch (`if self._model is not None and frame is not None`) can never run even if `yolov8n_plate.pt` existed; OCR likewise (`self._ocr_engine` unset anywhere in the app). Current behavior is honest (heuristic localization + `ANPR_PLATE_DETECTED`, no fabricated text) but the model path is dead wiring. Fix (root cause): give the analytic the frame (shape-B service call like reid/face), keep model-absent → honest PLATE_DETECTED.
4. **Re-ID is disabled at runtime** (`[reid] enabled=false` in config + `reid_enabled:false` in health). All reid code, ONNX, 23+ tests are present and passing; the capability simply isn't on. Not a defect per se (safe default), but for the demo either enable it or surface "disabled by config" prominently. The QML bridge `reidEnabled` property correctly reflects config+model.
5. **`updateEventStatus` in the desktop bridge** writes `dao.conn.execute` directly on the Qt thread — bypasses the DAO thread-affinity discipline (each thread owns its sqlite conn). Low-severity (SQLite in WAL tolerates cross-thread), but inconsistent with the connection-per-thread design.

## C. What is incomplete

- **ANPR end-to-end**: no plate model (`yolov8n_plate.pt`), no OCR engine → only heuristic localization + three-state classification unit/integration-tested. Honest fallback works; a real read never happens (see B3).
- **Re-ID cross-camera**: single-session MVP registers one camera at a time; cross-camera matching is tested synthetically (23 ported tests) but never demonstrated on 2 real camera streams in one app run.
- **Pose (yolov8n-pose)**: detector wired into session (`poses` layer), model present, unit-tested; but pose runs only when `pose` layer toggled ON and is detection-level only (no fall/behavior analytics consume keypoints yet).
- **RTSP**: source implemented + unit-tested + registered in factory; loopback rig script exists (`scripts/rtsp_test.py`) but real-camera auth untested (documented honest caveat).
- **Night analytics**: NIGHT_MOVEMENT fires only on `is_night` (luma<40) footage; no dark-scene clip exercised in drills yet.
- **SSE latency estimate** in L3 probe (~1.9s) is a coarse cross-observer measurement, not an instrumented metric.

## D. What is only unit-tested (not runtime-verified here)

- Webcam ladder (SOURCE_LOST → backoff → RECONNECTED) — unit/integration tested; no physical webcam exercise in this audit.
- RTSP reconnect ladder — monkeypatched VideoCapture only.
- Disk-low snapshot gate, poison-event writer path — simulated in tests.
- `m7_e2e.py` 24-check drill — not re-run this session (superseded by v35 drill 25/25).

## E. Runtime-verified summary

Boot, health, file session, detection, tracking, events, zones, trajectories, evidence, summaries, Hermes answers (grounded), map API, SSE, MJPEG, pause/resume/speed, EOS, restart-persistence (sessions/tracks/events survive across uvicorn restarts — DB rows verified), adversarial inputs (§A table).

## F. Broken contracts

- `GET /api/hermes/status` shape is fine but the *truth* it reports is wrong today (B1) — fix in flight.
- `POST /api/hermes/ask` uses `question` field; the first probe used `query` → FastAPI 422. Contract is `question` (documented in INTEGRATION_CONTRACT).
- No `contracts/` directory exists yet — schemas live implicitly in code/tests. Created in this pass (see INTEGRATION_CONTRACT.md).

## G. Performance problems

- None blocking. Measured: 28 FPS pipeline @ 45 FPS inference (MPS) on 30fps source with all analytics ON, faces ON, 22ms avg latency; probe avg 26.5 FPS; MJPEG ~14KB/frame q70. Kinematics B2 bug slightly distorts speed metrics (fix improves).
- Hermes round-trip 4.5–7.2s (network LLM) — acceptable for a copilot, noted in docs.

## H. Synchronization problems

- None observed: track/event/trajectory IDs are consistent across engine→DB→SSE→API→Hermes (LOITERING track #10 identical everywhere; verified in queries above).
- One-session-at-a-time rule enforced (409).

## I. Highest-priority fixes (this pass)

1. Hermes status truthfulness (API key wiring) — **FIXED + verified**: status `connected:true` (was false-401); key loaded from `.env` via the new §19 loader in `config.py`, sent as Bearer on both `/models` and `/chat/completions`. Regression: `tests/test_audit_fixes.py::TestHermesApiKeyWiring` (4 tests).
2. Kinematics FPS calibration — **FIXED + verified**: `set_fps()` added; session feeds container FPS after `open()` (files) and the measured rate for metadata-less live sources. Behavioral proof: SUSPECTED_RUNNING now fires on real running.mp4 (3 events, speeds 93–231 px/s) — was 0 in the pre-fix probe.
3. ANPR frame wiring — **FIXED**: `ANPRAnalytic.set_frame()` shape-B seam; the session passes pixels each tick so the model/OCR branches are live wiring (model absent → honest PLATE_DETECTED, verified 0 false positives). Pre-fix the session path could never deliver a frame.
4. Desktop-bridge `updateEventStatus` (B5) — **cleared by design**: `DAO.conn` is a property returning the CALLING thread's connection (`threading.local`), so Qt-thread writes already follow the per-thread discipline.
5. Integration contract + docs — **DONE**: `docs/INTEGRATION_CONTRACT.md` (v1, for the SwiftUI agent), `docs/BACKEND_ARCHITECTURE.md`, `docs/RUNTIME_RUNBOOK.md`, `docs/DEMO_RUNBOOK.md` (rewritten with verified values), `docs/FINAL_BACKEND_ACCEPTANCE.md`.

Post-fix gates: **363 passed / 0 failed** (350 + 13 new regression tests), v35 E2E drill 25/25, L3 probe clean, full-system rehearsal 22/22 scenarios (incl. the stop-race regression found by the rehearsal itself).

## J. Rehearsal-discovered fix (post-I)

6. **Stop-vs-finalize DB race** — the rehearsal exposed that a mid-stream `stop()` left the DB row `running` forever (worker thread's finally-finalize wrote the stale status before `stop()` assigned `stopped`; the idempotent guard then blocked the correct write). **FIXED**: `stop()` now assigns the terminal status BEFORE `join()`; regression `TestStopFinalizeRace`; live-verified (DB row `stopped` after mid-stream stop).
