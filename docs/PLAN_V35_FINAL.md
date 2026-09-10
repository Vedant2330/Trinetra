# TRINETRA V3.5 — FINAL EXECUTION TASK GRAPH & IMPLEMENTATION PLAN

**Stage:** 2 of 5 (PLANNER) · **Author:** planner-mtumzx5p  
**Chain of Custody:** RESEARCHER (`mtumwxna`) → **PLANNER (`mtumzx5p`, this artifact)** → ARCHITECT (`mtum77rw`) → EXECUTOR (`executer-mtum4rce`, sole implementer) → VERIFIER (`oscar-mtt8m47c` + `god`)  
**Base Tree:** `3d0c7e2` (M7 committed baseline) + V3 full light-theme sprint + M8 Re-ID initial port (uncommitted, verified tree-truth)  
**Deliverable Target:** `Trinetra/docs/PLAN_V35_FINAL.md`  
**Date:** 2026-09-10  

---

## 1. Executive Summary & Tree-Truth Reconciliation

This document establishes the definitive, dependency-aware task graph for TRINETRA V3.5. It reconciles the base implementation plan (`TRINETRA_FULL_IMPLEMENTATION_PLAN.md`) with the empirical findings of the Stage-1 Research audit (`docs/RESEARCH_V35.md`), the Architect Handoff contract (`TRINETRA_FULL_ARCHITECTURE_HANDOFF.md`), and the workspace resource inventory (`TRINETRA_RESOURCE_INVENTORY.md`).

### 1.1 Key Empirical Corrections Integrated
1. **F1 Re-ID Dynamic Batching (Phase 2):** OpenCV DNN (`cv2.dnn.readNetFromONNX`) natively handles dynamic batch sizes on `fast-reid_mobilenetv2.onnx`. Single-crop inference runs at **5.5ms** (12.7x speedup vs 69.8ms zero-padded batch-32) yielding byte-identical embeddings. Dynamic batch forwarding is promoted to primary with batch-32 padding retained strictly as fallback.
2. **F2 YuNet Face Detector Dimension Sync & Temp Eviction (Phase 3):** `yunet.onnx` (232,589 bytes, 2.2ms @ 320x320) currently resides in a volatile macOS `/var/folders/` temp directory. Phase 3 must copy it immediately to `Trinetra/models/yunet.onnx`. Furthermore, `cv2.FaceDetectorYN` requires dynamic `setInputSize(frame.shape[:2])` synchronization or explicit coordinate-scaled 320x320 evaluation to prevent runtime dimension assertion failures.
3. **Clean-Room AGPL Trajectory Analytics (Phase 4):** Kinematic heuristics (`SUSPECTED_RUNNING`, `SUSPECTED_ABNORMAL_MOVEMENT`, `LOITERING`, `NIGHT_MOVEMENT`) are implemented strictly from mathematical first principles using the existing `TrackState.positions` (maxlen 60 deque of foot-points). No imports, files, or code structures from the AGPL-3.0 crowd repository are permitted.
4. **Count-Based Crowd Density (§2.7, Phase 4):** Crowd density alerts are governed by authoritative person counts (`FenceAnalytic.zone_person_counts()`: medium=4, high=8, sustained=2 consecutive ticks). Coordinate-normalized polygon density is retained strictly as informational metadata to eliminate false alarms on small zones.
5. **Additive Event Engine Severity Ladder (§2.6, Phase 4/6):** Additive mapping `_NEW_TYPE_BASE` in `backend/analytics/engine.py` assigns explicit baseline severities (`MEDIUM`/`LOW`) and modifiers (night condition, restricted zones) without falling back to default `INFO`.
6. **Non-Blocking Database Migration Isolation (Phase 5):** Migration 3 (`ALTER TABLE tracks ADD COLUMN trajectory TEXT`) and `DAO.upsert_track_trajectories` are isolated to a God-managed schema update at Phase 5 start. Application code degrades gracefully beforehand via `hasattr` and sqlite pragma checks.
7. **ANPR Offline Network-Gate & Honest Fallback (Phase 6):** LPD/OCR dependencies and datasets are completely absent offline. Phase 6 enforces a graceful fallback to a color/geometry heuristic (`PLATE_DETECTED`) with `OCR_UNCERTAIN` state and honest UI labels ("ANPR — plate detection only (no read)").
8. **RTSP Venv Re-Measurement & Source Registration (Phase 7):** Historical 19.7 FPS / 1.6s TTFF figures were measured on system OpenCV 4.13; Phase 7 mandates re-measurement under venv OpenCV 5.0.0. `session.py:183` source type resolution is fixed via `getattr(self._source, "type_name", "file")`.
9. **Re-ID Hygiene & Benchmarks (Phase 2):** Correct 'HONST' docstring typo in `backend/reid/embedder.py` and port `scripts/m8_reid_bench.py` to benchmark `OpenCVDnnEmbedder`.
10. **Phase 0 Status:** The upload-to-browser chain was empirically proven operational by `scripts/phase0_upload_chain.py` (22/22 assertions green, 22.8 FPS, 8 live detections). Phase 0 requires no code changes.

---

## 2. Phase-by-Phase Task Graph

