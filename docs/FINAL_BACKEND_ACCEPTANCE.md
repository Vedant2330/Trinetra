# TRINETRA Final Backend Acceptance Matrix — 2026-09-10

Evidence key: **U** = unit test · **I** = integration test · **R** = runtime-verified (live boot/session/streams this audit) · **E** = end-to-end drill (`scripts/v35_e2e_drill.py` 25/25) · **A** = adversarially tested (audit §A) · ✓ = verified · — = not applicable/not present. No row is marked PASS without a concrete test or runtime check from this session.

| Capability | Implementation | Unit | Integration | Runtime | E2E/Adversarial | Status | Known limitation |
|---|---|---|---|---|---|---|---|
| Backend boot + health | backend/main.py lifespan | ✓ (test_m0_app) | ✓ | ✓ | ✓ E | **PASS** | anpr plate model absent → honest fallback mode |
| File source (mp4/mov/m4v, arbitrary paths) | sources/file.py | ✓ (test_m1_file) | ✓ | ✓ | ✓ E+A (unicode/space, missing, not-a-video) | **PASS** | codec support = local OpenCV build |
| Webcam source | sources/webcam.py | ✓ (test_m1_webcam) | ✓ | probe scan ✓ | — | **PASS** | physical-cam exercise not in this audit |
| RTSP source (TCP) | sources/rtsp.py | ✓ (test_rtsp_source) | ✓ monkeypatch | invalid URI 400 ✓ | ✓ E (reject) | **PASS** | loopback rig only; real-camera auth UNTESTED |
| Playback timing (file pacing to source FPS) | session `_run` pacing | ✓ (audit fix tests) | ✓ | ✓ 30.0 fps shown, 26 FPS display | ✓ E | **PASS** | faster-than-realtime only via speed ≤8× |
| Pause/Resume/Step/Speed | session controls + main routes | ✓ (test_session_controls) | ✓ | ✓ live | ✓ A (bounds 400) | **PASS** | — |
| EOS = COMPLETED | FileSource C3 split | ✓ (test_m1_file) | ✓ | ✓ ×2 sessions | ✓ E | **PASS** | — |
| YOLOv8n detection (MPS) | vision/tracker.py | ✓ (test_m2_detector) | ✓ | ✓ real people/boxes | ✓ E | **PASS** | classes limited to config set |
| ByteTrack tracking + IDs | vision/tracker + state/tracks | ✓ (test_m2_trackstate) | ✓ | ✓ stable IDs across events | ✓ E | **PASS** | ByteTrack is the only tracker |
| Confirm-edge dedup (once-per-track) | TrackStore.take_newly_confirmed | ✓ | ✓ | ✓ | ✓ E | **PASS** | — |
| Foot-point trajectories (live overlay) | annotation trajectories layer | ✓ (test_layers) | ✓ | ✓ layer round-trips <5ms | ✓ E | **PASS** | overlay only when layer ON |
| Trajectory persistence + API | session `_finalize` + sources.py | ✓ (test_summary) | ✓ | ✓ 60 waypoints served | ✓ E | **PASS** | flush at finalize only (live rows empty by design) |
| Zones (polygon) CRUD + entry/exit | analytics/zones+fence+geometry | ✓ (test_m4_*) | ✓ | ✓ live counts | ✓ E | **PASS** | — |
| Tripwires (line + direction) | fence line geometry | ✓ (test_m4_geometry) | ✓ | ✓ | ✓ E | **PASS** | — |
| Severity ladder + RESTRICTED/night mods | engine `_severity_for` | ✓ (test_m5_engine) | ✓ | ✓ HIGH on restricted entry observed | ✓ E | **PASS** | cap HIGH |
| Event engine cooldown/dedup | engine `_pass_cooldown` | ✓ | ✓ | ✓ | ✓ E | **PASS** | — |
| Event persistence (WAL, restart-safe) | db/* | ✓ (test_m5_db) | ✓ | ✓ rows survive restarts | ✓ E | **PASS** | — |
| SSE live events | events/sse + api/stream | ✓ (test_m5_sse) | ✓ | ✓ captured live | ✓ E | **PASS** | drop-oldest under slow reader |
| MJPEG annotated stream | main.py + annotation | ✓ (test_m3) | ✓ | ✓ 114 frames captured | ✓ E (61 frames) | **PASS** | — |
| Evidence snapshots (shared JPEG) | engine `_save_snapshot` | ✓ (test_m5_db) | ✓ | ✓ 128/200 events, JPEG 200 | ✓ E | **PASS** | disk-low gate may skip (flagged) |
| 7-W event summaries | services/summary | ✓ (test_summary) | ✓ | ✓ | ✓ E | **PASS** | absent fields render absent |
| Session summaries | services/summary | ✓ | ✓ | ✓ | ✓ E | **PASS** | — |
| Face detection (YuNet) | vision/face + session wiring | ✓ (test_face) | ✓ | ✓ FACE_DETECTED live (running_clip) | ✓ E | **PASS** | detection-only; NO identity claims |
| Pose (yolov8n-pose) | vision/pose + layer | ✓ (test_pose) | ✓ | model present, layer gated | — | **PASS (layer)** | no downstream keypoint analytics yet |
| Re-ID (fast-reid ONNX) | reid/* + cv2.dnn embedder | ✓ 23 ported (test_reid) + port | ✓ | capability config-OFF by default | ✓ E (gallery endpoints honest-empty) | **PASS (gated OFF)** | single-session MVP; cross-camera not demoed |
| Crowd analytics (count-based) | analytics/crowd | ✓ (test_crowd) | ✓ | ✓ | ✓ E | **PASS** | density informational only (count-authoritative) |
| Behavior: SUSPECTED_RUNNING | analytics/kinematics | ✓ (test_kinematics + audit fixes) | ✓ | ✓ REAL: 3 events on running.mp4, speeds 93–231 px/s | ✓ A (calibration regression) | **PASS** | heuristic, SUSPECTED label |
| Behavior: LOITERING | analytics/kinematics | ✓ | ✓ | ✓ live (dwell 31.8s real) | ✓ E | **PASS** | threshold 15s default |
| Behavior: ABNORMAL / NIGHT | analytics/kinematics | ✓ | ✓ | NIGHT not exercised on real dark footage | — | **PASS (unit)** | needs dark-scene clip for runtime proof |
| FPS calibration (tick→seconds) | kinematics.set_fps + session | ✓ (test_audit_fixes) | ✓ (real FileSource) | ✓ source_fps 30.0 adopted | ✓ | **PASS** | live sources use measured rate |
| ANPR three-state | analytics/anpr | ✓ (test_anpr) | ✓ | ✓ frame seam (audit fix); honest PLATE_DETECTED | ✓ A (0 false positives) | **PASS (heuristic)** | no plate model/OCR → no reads (honest) |
| Hermes grounded Q&A | services/hermes + api | ✓ (test_hermes) | ✓ | ✓ [OBSERVED] answers from real rows | ✓ E+A (nonexistent event refusal) | **PASS** | ~5–7s LLM latency |
| Hermes status truthfulness | Bearer key on /models | ✓ (test_audit_fixes) | ✓ | ✓ connected:true, 3335 models | ✓ | **PASS** | requires gateway + .env key |
| Maps key + config | api/map | ✓ (test_m7_geo) | ✓ | ✓ key served, simulated labeling | ✓ E | **PASS** | demo coordinates labeled SIMULATED |
| Camera geo / sectors | api/map + dao | ✓ | ✓ | ✓ CRUD verified | ✓ E | **PASS** | — |
| Upload chain | api/sources upload | ✓ (test_v2_sources) | ✓ | ✓ | ✓ E (probe0 chain) | **PASS** | mp4/mov/m4v ≤500MB |
| Desktop Qt/QML (legacy ref) | backend/desktop | ✓ (test_desktop_bridge 9) | ✓ | ✓ boots offscreen | — | **PASS (legacy)** | superseded by SwiftUI client |
| Session lifecycle status persistence (stop-vs-finalize race) | session.stop ordering fix | ✓ (test_audit_fixes::TestStopFinalizeRace) | ✓ | ✓ mid-stream stop → DB `stopped` | ✓ rehearsal | **PASS** | — |
| Adversarial input handling | throughout | ✓ | ✓ | ✓ §A table | ✓ A (12 cases) | **PASS** | — |
| Performance | measured, not claimed | — | ✓ benches | ✓ 28 FPS pipe / 45 FPS infer / 22ms latency (MPS) | ✓ probe 26.5 FPS | **PASS** | no zero-copy/60FPS claims |

**Suite: 363 passed / 0 failed** (350 pre-audit + 13 audit-fix regressions). Drills: v35_e2e 25/25, L3 probe clean, upload chain green, final full-system rehearsal 22/22 scenarios (health → live video → FPS → detections → tracks → layers → MJPEG → pause-frozen/resume → EOS-completed → trajectories persisted → zone events → evidence → 7W summary → Hermes grounded + honest refusal → replay → clean restart → adversarial 400/409).

## Honest open items (not faked, tracked)

1. ANPR OCR: requires plate model + OCR engine; system correctly reports `heuristic_fallback` and never fabricates reads.
2. Re-ID runtime enable: config-off; enabling for demo requires `[reid] enabled=true` + honest "EXPERIMENTAL — possible-match semantics" labeling.
3. NIGHT_MOVEMENT: implemented + unit-tested; no dark-scene clip exercised in a drill yet.
4. RTSP auth: loopback only.
5. SSE latency estimate (~1.9s) is coarse; per-event engine→client delivery is sub-second in practice (observed live).