```
[Phase 1: V3 Remainder & Layer Toggles]
   ├── T1.1: Backend Per-Class Counts & Atomic Status Snapshot
   ├── T1.2: Server-Side Layer Annotation & Inline Endpoints
   └── T1.3: Live View Toggles & EventSummary Reconciliation
          │
          ▼
[Phase 2: M8 Re-ID Port & Dynamic Batching]
   ├── T2.1: Re-ID Module Verification, Docstring Fix & Bench Script Port
   ├── T2.2: OpenCVDnnEmbedder Dynamic Batch Inference Optimization (F1)
   └── T2.3: MultiCameraReIdService Wiring & UI Identity Chips
          │
          ▼
[Phase 3: YuNet Face Detection]
   ├── T3.1: Model Eviction from Temp to Trinetra/models/yunet.onnx
   ├── T3.2: YuNetFaceDetector Implementation & setInputSize Sync
   └── T3.3: Event-Triggered Face Gating, Annotation & UI Toggle
          │
          ▼
[Phase 4: Crowd & Behavior Analytics (AGPL-Safe)]
   ├── T4.1: CrowdAnalytic Count-Based Density & Occupancy
   ├── T4.2: BehaviorAnalytic Kinematic Heuristics (Running, Abnormal, Loitering, Night)
   └── T4.3: Additive Event Engine Severity Mapping (_NEW_TYPE_BASE)
          │
          ▼
[Phase 5: Deterministic Summary & Investigation Enrichment]
   ├── T5.1: [GOD HUNK] Schema Migration 3 & DAO Trajectory Persistence
   ├── T5.2: Backend Session Summary Service (GET /api/sessions/{id}/summary)
   └── T5.3: Investigation Page Trajectory Mini-Canvas & Related Events
          │
          ▼
[Phase 6: ANPR Heuristic & Graceful Network-Gate Fallback]
   ├── T6.1: Indian License Plate Regex & 3-State Validation Engine
   ├── T6.2: Vehicle-Triggered Plate Detection & Network-Gated Fallback
   └── T6.3: UI ANPR State Labels & Evidence Verification
          │
          ▼
[Phase 7: RTSP Ingestion & Camera Management Polish]
   ├── T7.1: RtspSource Class & VideoCapture FFMPEG Transport
   ├── T7.2: Source Type Registration & session.py:183 Resolution
   └── T7.3: RTSP Venv Benchmark & Camera/Map UI Polish
          │
          ▼
[Phase 8: Full E2E Demo Drill & Final Verification Report]
   ├── T8.1: Unified E2E Test Runner Extension (scripts/trinetra_e2e.py)
   └── T8.2: Final Integration Report & Honesty Ledger (docs/TRINETRA_FINAL_INTEGRATION_REPORT.md)
```

---

## Phase 1: V3 P1 Remainder & Live View Layer Toggles

### Task 1.1: Backend Per-Class Counts & Atomic Status Snapshot
- **Objective:** Provide thread-safe, cumulative and active per-class track counts (`people_detected`, `vehicles_detected`, `active_people`, `active_vehicles`) in `status_payload` and `_stats_payload`.
- **Files Involved:**
  - Modified: `backend/services/session.py` (lines ~402-428)
  - Tests: `tests/test_layers.py` (new)
- **Dependencies:** None (starts from working baseline).
- **Expected Behavior:** Snapshot `dict(self._store.tracks)` atomically under Python GIL. Compute cumulative unique tracks by class (`person` vs `_VEHICLE_CLASSES`) and active counts matching `count_active()`. Keys must be 0 when empty, never omitted.
- **Tests:** `tests/test_layers.py::test_status_payload_counts`, `tests/test_layers.py::test_status_zero_when_empty`.
- **Acceptance Criteria:** `GET /api/session/status` returns correct non-zero counts on active sessions and `0` when empty; zero thread mutation races.
- **Complexity:** Small | **Risk:** Low.

### Task 1.2: Server-Side Layer Annotation & Inline Endpoints (C2, C3, C4, C7)
- **Objective:** Add runtime toggleable rendering layers (`boxes`, `labels`, `fps`, `trajectories`, `zones`) executed strictly server-side in `_annotate`, with thread-safe atomic swap and inline REST endpoints.
- **Files Involved:**
  - Modified: `backend/services/session.py`
  - Modified: `backend/main.py` (inline routes after `:168`, no new router files, no touching include block `:50-56` or `_DIST` mount)
  - Read-Only: `backend/vision/annotation.py` (contains uncommitted hardening diff; preserve intact)
  - Tests: `tests/test_layers.py`
- **Dependencies:** Task 1.1.
- **Expected Behavior:**
  - `Session.__init__` initializes `self._layers = {"boxes": True, "labels": True, "fps": True, "trajectories": False, "zones": True}` and `self._layers_lock = threading.Lock()`.
  - `update_layers(partial: dict) -> dict` validates keys, raises `ValueError` on unknown keys, and atomically replaces `self._layers` via `{**self._layers, **valid}` under lock (C3 immutable swap).
  - `_annotate` reads `self._layers` once per frame tick and passes trajectory points and normalized zone dicts (via `self._zones.zones(self.source_id, active_only=True)`) to `annotation.py:annotate`.
  - Add `POST /api/session/layers` and `GET /api/session/layers` inline in `main.py`. Returns `404` when no session is active, `400` on invalid keys.
- **Tests:** `tests/test_layers.py::test_layers_endpoint_crud`, `tests/test_layers.py::test_annotate_with_layers`, `tests/test_layers.py::test_layer_defaults_byte_identical`.
- **Acceptance Criteria:** POSTing `{ "boxes": false }` removes bounding boxes from MJPEG stream within 1s; zones and trajectories burn into shared-JPEG evidence when toggled ON; full test suite passes.
- **Complexity:** Medium | **Risk:** Low.

### Task 1.3: Live View Toggles & EventSummary Reconciliation
- **Objective:** Connect frontend layer toggles to backend endpoints, eliminate duplicate client-side zone rendering in `LiveFeed.tsx` (C2), and verify `EventSummary.tsx` displays zero fabricated facts.
- **Files Involved:**
  - Modified: `frontend/src/components/LiveFeed.tsx` (remove lines 21-73 zone canvas draw)
  - Modified: `frontend/src/pages/Cameras.tsx`, `frontend/src/pages/Analytics.tsx`, `frontend/src/pages/Dashboard.tsx`
  - Modified: `frontend/src/components/EventSummary.tsx`, `frontend/src/api.ts`, `frontend/src/types.ts`
- **Dependencies:** Task 1.2.
- **Expected Behavior:** Toggle bar (Detections, Track IDs, Trajectories, Virtual Fence, FPS) dispatches real API calls to `POST /api/session/layers`. Virtual Fence toggle controls server-side zone burning. `EventSummary` formats deterministic sentences solely from `EventRow` fields.
- **Tests:** `npx tsc --noEmit` clean, `npm run build` clean, Playwright UI check in `scripts/trinetra_e2e.py`.
- **Acceptance Criteria:** Toggles update server stream visually; network tab confirms 200 OK responses; zero duplicate zone boundaries; `tsc` and `vite build` report 0 errors.
- **Complexity:** Medium | **Risk:** Low.

---

## Phase 2: M8 Re-ID Port & Dynamic Batch Optimization

### Task 2.1: Re-ID Module Verification, Docstring Fix & Bench Script Port
- **Objective:** Verify the 10 landed `backend/reid/` modules, correct minor docstring typo, and port the Re-ID benchmarking script.
- **Files Involved:**
  - Modified: `backend/reid/embedder.py` (fix 'HONST' docstring typo at line 83)
  - Created: `scripts/m8_reid_bench.py` (ported from `Trinetra-m8/scripts/m8_reid_bench.py`)
  - Read-Only: `backend/reid/` (all modules: gallery, matcher, sampling, history, identity, etc.)
  - Tests: `tests/test_m8_reid.py` (23 tests), `tests/test_reid_port.py` (11 tests)
- **Dependencies:** Phase 1 complete.
- **Expected Behavior:** All 34 Re-ID tests execute green in the venv without external dependencies.
- **Tests:** `pytest tests/test_m8_reid.py tests/test_reid_port.py`.
- **Acceptance Criteria:** 34/34 Re-ID tests pass; docstring typo fixed; `scripts/m8_reid_bench.py` runs and outputs FPS/latency metrics.
- **Complexity:** Small | **Risk:** Low.

### Task 2.2: OpenCVDnnEmbedder Dynamic Batch Inference Optimization (F1)
- **Objective:** Optimize `OpenCVDnnEmbedder.embed()` in `backend/reid/embedder.py` to utilize `cv2.dnn` native dynamic batch forwarding, reducing single-crop latency from 69.8ms to 5.5ms while retaining batch-32 padding as a fallback.
- **Files Involved:**
  - Modified: `backend/reid/embedder.py`
  - Modified: `backend/reid/integration.py`
  - Read-Only: `Trinetra/models/fast-reid_mobilenetv2.onnx` (md5: `77a97e84aac88bdb3eeaa17dd6c57180`)
  - Tests: `tests/test_reid_port.py`
- **Dependencies:** Task 2.1.
- **Expected Behavior:**
  - `embed(crops)` prepares dynamic tensor `[N, 3, 256, 128]` from preprocessed crops.
  - Passes tensor directly to `self._net.setInput(blob)` and executes `self._net.forward()`.
  - If OpenCV raises a shape exception on non-32 batch sizes, gracefully fall back to zero-padding to 32 crops (`[32, 3, 256, 128]`) and slice the first `N` rows.
  - Apply L2 normalization to output embeddings.
- **Tests:** `tests/test_reid_port.py::test_dynamic_batch_embedding_equivalence`, `tests/test_reid_port.py::test_single_crop_latency_budget`.
- **Acceptance Criteria:** Batch-1 embedding latency <= 10.0ms on M4 CPU; output vector is byte-identical (within float32 eps 1e-5) to padded batch-32 embedding; L2 norm == 1.0.
- **Complexity:** Medium | **Risk:** Low.

### Task 2.3: MultiCameraReIdService Wiring & UI Identity Chips
- **Objective:** Ensure `MultiCameraReIdService` is instantiated in app lifespan, processes frame crops via selective sampling, enriches `ZONE_ENTRY` events with `global_person_id` when similarity >= 0.80, and exposes investigation endpoints.
- **Files Involved:**
  - Modified: `backend/main.py` (lifespan Re-ID service registration, `_model_status()` reporting, routes `/api/reid/persons`)
  - Modified: `backend/services/session.py` (per-tick `process_tick` and `enrich_drafts` calls)
  - Modified: `frontend/src/components/EventDetail.tsx`, `frontend/src/pages/Investigation.tsx`
  - Tests: `tests/test_reid_port.py`
- **Dependencies:** Task 2.2.
- **Expected Behavior:**
  - Re-ID is gated on model presence via `_try_load()`. If ONNX is absent, gracefully no-op without raising errors.
  - Event metadata receives `global_person_id` and `identity_cameras` only upon CONFIRMED match (>= 0.80). CANDIDATE matches (0.55-0.79) never link identities.
  - Frontend displays identity badges and cross-camera history using "POSSIBLE MATCH (score)" wording.
- **Tests:** `tests/test_reid_port.py::test_reid_session_integration_enrichment`, `tests/test_reid_port.py::test_candidate_never_links`.
- **Acceptance Criteria:** `running_clip.mp4` processes with Re-ID enabled with < 15% FPS degradation; confirmed matches populate `global_person_id`; UI displays identity chips only when metadata is present.
- **Complexity:** Medium | **Risk:** Low.

---

## Phase 3: YuNet Face Detection Module

### Task 3.1: Model Eviction from Temp to Trinetra/models/yunet.onnx
- **Objective:** Relocate `yunet.onnx` from volatile `/var/folders/...` temp storage to permanent repository model storage `Trinetra/models/yunet.onnx`.
- **Files Involved:**
  - Created: `Trinetra/models/yunet.onnx` (copied from temp path, 232,589 bytes)
  - Created: `tests/assets/face_frame_intrusion.jpg` (1 extracted frame from intrusion.mp4 for fixture tests)
- **Dependencies:** Phase 2 complete.
- **Expected Behavior:** File exists at `Trinetra/models/yunet.onnx` with size 232,589 bytes and md5 `a9914757c23101eb652077fb5b7a08ec`.
- **Tests:** `test -f Trinetra/models/yunet.onnx && test -s Trinetra/models/yunet.onnx`.
- **Acceptance Criteria:** Model file permanently situated in repository; survives OS temp sweeps.
- **Complexity:** Small | **Risk:** Low.

### Task 3.2: YuNetFaceDetector Implementation & setInputSize Sync (F2)
- **Objective:** Implement `backend/vision/face.py` using `cv2.FaceDetectorYN` with dynamic input size synchronization or coordinate-scaled 320x320 detection.
- **Files Involved:**
  - Created: `backend/vision/face.py`
  - Tests: `tests/test_face.py` (new)
- **Dependencies:** Task 3.1.
- **Expected Behavior:**
  - `YuNetFaceDetector` class initializes `cv2.FaceDetectorYN.create(str(model_path), "", (320, 320), score_threshold=0.6, nms_threshold=0.3)`.
  - Implement `detect(frame)`: dynamically invoke `self._detector.setInputSize((frame.shape[1], frame.shape[0]))` prior to `self._detector.detect(frame)` to prevent OpenCV dimension assertion failures.
  - Return structured list of dicts: `[{"bbox": [x, y, w, h], "conf": float, "landmarks": [...]}]`.
  - If model file is missing, set `self.available = False` and return `[]` without throwing exceptions.
  - Strictly detection only: NO face recognition, NO face identity database, NO face embeddings.
- **Tests:** `tests/test_face.py::test_yunet_detector_dynamic_dimensions`, `tests/test_face.py::test_yunet_missing_model_fallback`.
- **Acceptance Criteria:** Runs on arbitrary frame resolutions (320x320, 640x480, 1080p) without dimension mismatch errors; detects 5 faces in `tests/assets/face_frame_intrusion.jpg` with conf >= 0.60 in < 5ms.
- **Complexity:** Medium | **Risk:** Low.

### Task 3.3: Event-Triggered Face Gating, Annotation & UI Toggle
- **Objective:** Wire face detection into the session pipeline as an event-triggered (selective) module, annotate faces in MJPEG overlays, and expose UI toggle.
- **Files Involved:**
  - Modified: `backend/services/session.py` (trigger face detection on person tracks with bbox height >= 80px, cooldown 5s)
  - Modified: `backend/vision/annotation.py` (add optional `faces=None` kwarg around existing hardening diff)
  - Modified: `backend/main.py` (update `_model_status()` with `models.face`)
  - Modified: `frontend/src/pages/Cameras.tsx` (add Face Detection toggle, enabled only when model is present)
  - Tests: `tests/test_face.py`
- **Dependencies:** Task 3.2.
- **Expected Behavior:**
  - Face detection runs ONLY when triggered by a person track (never every frame on raw stream).
  - Emits `FACE_DETECTED` event (Severity: `LOW`, metadata: `{track_id, conf, landmarks_count, bbox}`).
  - `annotation.py` renders thin cyan bounding box with `FACE 0.xx` label when `layers["faces"]` is active.
- **Tests:** `tests/test_face.py::test_face_event_trigger_gating`, `tests/test_face.py::test_annotation_with_faces`.
- **Acceptance Criteria:** `FACE_DETECTED` events appear in event stream; cyan boxes visible in MJPEG stream when toggled ON; overall session FPS impact < 3%.
- **Complexity:** Medium | **Risk:** Low.

---

## Phase 4: Crowd & Behavior Analytics (AGPL-Safe Reimplementations)

### Task 4.1: CrowdAnalytic Count-Based Density & Occupancy (§2.7)
- **Objective:** Implement `backend/analytics/crowd.py` as an `AnalyticModule` emitting `CROWD_DENSITY` events based on authoritative person counts from `FenceAnalytic.zone_person_counts()`.
- **Files Involved:**
  - Created: `backend/analytics/crowd.py`
  - Modified: `backend/analytics/__init__.py`
  - Tests: `tests/test_crowd.py` (new)
- **Dependencies:** Phase 3 complete.
- **Expected Behavior:**
  - Evaluates active zones per tick using authoritative ByteTrack tracker person counts inside zone polygons.
  - Emits `CROWD_DENSITY` event when person count >= `crowd_count_medium` (default 4, Severity `MEDIUM`) or >= `crowd_count_high` (default 8, Severity `HIGH`) sustained for >= 2 consecutive ticks.
  - Normalized coordinate polygon density (`count / shoelace_area`) is recorded strictly in event metadata as informational context.
- **Tests:** `tests/test_crowd.py::test_crowd_count_thresholds`, `tests/test_crowd.py::test_crowd_hysteresis_state_transitions`.
- **Acceptance Criteria:** `CROWD_DENSITY` fires reliably when simulated zone count >= 4; zero false alarms on single occupants in tiny zones.
- **Complexity:** Small | **Risk:** Low.

### Task 4.2: BehaviorAnalytic Kinematic Heuristics (Running, Abnormal, Loitering, Night)
- **Objective:** Implement `backend/analytics/behavior.py` using pure mathematical kinematics over `TrackState.positions` (maxlen 60 deque of foot-points) without AGPL code contamination.
- **Files Involved:**
  - Created: `backend/analytics/behavior.py`
  - Created: `docs/BEHAVIOR_CALIBRATION.md` (empirical calibration log on test clips)
  - Modified: `backend/analytics/__init__.py`
  - Modified: `backend/services/session.py` (append behavior module to `self._analytics`)
  - Modified: `backend/core/config.py`, `config/default.toml` (add `[behavior]` and `[crowd]` config sections)
  - Tests: `tests/test_behavior.py` (new)
- **Dependencies:** Task 4.1.
- **Expected Behavior:**
  - **Running (`SUSPECTED_RUNNING`):** Over window W=10 samples, calculate `speed_score = min(1.0, avg_px_s / 80)`, `displacement_score = min(1.0, disp_px / 150)`, `direction_score = resultant_vector_length`. `confidence = 0.5*speed + 0.3*disp + 0.2*dir`. Triggers when confidence >= 0.50 for >= 3 consecutive ticks. Severity: `MEDIUM` (raised to `HIGH` if inside RESTRICTED zone).
  - **Abnormal Movement (`SUSPECTED_ABNORMAL_MOVEMENT`):** Rolling median speed baseline per camera over 60s. Triggers when speed > max(2.0*baseline, 120px/s) and direction stability < 0.30 for >= 3 ticks. Severity: `LOW`.
  - **Loitering (`LOITERING`):** Track confirmed >= 20.0s wall time with spatial bounding radius < 80px. Severity: `LOW` (raised to `MEDIUM` in restricted zones).
  - **Night Movement (`NIGHT_MOVEMENT`):** Track active while `ctx.is_night` (luminance < 40) for >= 5 consecutive ticks. Severity: `LOW`.
  - All heuristics labeled "SUSPECTED" in metadata and UI.
- **Tests:** `tests/test_behavior.py::test_running_synthetic_trajectory`, `tests/test_behavior.py::test_abnormal_movement_erratic`, `tests/test_behavior.py::test_loitering_dwell`, `tests/test_behavior.py::test_night_movement_gated`.
- **Acceptance Criteria:** `crowd.../assets/running.mp4` triggers `SUSPECTED_RUNNING`; static tracks trigger `LOITERING` after 20s; zero AGPL imports in codebase (verified via grep gate); suite green.
- **Complexity:** Large | **Risk:** Medium (calibration tuning).

### Task 4.3: Additive Event Engine Severity Mapping (_NEW_TYPE_BASE) (§2.6)
- **Objective:** Add explicit additive routing `_NEW_TYPE_BASE` to `backend/analytics/engine.py` to correctly map new V3.5 event types to severities without falling back to default `INFO`.
- **Files Involved:**
  - Modified: `backend/analytics/engine.py`
  - Tests: `tests/test_behavior.py`, `tests/test_crowd.py`
- **Dependencies:** Task 4.2.
- **Expected Behavior:**
  - Define `_NEW_TYPE_BASE` mapping:
    ```python
    _NEW_TYPE_BASE = {
        "SUSPECTED_RUNNING": Severity.MEDIUM,
        "CROWD_DENSITY": Severity.MEDIUM,
        "FACE_DETECTED": Severity.LOW,
        "SUSPECTED_ABNORMAL_MOVEMENT": Severity.LOW,
        "LOITERING": Severity.LOW,
        "NIGHT_MOVEMENT": Severity.LOW,
        "ANPR_READ": Severity.MEDIUM,
        "ANPR_PLATE_DETECTED": Severity.LOW,
        "OCR_UNCERTAIN": Severity.LOW,
        "PERSON_IDENTITY_MATCHED": Severity.INFO,
        "PERSON_CAMERA_TRANSITION": Severity.INFO,
    }
    ```
  - In `_severity_for(draft)`: check `_NEW_TYPE_BASE` and apply zone modifiers (e.g., `RESTRICTED` zones elevate `SUSPECTED_RUNNING` to `HIGH` and `LOITERING` to `MEDIUM`).
- **Tests:** `tests/test_behavior.py::test_engine_severity_ladder_custom_events`.
- **Acceptance Criteria:** All custom events receive designated `MEDIUM`/`LOW` severities with proper zone elevation; none incorrectly default to `INFO`.
- **Complexity:** Small | **Risk:** Low.

---

## Phase 5: Deterministic Summary & Investigation Enrichment

### Task 5.1: [GOD HUNK] Schema Migration 3 & DAO Trajectory Persistence
- **Objective:** Apply additive schema Migration 3 (`ALTER TABLE tracks ADD COLUMN trajectory TEXT`) and extend `TrackDAO.flush_tracks()` to persist downsampled normalized trajectories (<= 60 points JSON).
- **Files Involved:**
  - God-Managed: `backend/db/migrations.py` (migration 3), `backend/db/dao.py` (`upsert_track_trajectories` / extended `flush_tracks`)
  - Executor Code: `backend/services/session.py` (downsample and serialize trajectory in `_finalize_tracks` with graceful `hasattr` check)
  - Tests: `tests/test_summary.py` (new)
- **Dependencies:** Phase 4 complete. Flag dependency to God at Phase 5 start.
- **Expected Behavior:**
  - Migration 3 executes idempotently adding nullable `trajectory` column to `tracks` table.
  - When session completes, `_finalize_tracks` converts `TrackState.positions` to JSON string `[{"x": norm_x, "y": norm_y, "t": tick}, ...]` (max 60 points) and passes to DAO.
  - If column/method is absent in older DB, degrades gracefully without error.
- **Tests:** `tests/test_summary.py::test_migration_3_trajectory_column`, `tests/test_summary.py::test_trajectory_persistence_roundtrip`.
- **Acceptance Criteria:** Database migration applies cleanly; persisted tracks retrieve valid trajectory JSON; existing rows with NULL trajectory load without error.
- **Complexity:** Medium | **Risk:** Low (guarded by God hunk isolation).

### Task 5.2: Backend Session Summary Service (GET /api/sessions/{id}/summary)
- **Objective:** Implement `backend/services/summary.py` providing deterministic session audit summaries computed solely from database rows and session stats without LLM hallucinations.
- **Files Involved:**
  - Created: `backend/services/summary.py`
  - Modified: `backend/api/sources.py` (add route `GET /api/sessions/{id}/summary` inline)
  - Tests: `tests/test_summary.py`
- **Dependencies:** Task 5.1.
- **Expected Behavior:**
  - Returns dictionary matching schema: `{session_id, source_id, duration_s, frames, people_detected, vehicles_detected, unique_tracks, events_by_severity, events_by_type, zones_breached, max_concurrent_people, first_event_ts, last_event_ts, notes: [...]}`.
  - `notes` contains factual, template-generated summaries (e.g., "ZONE_ENTRY HIGH committed in restricted zone 'North Perimeter' at 00:14.2").
  - Returns 404 for unknown session ID, null summary with honest message if session unfinalized.
- **Tests:** `tests/test_summary.py::test_session_summary_deterministic_values`, `tests/test_summary.py::test_summary_endpoint_404`.
- **Acceptance Criteria:** Summary figures exactly match underlying `EventRow` and `TrackRow` database counts; zero fabricated sentences.
- **Complexity:** Medium | **Risk:** Low.

### Task 5.3: Investigation Page Trajectory Mini-Canvas & Related Events
- **Objective:** Enrich the Investigation UI with normalized trajectory mini-canvas visualizer and related events timeline.
- **Files Involved:**
  - Modified: `frontend/src/pages/Investigation.tsx`
  - Modified: `frontend/src/components/EventSummary.tsx`
  - Modified: `frontend/src/components/EventDetail.tsx`
  - Tests: `npx tsc --noEmit`, Playwright UI verification in `scripts/trinetra_e2e.py`
- **Dependencies:** Task 5.2.
- **Expected Behavior:**
  - Tracks table renders a mini `<canvas>` polyline displaying the person/vehicle movement path over time.
  - Selecting a track filters and highlights related events in the timeline.
  - Session summary panel displays the structured summary card on Dashboard and Investigation pages.
- **Tests:** `npm run build` clean, UI validation in E2E suite.
- **Acceptance Criteria:** Trajectory canvas renders normalized paths accurately; `tsc` 0 errors; UI functions with or without persisted trajectories.
- **Complexity:** Medium | **Risk:** Low.

---

## Phase 6: ANPR Heuristic & Graceful Network-Gate Fallback

### Task 6.1: Indian License Plate Regex & 3-State Validation Engine (§2.8)
- **Objective:** Implement `backend/analytics/anpr.py` containing validated Indian license plate regex validators supporting standard and official BH-series formats.
- **Files Involved:**
  - Created: `backend/analytics/anpr.py`
  - Tests: `tests/test_anpr.py` (new)
- **Dependencies:** Phase 5 complete.
- **Expected Behavior:**
  - Standard format regex: `^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$` (e.g., `DL01AB1234`, `MH12CD5678`).
  - BH-series format regex: `^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$` (e.g., `22BH1234AA`).
  - Validation engine classifies reads into three explicit states:
    1. `ANPR_READ` (Severity: `MEDIUM`): OCR confidence >= 0.80 and regex matches valid Indian format.
    2. `OCR_UNCERTAIN` (Severity: `LOW`): OCR text present but confidence < 0.80 or fails regex validation.
    3. `ANPR_PLATE_DETECTED` (Severity: `LOW`): Plate region localized, but OCR unavailable/unperformed.
- **Tests:** `tests/test_anpr.py::test_indian_plate_regex_standard`, `tests/test_anpr.py::test_indian_plate_regex_bh_series`, `tests/test_anpr.py::test_junk_rejection`.
- **Acceptance Criteria:** All test plate formats validate correctly; malformed strings properly flagged as `OCR_UNCERTAIN`; zero string coercion.
- **Complexity:** Small | **Risk:** Low.

### Task 6.2: Vehicle-Triggered Plate Detection & Network-Gated Fallback
- **Objective:** Implement vehicle-triggered plate detection in the session loop with automatic, honest fallback to heuristic plate localization when offline.
- **Files Involved:**
  - Modified: `backend/analytics/anpr.py`
  - Modified: `backend/services/session.py` (trigger on vehicle tracks with bbox width >= 100px)
  - Modified: `backend/main.py` (`_model_status()` reporting `models.anpr`)
  - Tests: `tests/test_anpr.py`
- **Dependencies:** Task 6.1.
- **Expected Behavior:**
  - Checks for presence of `models/yolov8n_plate.pt`. If absent, gracefully activates the color/aspect-ratio heuristic (detects bright rectangular lower-third region on vehicle bounding boxes).
  - Emits `ANPR_PLATE_DETECTED` (or `OCR_UNCERTAIN` / `ANPR_READ` if OCR model is available).
  - If plate crop < 64px wide, skips OCR to avoid high-noise hallucinations.
  - Never attempts network downloads in offline mode.
- **Tests:** `tests/test_anpr.py::test_anpr_offline_heuristic_fallback`, `tests/test_anpr.py::test_anpr_size_gating`.
- **Acceptance Criteria:** Emits `ANPR_PLATE_DETECTED` on vehicle clips without crashing; health status honestly reports model availability status; no network calls attempted.
- **Complexity:** Medium | **Risk:** Low.

### Task 6.3: UI ANPR State Labels & Evidence Verification
- **Objective:** Display ANPR events, plates, and state badges in the frontend with strict honesty labels.
- **Files Involved:**
  - Modified: `frontend/src/pages/Cameras.tsx` (ANPR toggle labeled "ANPR — plate detection only (no read)" when in heuristic fallback)
  - Modified: `frontend/src/components/EventDetail.tsx` (show plate crop, OCR confidence, format validation badge)
  - Tests: `npx tsc --noEmit`, E2E test runner
- **Dependencies:** Task 6.2.
- **Expected Behavior:**
  - UI clearly communicates whether ANPR is running full OCR or heuristic detection only.
  - Event details show plate metadata and validation status accurately.
- **Tests:** `npm run build` clean.
- **Acceptance Criteria:** Frontend builds with 0 errors; ANPR state transitions rendered accurately without placeholder text.
- **Complexity:** Small | **Risk:** Low.

---

## Phase 7: RTSP Ingestion & Camera Management Polish

### Task 7.1: RtspSource Class & VideoCapture FFMPEG Transport
- **Objective:** Implement `backend/sources/rtsp.py` adhering to the `VideoSource` protocol with robust TCP FFMPEG transport and backoff reconnection.
- **Files Involved:**
  - Created: `backend/sources/rtsp.py`
  - Modified: `backend/sources/__init__.py`
  - Tests: `tests/test_rtsp_source.py` (new)
- **Dependencies:** Phase 6 complete.
- **Expected Behavior:**
  - `RtspSource` defines `type_name = "rtsp"` and `is_live = True`.
  - Sets `os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"`.
  - Initializes `cv2.VideoCapture(uri, cv2.CAP_FFMPEG)`.
  - Implements exponential backoff reconnection ladder (1s -> 2s -> 4s -> 8s) on stream loss, emitting `SOURCE_LOST` and `SOURCE_RECONNECTED` notifications via `session.py:237-262`.
- **Tests:** `tests/test_rtsp_source.py::test_rtsp_source_lifecycle_and_backoff`.
- **Acceptance Criteria:** Gracefully handles invalid/dropped RTSP streams; reconnect loop functions without deadlocking session thread.
- **Complexity:** Medium | **Risk:** Low.

### Task 7.2: Source Type Registration & session.py:183 Resolution (§2.9)
- **Objective:** Ensure all source classes define explicit `type_name` and update `session.py:183` to resolve source types cleanly.
- **Files Involved:**
  - Modified: `backend/sources/base.py`, `backend/sources/file.py`, `backend/sources/webcam.py`, `backend/sources/rtsp.py`
  - Modified: `backend/services/session.py` (line 183: `src_type = getattr(self._source, "type_name", "file")`)
  - Modified: `backend/main.py` (`StartRequest` model accepts `uri: str = ""`)
  - Tests: `tests/test_rtsp_source.py`
- **Dependencies:** Task 7.1.
- **Expected Behavior:** RTSP sessions register in `active_session` payload with `source_type: "rtsp"` instead of defaulting to `"file"`.
- **Tests:** `tests/test_rtsp_source.py::test_source_type_resolution`.
- **Acceptance Criteria:** Session status correctly identifies RTSP sources; camera registry displays `rtsp` badge.
- **Complexity:** Small | **Risk:** Low.

### Task 7.3: RTSP Venv Benchmark & Camera/Map UI Polish
- **Objective:** Create `scripts/rtsp_test.py` benchmark script to measure RTSP FPS/TTFF on venv OpenCV 5.0.0 and polish Sources/Map UI.
- **Files Involved:**
  - Created: `scripts/rtsp_test.py`
  - Modified: `frontend/src/pages/Sources.tsx`
  - Modified: `frontend/src/pages/Geography.tsx`, `frontend/src/components/GeoMap.tsx`
  - Modified: `frontend/src/components/SourcePicker.tsx` (add RTSP stream URL input)
  - Tests: `npx tsc --noEmit`, E2E test runner
- **Dependencies:** Task 7.2.
- **Expected Behavior:**
  - `scripts/rtsp_test.py` runs against local MediaMTX loopback (if active) and outputs measured FPS and Time-To-First-Frame (TTFF) under venv cv2 5.0.0.
  - `Sources.tsx` table displays camera registry with live status matching active session.
  - Map marker clicks select camera card and center view; handles blocked Google Maps gracefully.
- **Tests:** `npm run build` clean.
- **Acceptance Criteria:** RTSP input accepts stream URIs; camera registry and map display real backend status; frontend build clean.
- **Complexity:** Medium | **Risk:** Low.

---

## Phase 8: Full E2E Demo Drill & Final Verification Report

### Task 8.1: Unified E2E Test Runner Extension (scripts/trinetra_e2e.py)
- **Objective:** Extend `scripts/trinetra_e2e.py` to execute a comprehensive, browser-scripted (Playwright Chromium) and API-level drill exercising all V3.5 capabilities in sequence.
- **Files Involved:**
  - Modified: `scripts/trinetra_e2e.py`
  - Created: `docs/TRINETRA_E2E_DEMO_LOG.md` (detailed execution log)
  - Tests: Full automated E2E run
- **Dependencies:** Phases 1-7 complete.
- **Expected Behavior:**
  - Boots isolated uvicorn test instance.
  - Runs 53-step verification checklist: Health check -> 4 light-theme cards zero -> Source upload (`running_clip.mp4`) -> Session start -> Live MJPEG stream with boxes/IDs/FPS -> Layer toggles (boxes off, trajectories on, zones on) -> Virtual fence breach (`ZONE_ENTRY` HIGH) -> Face detection (`FACE_DETECTED` LOW) -> Re-ID identity match (`PERSON_IDENTITY_MATCHED`) -> Running detection (`SUSPECTED_RUNNING`) on `running.mp4` -> Event summary diff == 0 invented facts -> Session stop -> Session summary query -> Persistence reload.
  - Records every step with timestamp, status (PASS/FAIL), and measured value in `docs/TRINETRA_E2E_DEMO_LOG.md`.
- **Tests:** `python scripts/trinetra_e2e.py`.
- **Acceptance Criteria:** All drill steps pass; zero assertion errors; detailed log generated.
- **Complexity:** Large | **Risk:** Medium.

### Task 8.2: Final Integration Report & Honesty Ledger (docs/TRINETRA_FINAL_INTEGRATION_REPORT.md)
- **Objective:** Generate the authoritative V3.5 final integration report containing verified test tallies, FPS benchmarks, honesty ledgers, and reproduction commands.
- **Files Involved:**
  - Created: `docs/TRINETRA_FINAL_INTEGRATION_REPORT.md`
- **Dependencies:** Task 8.1.
- **Expected Behavior:**
  - Documents verified test counts (all unit and integration tests passing, 4 skips preserved).
  - Documents benchmark table (FPS per capability on M4 CPU/MPS).
  - Documents honesty ledger classifying every feature as `VERIFIED`, `HEURISTIC`, `EXPERIMENTAL`, or `DISABLED`.
  - Documents open gaps honestly (ANPR Indian plate fine-tuning, multi-camera Re-ID field footage).
- **Tests:** `pytest -q`, `npx tsc --noEmit`, `npm run build`.
- **Acceptance Criteria:** Written report complete, transparent, and verified against actual system performance.
- **Complexity:** Medium | **Risk:** Low.

---

## 3. Phase Boundaries, Verification Gates & Report Points

To maintain strict chain-of-custody and prevent regression cascades, the following verification gates must be satisfied at each phase boundary before proceeding:

| Phase Boundary | Mandatory Verification Gate | Report Artifact / Action |
|---|---|---|
| **Phase 1 -> Phase 2** | `pytest tests/test_layers.py` (all green) + `npx tsc --noEmit` (0 errors) + `npm run build` clean | Report to God: Phase 1 Layer Toggles & Per-Class Counts complete. |
| **Phase 2 -> Phase 3** | `pytest tests/test_m8_reid.py tests/test_reid_port.py` (34/34 green) + Re-ID dynamic batch latency <= 10ms | Report to God: Phase 2 Re-ID Port & F1 Optimization complete. |
| **Phase 3 -> Phase 4** | `pytest tests/test_face.py` (all green) + `models/yunet.onnx` verified in place | Report to God: Phase 3 YuNet Face Detection complete. |
| **Phase 4 -> Phase 5** | `pytest tests/test_behavior.py tests/test_crowd.py` (all green) + AGPL grep-gate clean | Report to God: Phase 4 Behavior/Crowd Analytics complete. **Request God Hunk for Migration 3.** |
| **Phase 5 -> Phase 6** | `pytest tests/test_summary.py` (all green) + Migration 3 applied + Summary endpoint 200 OK | Report to God: Phase 5 Deterministic Summary & Persistence complete. |
| **Phase 6 -> Phase 7** | `pytest tests/test_anpr.py` (all green) + Offline fallback verified (no network calls) | Report to God: Phase 6 ANPR Heuristic & Graceful Fallback complete. |
| **Phase 7 -> Phase 8** | `pytest tests/test_rtsp_source.py` (all green) + RTSP stream lifecycle verified | Report to God: Phase 7 RTSP Ingestion & Camera Polish complete. |
| **Phase 8 (Final)** | Full suite `pytest -q` (all green, 4 skips) + `python scripts/trinetra_e2e.py` (all steps PASS) | Deliver `docs/TRINETRA_FINAL_INTEGRATION_REPORT.md` and report to God for Oscar review. |

---

## 4. Risk Register & Non-Negotiable Governance Rules

### 4.1 Binding Risk Register
1. **R1: AGPL Contamination:** Zero code, imports, or file copies from `crowd-abnormal-behavior-detection-main`. All behavior algorithms are implemented clean-room from kinematic geometry.
2. **R2: Strict Honesty & No Fake Data:** No mock generators, no Math.random in UI, no fabricated OCR plates, and no hallucinated LLM summaries. Heuristics are explicitly tagged `SUSPECTED`.
3. **R3: Shared-JPEG Rule (A1):** Operator MJPEG frame and evidence snapshot remain byte-identical from a single encoding pass. Layer toggles affect both by design.
4. **R4: Suite Green Gate:** Full pytest test suite must remain green across all existing and new tests at every step. The 4 historical skips must remain unchanged.
5. **R5: Clean Frontend Gate:** `npx tsc --noEmit` must report 0 errors and `npm run build` must complete cleanly after every frontend modification.
6. **R6: Hardware Honesty:** This M4 machine has no active webcam; webcam selection must honestly display "no camera available".
7. **R7: Uncommitted Hardening Diffs:** The two existing uncommitted hardening diffs (`backend/api/map.py` and `backend/vision/annotation.py`) must be preserved without reversion.
8. **R8: Single Executor Discipline:** `executer-mtum4rce` is the sole implementer to maintain architectural context and prevent merge conflicts.
9. **R9: Commits Reserved for God:** All executor modifications remain uncommitted in the working tree for God review and Oscar adversarial verification.

---

## 5. File Manifest Summary

| Phase | New Files to Create | Existing Files to Modify |
|---|---|---|
| **Phase 1** | `tests/test_layers.py` | `backend/services/session.py`, `backend/main.py`, `frontend/src/components/LiveFeed.tsx`, `frontend/src/pages/Cameras.tsx`, `frontend/src/pages/Analytics.tsx`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/components/EventSummary.tsx`, `frontend/src/api.ts`, `frontend/src/types.ts` |
| **Phase 2** | `scripts/m8_reid_bench.py` | `backend/reid/embedder.py`, `backend/reid/integration.py`, `backend/main.py`, `backend/services/session.py`, `frontend/src/components/EventDetail.tsx`, `frontend/src/pages/Investigation.tsx` |
| **Phase 3** | `Trinetra/models/yunet.onnx` (copy), `backend/vision/face.py`, `tests/test_face.py`, `tests/assets/face_frame_intrusion.jpg` | `backend/services/session.py`, `backend/vision/annotation.py`, `backend/main.py`, `frontend/src/pages/Cameras.tsx` |
| **Phase 4** | `backend/analytics/crowd.py`, `backend/analytics/behavior.py`, `docs/BEHAVIOR_CALIBRATION.md`, `tests/test_crowd.py`, `tests/test_behavior.py` | `backend/analytics/__init__.py`, `backend/analytics/engine.py`, `backend/services/session.py`, `backend/core/config.py`, `config/default.toml`, `frontend/src/pages/Cameras.tsx` |
| **Phase 5** | `backend/services/summary.py`, `tests/test_summary.py` | `backend/db/migrations.py` (God hunk), `backend/db/dao.py` (God hunk), `backend/services/session.py`, `backend/api/sources.py`, `frontend/src/pages/Investigation.tsx`, `frontend/src/components/EventSummary.tsx`, `frontend/src/components/EventDetail.tsx` |
| **Phase 6** | `backend/analytics/anpr.py`, `tests/test_anpr.py` | `backend/services/session.py`, `backend/main.py`, `frontend/src/pages/Cameras.tsx`, `frontend/src/components/EventDetail.tsx` |
| **Phase 7** | `backend/sources/rtsp.py`, `scripts/rtsp_test.py`, `tests/test_rtsp_source.py` | `backend/sources/__init__.py`, `backend/sources/base.py`, `backend/sources/file.py`, `backend/sources/webcam.py`, `backend/services/session.py`, `backend/main.py`, `frontend/src/pages/Sources.tsx`, `frontend/src/pages/Geography.tsx`, `frontend/src/components/GeoMap.tsx`, `frontend/src/components/SourcePicker.tsx` |
| **Phase 8** | `docs/TRINETRA_E2E_DEMO_LOG.md`, `docs/TRINETRA_FINAL_INTEGRATION_REPORT.md` | `scripts/trinetra_e2e.py` |

---

## 6. Open Decisions & Asks for God

1. **Phase 5 God-Hunk Timing:** Confirmation that God will apply Migration 3 (`ALTER TABLE tracks ADD COLUMN trajectory TEXT`) and the associated `DAO` method when Phase 5 begins, allowing the executor to implement the session flush cleanly.
2. **Re-ID Router Placement:** Permission to keep Re-ID endpoints inline in `main.py` or include a minimal `backend/api/reid.py` via a single sanctioned line in `main.py:50-56`.
3. **Chain Hand-Off:** Ready for Stage 3 (ARCHITECT `architect-and-pipeline-mtum77rw`) review and formal sign-off.
