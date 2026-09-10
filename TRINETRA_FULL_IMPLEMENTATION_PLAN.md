# TRINETRA — FULL IMPLEMENTATION PLAN (V3.5 Capability Build)

**Author:** PLANNER · **Date:** 2026-09-10 · **Executor:** EXECUTOR1 (the ONLY implementer)
**Base:** Trinetra @ HEAD `3d0c7e2` (M7) + 2 uncommitted hardening diffs (map.py, annotation.py) — **leave those alone, do not revert, do not commit them yourself**; EXECUTOR's own changes stay UNCOMMITTED for MICHAEL review.
**Mission:** turn the verified M7 core into a REAL end-to-end video-analytics platform using the workspace resources (see `TRINETRA_RESOURCE_INVENTORY.md`). NO FAKE DATA, NO FEATURE THEATER, honest evidence-backed labels everywhere. Target machine: MacBook Air M4 16GB.

**Governing rules (binding, from master prompt + handoff):**
- NO NEW DEPS beyond torch/ultralytics/opencv/numpy/fastapi stack already present. `onnxruntime` is NOT allowed — Phase 2 uses cv2.dnn instead (planner-measured working). PaddleOCR (Phase 6) is the ONLY exception and only after MICHAEL approves acquisition.
- Lazy/selective model loading (§44): NO model loads at import/boot; every capability gate-checks file presence and reports honestly (pattern: `main.py:73-82` `_model_status`, `embedder.py:111-127` `_try_load`).
- ONE active session (session.py:445-482 enforces it) — every UI surface derives from `active_session`; nothing may imply multi-camera concurrency.
- Shared-JPEG rule (A1): evidence snapshot == operator frame, byte-identical (session.py:321-335). Layer toggles affect both — documented, defaults all-ON.
- ByteTrack is the ONE tracker authority; analytics modules only read `(ctx, view)` (analytics/base.py:53-79) except Re-ID which additionally receives the frame (integration.py:1-15 documents this seam).
- Suite-green gate: `pytest -q` full suite green at **≥207 collected + all new tests**, 4 skips unchanged (planner re-verified 207 today). Frontend gate: `npx tsc --noEmit` 0 errors + `npm run build` clean.
- No webcam on this machine honesty: file-source demo; webcam path stays implemented and honestly reports "no camera available" (M7_REPORT.md:57). NEVER fake a webcam.
- Commits NOT in scope: executor leaves tree changes uncommitted for MICHAEL review.

---

## MODEL_DECISIONS TABLE

| Capability | PRIMARY | FALLBACK | EXPERIMENTAL | REJECTED |
|---|---|---|---|---|
| Detection (person/vehicle) | `yolov8n.pt` (Trinetra/models/, in use) | yolov8s if small objects disappoint (not acquired) | — | yolov7-tiny ×2, yolo26n, ssdlite pb/tflite (duplicate/dead families) |
| Tracking | ByteTrack builtin (only authority) | — | — | any second tracker |
| Re-ID embedding | **`fast-reid_mobilenetv2.onnx` via cv2.dnn** (batch-32 pad, raw-scale 256×128; discrimination margin 0.638 measured; loads+infers in main venv — planner-verified today) | `TorchScriptEmbedder` class retained (m8 seam) | cross-camera claims until 2-camera footage test | `reid.ts` InceptionV3 proxy for shipping (false-confirms at 0.80 — M8_BENCHMARKS.md:28); OSNet x0.25 (margin 0.334 overlapping) |
| Re-ID correlation/gallery | m8 `backend/reid` package port (gallery/matcher/sampling/history — 23 tests) | — | — | re-implementing the machinery |
| Face detection | `yunet.onnx` via `cv2.FaceDetectorYN` (2.8ms measured; 232,589 bytes in temp — COPY+COMMIT) | MTCNN ncnn det1-3 (verified loadable; needs pip ncnn — only activate if YuNet fails) | — | model.pth RetinaFace/mmdet; dlib; TF1 FaceNet; face *recognition*/identity DB entirely OUT of scope |
| Pose (behavior) | `yolov8n-pose.pt` selective every-3rd (only IF fall/posture ships — copy from BorderSurvaillance/) | — | crop-pose hybrid (17.1 vs 21.9 FPS — not worth it) | pose every frame (13.5 FPS) |
| Running/abnormal/loitering/night | Deterministic heuristics on TrackState.positions (reimplemented from crowd-repo concepts; constants below) | — | per-camera threshold calibration | calling heuristics "action recognition" |
| Fall (optional stretch) | pose-geometry + trajectory-drop fusion (crowd-repo concept, reimplemented) | — | needs pose model import | TSSTG best-model.pth, tsstg-model.pth |
| Crowd analytics | deterministic count/density/occupancy from authoritative tracker | — | — | any "AI crowd model" claim |
| ANPR (Phase 6) | plate-detect: open Indian-plate LPD model **to acquire** (single recommendation below) + OCR: **PaddleOCR CPU** | plate-only detection without read (PLATE_DETECTED) | OCR_UNCERTAIN state | fabricating plates; Russian haar cascade (not found locally anyway) |
| Agentic summary | deterministic EventSummary over verified EventRows | — | optional LLM renderer ONLY if provided; never invents facts | LLM generating event facts |
| Night | luminance gate (<40 mean gray, session.py:63) + tracked movement | CLAHE pre-pass (sentinel concept) if quality demands | — | thermal/night-AI claims |

---

# PHASE 0 — RE-VERIFY THE UPLOAD→BROWSER CHAIN (broken-before-new)

**Why first:** master prompt says "the upload flow does not reliably result in the uploaded video appearing in the WebUI" while `uploads/` contains 2 real files uploaded 2026-09-10 01:22 via the UI — the chain is UNVERIFIED-BROKEN. Everything else builds on a working browser→analytics loop.

**Method — extend `scripts/m7_e2e.py` into `scripts/trinetra_e2e.py`** (new file; leave m7_e2e.py untouched as the 24-check regression harness):
1. Boot uvicorn on a free port (same pattern m7_e2e.py:14-23).
2. **Playwright (Chromium)** via the installed CLI/npx (1.63.0 — planner-verified present OUTSIDE venv; run as a subprocess or node script; do NOT pip-install anything): open `http://127.0.0.1:{port}/`, assert: header shows TRINETRA/SYSTEM ONLINE (App.tsx:54-71), 4 cards render (Dashboard.tsx:29-45).
3. Navigate to Live View; drop `tests/assets/running_clip.mp4` through the REAL UI drop zone (SourcePicker.tsx:44-60 onDrop → `api.uploadVideo` XHR `api.ts:80-98` → `POST /api/sources/upload` `sources.py:72-117` probe-validated).
4. Click START ANALYSIS (SourcePicker.tsx:189 `startSession('file',{path:upload.path})` → `POST /api/session/start` main.py:115-152).
5. Assert IN THE BROWSER: MJPEG `<img>` receives REAL frames (decode ≥10 multipart JPEGs — sized >2KB, not the black frame), session pill RUNNING, camera row LIVE, PERSON_DETECTED appears in LIVE ALERTS ≤5s (SSE path App.tsx EventTimeline), People Detected card increments on next status poll.
6. Also re-run the API-level m7_e2e.py as-is (regression, 24 checks must stay green).
7. Repeat the browser drill with one of `uploads/22c250_Normal_Videos057_x264.mp4` (the real 14MB upload — proves the previously-uploaded file path replays).
8. Webcam scan button: press, honestly record result (this machine likely "no camera available" — that is a PASS if the message is honest).

**If (and only if) something is actually broken:** fix the minimal seam — likely candidates (do not preemptively change): upload response path handling in SourcePicker (frontend), `make_source` path validation (session.py:485-499), MJPEG generator status handling (main.py:183-194). Any fix must state the exact observed failure in its section of the final report.

**Acceptance:** a written `docs/PHASE0_E2E_LOG.md` (executor fills during run; honest PASS/FAIL per step with screenshots dir `docs/phase0_shots/` if Playwright supports it) + regression m7_e2e 24/24 + full pytest suite green ≥207. **No code changes expected unless a real break is found.**
**Test mapping:** §52 items upload/start/live-frames/SSE-visible.
**Files touched:** `scripts/trinetra_e2e.py` (new), `docs/PHASE0_E2E_LOG.md` (new). Nothing else.

---

# PHASE 1 — V3 P1 BACKEND COMPLETION + LIVE VIEW TOGGLES

*(This phase completes the V3 P1 remainder exactly as specced by TRINETRA_IMPLEMENTATION_PLAN.md T1.1-T1.6 + HANDOFF corrections C2-C7, C9, C10 — reproduced here in executable form with current file:line refs.)*

## 1.1 Per-class counts in status payload (C5 race-safe)
- **File:** `backend/services/session.py` (`status_payload` :414-428, `_stats_payload` :402-410).
- **Change:** snapshot-copy `tracks = dict(self._store.tracks)` once (GIL-atomic; kills the API-thread vs session-thread dict-mutation race — C5), then compute ADDITIVELY: `people_detected`/`vehicles_detected` (cumulative unique tracks whose `class_name` == "person" / in `_VEHICLE_CLASSES` session.py:65-66 — reuse, never duplicate the set) and `active_people`/`active_vehicles` (sums over snapshot, same semantics as `count_active` tracks.py:202). Zero when zero. Add the same 4 keys to `_stats_payload` so session rows persist them.
- **Tests:** new `tests/test_layers.py` (one file for all Phase-1 backend tests): status fields on stub session with synthetic tracks; zero-when-empty; no-iteration-race smoke (assert snapshot copy used).
- **Acceptance:** GET /api/session/status during a running_clip session shows `people_detected > 0`; suite green ≥207+new.

## 1.2 Render-layer wiring in the session loop (C2 single-renderer + C3 atomic swap + C4 contract)
- **Files:** `backend/services/session.py` ONLY (annotation.py already has the full C4 surface — annotate signature :98-106, layer parse :124-130, trajectory draw :81-95, zone draw :48-78; DO NOT touch annotation.py, it carries an uncommitted hardening diff that must survive).
- **Change:**
  - `__init__`: `self._layers = {"boxes": True, "labels": True, "fps": True, "trajectories": False, "zones": True}` + `self._layers_lock = threading.Lock()`. Defaults per handoff §3 (zones ON = intended M7 completion; trajectories OFF preserves today's look).
  - New method `update_layers(partial: dict) -> dict` (validate keys, unknown → raise ValueError for the route to 400; store as NEW dict under lock: `self._layers = {**self._layers, **valid}` — C3 immutable-swap; render thread reads the reference once per tick, no lock held across annotate).
  - New method `get_layers() -> dict`.
  - `_annotate` (:205-214): pass `layers=self._layers` (read once), `trajectories={tid: [(x, y) for x, y, _tick in t.positions] for active person/vehicle tracks}` (3-tuple deque → 2-tuple pixels, tracks.py:72-80) when `layers["trajectories"]`, and `zones=<normalized dicts for this source>` when `layers["zones"]` — build from `self._zones.zones(self.source_id, active_only=True)` (zones.py:207-223) converting Zone objects to §12 dicts exactly as `api/zones.py:53-60` does (`kind`, `zone_type`, `geometry` JSON, `name`). Reuse the per-tick zone read pattern the fence already does (fence.py:95); wrap in try/except → zone-draw never kills a frame (annotation already degrades per-zone, annotation.py:76-78).
- **C2 binding:** once server-side zones are live, REMOVE the existing-zones canvas draw in `frontend/src/components/LiveFeed.tsx:21-73` (double-draw ban); the Virtual Fence toggle drives the server layer only. KEEP the VideoZones editor preview (authoring UX).
- **Endpoints (C7 placement):** add INLINE in main.py session-endpoints region (after :168, next to start/stop/status; NO new router file, NO touching include block :50-56 / lifespan / `_DIST` mount :263-267):
  - `POST /api/session/layers` body `{boxes?, labels?, fps?, trajectories?, zones?}` partial merge; unknown key → 400; no active session → 404 `{"detail": "no active session"}`; returns `{"layers": {...}}`.
  - `GET /api/session/layers` same shape; 404 without session.
- **Tests (test_layers.py):** endpoint 404/400/200/merge; annotate-with-layers unit (boxes off → no rectangles drawn — pixel-count or monkeypatched cv2.rectangle spy); trajectories drawn as polylines on synthetic pts; zones-in-evidence: stub session commit path shows zone pixels (or verify annotate receives zone dicts via monkeypatch — honest, no over-mock); defaults byte-identical (call _annotate without layers change → identical output to M7 baseline on a fixture frame).
- **Acceptance:** with running_clip session: POST layers `{boxes:false}` → next frames have no rectangles within ~1-2s; trajectories ON → foot-point paths visible; zones burned into MJPEG AND evidence snapshots (fence visible in ZONE_ENTRY evidence); FPS drop <5% vs baseline (reuse `scripts/bench.py`); suite green.

## 1.3 Live View + Analytics UI wiring
- **Files:** `frontend/src/pages/Cameras.tsx` (add stats strip + Analytics Layers toggle bar), `frontend/src/components/SourcePicker.tsx` (labels only), `frontend/src/components/LiveFeed.tsx` (REMOVE client zone overlay per C2 — lines 21-73 zone-draw path; keep video well + status chips), `frontend/src/api.ts` (add `sessionLayersGet/Post`), `frontend/src/types.ts` (SessionPayload + 4 fields people_detected/vehicles_detected/active_people/active_vehicles), `frontend/src/pages/Analytics.tsx` (Runtime panel: people/vehicles/active tracks/FPS/frames/device/uptime from status; Trajectory Info = `history_len` 60 points × active tracks; Fence Status = zone count + `zone_person_counts`), `frontend/src/pages/Dashboard.tsx` (cards 1-2 switch to session fields — replace the interim event-derived loop at Dashboard.tsx:20-24).
- **Toggle bar:** Detections / Track IDs / Trajectories / Virtual Fence / FPS → POST /api/session/layers (Virtual Fence maps to `zones` key); disabled with visible reason "no active session" when idle; reset to defaults on session end (GET refresh). Every toggle hits the real endpoint — NO dead controls.
- **Acceptance:** network tab shows real POSTs; toggling visibly changes the stream; `tsc --noEmit` + `vite build` clean; zero-when-zero on all cards.

## 1.4 AI/Event Summary surface (deterministic, frontend-only)
- **Files:** NEW `frontend/src/components/EventSummary.tsx`; mount on Dashboard below ALERTS SUMMARY (Dashboard.tsx:53 area) — keep the "HERMES — NOT CONNECTED" honesty block in App.tsx:112-116 untouched.
- **Behavior:** consumes ONLY real EventRow fields. Template: `At {ts}, {Type label} — severity {severity} — source {source_id}{, Track #ids}{, zone {name}}{, direction {direction}}{. Reason: severity_reason}`. Zone name resolved from `store.zones` by zone_id (C6: deleted zone → show raw zone_id or omit — never fabricate). Last 3-5 events as feed; empty state "no events yet — run a session". Zero facts not present in the row.
- **Acceptance:** diff 3 sentences vs Event Log rows (incl. one ZONE_ENTRY with track+zone+direction) → zero invented facts.

**Phase 1 files total:** `backend/services/session.py`, `backend/main.py` (inline routes), `tests/test_layers.py` (new), frontend: Cameras/Analytics/Dashboard/SourcePicker/LiveFeed/api.ts/types.ts/EventSummary.tsx(new).
**Test mapping:** §52 layer toggles, per-class counts, event summary, live-view stats.

---

# PHASE 2 — M8 RE-ID PORT (with the fast-reid-via-cv2.dnn upgrade)

**Copy from `Trinetra-m8/`** (read-only source; do NOT touch that repo): `backend/reid/` package (all 11 modules), `tests/test_m8_reid.py`, `scripts/m8_reid_bench.py`, and the `[reid]` config block.

**Config merge — `Trinetra/config/default.toml`:** append the m8 `[reid]` block (Trinetra-m8/config/default.toml:39-54) AND extend with `embedder = "cv2dnn"` default + `onnx_path = "fast-reid_mobilenetv2.onnx"`. **`backend/core/config.py`:** add `ReIdCfg` dataclass (mirroring m8 config.py:82-101 minus torchscript-only bits, plus cv2dnn fields) and extend `_build()` (:91) to parse `[reid]` → export `REID` (m8 config.py:141-150 pattern; main tree currently exports 7 groups at :140 — append REID, keep all existing).

**New embedder — `backend/reid/embedder.py` (port + extend):**
- Port the file as-is (it keeps `TorchScriptEmbedder` + `DummyEmbedder` + frozen `preprocess_crop`), then ADD:

```python
class OpenCVDnnEmbedder(ReIDEmbedder):     # PRIMARY (no onnxruntime dep)
    name = "cv2dnn"
    def __init__(self, onnx_path=None): ...  # MODELS_DIR / onnx_path
    # _try_load: cv2.dnn.readNetFromONNX; honest available gate (file-missing → False)
    # embed(crop): preprocess_crop(crop) → batch-pad to 32 (fixed-shape graph)
    #   → net.forward()[0] → l2_normalize
```
- Batch-32 pad contract + raw-scale 256×128 (RGB, INTER_CUBIC, float32, NO /255, HWC→CHW) — embedder.py:42-61 `preprocess_crop` is already exact; pad is the new piece. **Planner-measured today in the main venv: load ✓, [32,3,128,256]→[32,1280] ✓, 96.9ms/batch (3.03ms/crop effective).**
- `make_embedder` (integration.py:77-86): add the `"cv2dnn"` branch.

**Model files — `Trinetra/models/`:** COPY `fast-reid_mobilenetv2.onnx` from `DeepCamera-master/src/yolov7_reid/src/models/` (8.5MB, MIT — license-safe). **Do NOT copy reid.ts** (109MB proxy; false-confirms at 0.80 per M8_BENCHMARKS.md:28 — see inventory §6 Q1; TorchScriptEmbedder stays for provenance but nothing points at it by default). Record the md5 (77a97e84aac88bdb3eeaa17dd6c57180, planner-measured) in the models manifest comment.

**Integration into the M7 session loop — `backend/services/session.py`:**
- Import lazily inside `__init__`-adjacent guarded block (§44: model file check via `embedder_available`; honest no-op if missing — integration.py:150-152 already returns [] when unavailable; NO identity ever fabricated, test T14 pins it).
- App-scoped service: create ONE `MultiCameraReIdService` per app — instantiate in `main.py` lifespan (:212-250) right after the ZoneStore install (:234), stash in ApiState (`backend/core/errors.py` `_state`) alongside dao/hub/zone_store; the SESSION fetches it via the same `get_*` accessor pattern. (m8 kept it session-side; M7's app-scoped ZoneStore pattern — main.py:231-234 — is the correct analog. **OPEN QUESTION → default OK: m8 contract says "one per app; cameras register" — single-session MVP registers the running source_id as the camera_id on session start and unregisters on finalize.**)
- Per-tick wiring in `_run` (:304-319 region), AFTER the analytics chain, BEFORE annotate:
  ```python
  drafts += reid.process_tick(self.source_id, ctx, view, pkt.frame)   # sampling inside
  drafts  = reid.enrich_drafts(self.source_id, drafts)                # fence enrichment
  ```
  ByteTrack stays sole tracker; reid never positions/tracks (integration.py:1-15).
- `FrameContext`/`EventDraft` are byte-identical between trees (planner-diff-verified) — zero analytics/base.py changes.
- Event types `PERSON_IDENTITY_MATCHED` / `PERSON_CAMERA_TRANSITION` flow through the EXISTING engine unchanged (generic INFO branch engine.py:235-237; cooldown backstop engine.py:190-201 applies; severity stays INFO — identity is context, the alarm stays ZONE_ENTRY's HIGH, M8_REID.md:79-83).
- Enrichment: ZONE_ENTRY/LINE_CROSSING/PERSON/VEHICLE_DETECTED drafts gain `global_person_id` + `identity_cameras` metadata ONLY when CONFIRMED (integration.py:257-287; CANDIDATE never links — thresholds 0.80 confirm / 0.55 candidate-never-merge, m8 contract table).

**Config block (ported, with new defaults):**
```toml
[reid]
embedder = "cv2dnn"                  # fast-reid ONNX via cv2.dnn (PRIMARY)
onnx_path = "fast-reid_mobilenetv2.onnx"
confirm_similarity = 0.80
candidate_similarity = 0.55
max_gap_s = 600.0
exemplars_per_camera = 8
sample_interval_ticks = 25
sample_min_frames_seen = 5
sample_min_gap_s = 10.0
```

**Tests:** port `tests/test_m8_reid.py` VERBATIM (23 tests, DummyEmbedder — no model download, all port clean). ADD: `tests/test_reid_port.py` — (a) OpenCVDnnEmbedder loads the committed onnx and embeds a synthetic crop to a 1280-d unit vector (skip-with-reason if model file absent — pattern: pytest.importorskip/file-exists skip); (b) discrimination smoke: two crops of the same synthetic identity vs different → same > diff (weak assertion, model quality is already audit-proven; keep it a shape/scale test, don't over-claim); (c) end-to-end wiring: stub session with reid enabled → PERSON_IDENTITY_MATCHED appears once, ZONE_ENTRY carries global_person_id when confirmed, enrich respects CANDIDATE-never-links.
**Bench:** port `scripts/m8_reid_bench.py`, point at the cv2dnn embedder; record FPS with reid ON vs OFF on running_clip (budget: selective sampling ≤1 embed/track/25 ticks + 10s → ~1-2 embeds/s — well within headroom per m8 latency math; planner-measured 90ms/single padded forward).

**UI surfaces:**
- `frontend/src/components/EventDetail.tsx`: show `global_person_id` + `identity_cameras` chips when present in metadata (absent → nothing; never placeholder).
- Investigation page (`frontend/src/pages/Investigation.tsx`): "Identity" strip for events with global ids — cameras visited, first/last seen, track bindings from `svc.person_summary` (contract M8_CROSS_CAMERA_CONTRACT.md:93-119). Backend surface: NEW small endpoints INLINE in main.py session-region or a minimal `backend/api/reid.py` router **included via ONE line in main.py:50-56 include block — this is the single sanctioned edit to that block** (C7 relaxed for this phase because it's an additive router, matching the M7 map.py precedent; if MICHAEL objects, inline in main.py instead): `GET /api/reid/persons` (all_persons) + `GET /api/reid/persons/{pid}` (person_summary). 404-clean, honest empty when no identities.
- Live View advanced toggles: "Re-ID" toggle — enabled only when model present (health surface: extend `_model_status()` main.py:73-82 to report reid onnx present/absent); OFF by default; label "EXPERIMENTAL — possible-match semantics" until 2-camera footage exists (audit §32).
- Cross-camera wording rule: single-video re-entry = "match"; cross-camera = "POSSIBLE MATCH (score)" — never "same person" (audit §15).

**Acceptance:** 207+23+new all green; running_clip session with reid ON: FPS drop <15% vs reid OFF (measure, don't guess); PERSON_IDENTITY_MATCHED fires once per identity; enriched ZONE_ENTRY shows global_person_id; UI shows identity chips only when real.
**Test mapping:** §52 reid toggle, identity enrichment, investigation query.

---

# PHASE 3 — YUNET FACE DETECTION MODULE

**Model:** copy `yunet.onnx` (232,589 bytes) from `/var/folders/gj/xmn351s52wg2crpnx5wvpz080000gp/T/opencode/trinetra_audit/yunet.onnx` → `Trinetra/models/yunet.onnx` (planner-verified present today; the ONLY face detector that matters — MTCNN stays dormant fallback).

**Backend — NEW `backend/vision/face.py` (module, not an AnalyticModule — same rationale as reid: needs pixels):**
- `class YuNetFaceDetector`: lazy `cv2.FaceDetectorYN.create(str(path), "", (320,320) size_hint, score_threshold=0.6, nms_threshold=0.3)` guarded by file-existence + honest `available` property (pattern: embedder.py:107-127; verified API exists in venv cv2 5.0.0 — planner-checked `hasattr(cv2,'FaceDetectorYN')` today).
- **Selective scheduling (§44):** run ONLY on event-triggers, never per-frame — trigger when (a) a PERSON_DETECTED/ZONE_ENTRY/REID-confirmed draft carries a person track with bbox ≥ ~80px tall (audit §14 rule: flagged-for-evidence / zone-entering / reid-enrollment), (b) at most once per track per 5s (cooldown dict, same pattern as engine cooldown). 2.8ms/frame measured means even generous triggering is noise.
- Output: `[{bbox, conf, landmarks5}]` + optional face crop path in metadata; **NO recognition, NO identity DB, NO face gallery** (master prompt ban).

**Events + overlay:**
- `FACE_DETECTED` — LOW severity, once per (track, face) via the standard cooldown map (engine.py:190-201), metadata: `{track_id, face_conf, landmarks_count, bbox, trigger_reason}` + evidence snapshot rides the existing shared-JPEG (severity LOW < MEDIUM snapshot floor — if snapshot wanted, either keep LOW (no snapshot, honest) or raise via a `snapshot` hint; **recommendation: keep LOW, rely on the frame** — the operator already sees the face burned into the MJPEG overlay).
- **Overlay:** extend `backend/vision/annotation.py` `annotate()` ADDITIVELY with optional `faces=None` kwarg (list of face dicts) → thin cyan box + `FACE 0.xx` label above the person box; NEVER mutates existing draws; default None = byte-identical surface (same contract as layers/zones/trajectories). **Careful: this file has an uncommitted hardening diff — extend around it, do not revert it.** Session: pass faces when face results exist and `layers["faces"]` (extend the layers dict with `"faces": False` default — OFF default keeps stream clean; toggle in UI).
- Status: extend `_model_status()` main.py:73-82 → `models.face = {file, present, size_mb}` + health stays honest.

**Tests:** `tests/test_face.py` — module unit with a synthetic image (cv2 rectangle-drawn "face-like" pattern is NOT a real face — use the model on `crowd-abnormal-behavior-detection-main/assets/intrusion.mp4` frame extraction as the fixture: audit measured 334 detections/60 frames there; commit 1-2 extracted frames as small test assets under tests/assets/, planner sanctions); trigger-gating unit (event-only, cooldown respected, no per-frame inference — count detect() calls via monkeypatch); annotate-faces unit; endpoint/honest-unavailable test (delete-model dir simulation → available False, sessions unaffected, health reports present:False).
**Acceptance:** running intrusion.mp4 with faces ON: FACE_DETECTED events appear ONLY after person triggers (not per frame), faces burned into MJPEG when toggled; FPS impact <3% (measure); honest toggle label "Face Detection" enabled-only-when-model-present.
**Test mapping:** §52 face toggle + FACE_DETECTED event + no-recognition honesty.

---

# PHASE 4 — CROWD / BEHAVIOR / NIGHT ANALYTICS (AGPL-safe reimplementations)

**License rule:** crowd-abnormal-behavior-detection-main is AGPL-3.0 (LICENSE file). TRINETRA implements the ALGORITHMS independently from the published math (standard geometry/statistics) with its own constants and code. NO code copy — no imports, no file copies, no line-level translation. Cite the papers/concepts, not the code. (audit §29.5; inventory §2.)

**Files:** NEW `backend/analytics/behavior.py` (running + abnormal-movement + loitering), NEW `backend/analytics/crowd.py` (zone count/density), extend `backend/analytics/__init__.py` exports; session chain appends modules (session.py:108 `self._analytics = [FenceAnalytic(...), ...]`).

**Module contract (AnalyticModule — analytics/base.py:53-79):** `process(ctx, view) -> [EventDraft]`, `reset(session_id)`; reads ONLY ctx + TrackView (has everything: positions (x,y,tick) deque-60 tracks.py:51-67, frames_seen, class_name, active); drafts commit through the existing engine.

## 4.1 CrowdAnalytic (per-zone person count + density) — `crowd.py`
- Per tick: for each active zone (from ZoneStore via the fence's zone view — reuse FenceAnalytic.zone_person_counts() fence.py:281 which EXISTS), compute: `person_count` (authoritative tracker, foot-point PIP — already done), `density = count / polygon_area` (normalized-coords shoelace area — reuse backend/analytics/geometry.py), and emit **CROWD_DENSITY** when density crosses a configurable threshold ≥2 consecutive ticks (state-transition emit, not per-frame; cooldown backstop engine.py:190-201). Severity: MEDIUM when above `crowd.density_high` (=0.15 persons/unit² default), LOW otherwise on entry.
- **Zone occupancy is ALREADY in status_payload (`zone_person_counts` session.py:425) — the module only adds the EVENT layer on top. No new counting path.**

## 4.2 RunningAnalytic (SUSPECTED_RUNNING) — `behavior.py`
Reimplemented explainable score (source concepts: running_detection.py:221-266; constants :74-99 — our own values):
- Per person track, over the last W=10 position samples: `speed_score = min(1, avg_px_per_s / 80)`, `displacement_score = min(1, total_displacement_px / 150)`, `direction_score = |mean(sin θ)|+|mean(cos θ)| resultant length` (circular-mean stability, computed over moves >2px). `confidence = 0.5·speed + 0.3·displacement + 0.2·direction` (weights are the published explainable scheme — standard evidence fusion; our code our own).
- Gate: track alive ≥5 ticks (skip newborn flicker); trigger ≥0.50 for ≥3 consecutive ticks (hysteresis up/down); event `SUSPECTED_RUNNING` MEDIUM (+HIGH if inside RESTRICTED zone — metadata carries zone context, engine ladder stays as-is via zone_type metadata key) once per track per cooldown; confidence = the score; metadata includes the full breakdown `{speed_px_s, displacement_px, direction_score, weights}` — explainable by construction.
- **Per-camera calibration honesty:** thresholds are px-based → perspective-dependent. Config `[behavior] running = {speed_norm_px_s=80, displ_norm_px=150, trigger=0.50, window=10, min_ticks=5}` in default.toml; UI label "SUSPECTED — velocity heuristic" NEVER "action recognition".

## 4.3 AbnormalMovementAnalytic (SUSPECTED_ABNORMAL_MOVEMENT)
- Deviation-from-baseline: per-camera rolling baseline of median person speed over last 60s (EWMA); a track with speed > max(2×baseline, 1.5×running-speed-gate) AND direction_score <0.3 (erratic) for ≥3 ticks → event, LOW severity, honest metadata `{baseline_px_s, observed_px_s, direction_score}`. If baseline has <5 person-observations the module is a NO-OP (under-calibrated — honest).

## 4.4 NightMovement (NIGHT_MOVEMENT)
- ctx.is_night already computed per tick (session.py:63,301 luminance<40). State: person-track active AND `ctx.is_night` for ≥5 consecutive ticks → `NIGHT_MOVEMENT` LOW once per track (cooldown; metadata `{mean_luminance, ticks_in_dark}`). Severity rationale text: "tracked movement in darkness". No image enhancement claim. (Optional CLAHE pre-pass from sentinel concept = OUT unless quality demands — keep the analytic read-only.)

## 4.5 LoiteringAnalytic (LOITERING)
- Dwell: person track continuously confirmed for ≥ `behavior.loiter_min_s` (default 20s wall) AND spatial radius (std of positions) < `behavior.loiter_radius_px` (default 80px) → `LOITERING` LOW (MEDIUM inside a zone — zone context via foot-point vs zones, reuse FenceAnalytic's zone query pattern fence.py:95). Once per track; hysteresis release when radius or activity resumes.

**Config:** one new `[behavior]` + `[crowd]` block in default.toml + parsed in config.py `_build` (mirrors FENCE pattern).
**Tests:** `tests/test_behavior.py` + `tests/test_crowd.py` — synthetic TrackStore with scripted positions (fast straight line → RUNNING fires; slow arc → not; jumpy erratic → ABNORMAL; stationary 25s → LOITERING; is_night ctx → NIGHT; density threshold → CROWD_DENSITY); all with real geometry math (no mocking cv2); AGPL-clean (no imports from the crowd repo anywhere — grep-gate test optional).
**Real-footage validation (executor runs, logs honestly):** `crowd.../assets/running.mp4` (632×480@30) — expect ≥1 SUSPECTED_RUNNING on the runner; `intrusion.mp4` — expect ZONE_ENTRY (existing) + face (Phase 3) co-existence; record actual counts + FPS in `docs/BEHAVIOR_CALIBRATION.md` (new, executor fills with REAL numbers, including any misses).
**Acceptance:** every new event carries an explainable score breakdown; heuristics labeled SUSPECTED everywhere (UI type-label map + EventSummary template); suite green ≥207+all-new; FPS with all behavior modules ON ≥85% of Phase-1 baseline (measure).
**Test mapping:** §52 crowd/running/abnormal/night/loitering toggles + honest labels.

---

# PHASE 5 — DETERMINISTIC EVENT SUMMARY / AGENTIC LAYER + INVESTIGATION ENRICHMENT

## 5.1 Backend session summary (structured, deterministic)
- **File:** NEW `backend/services/summary.py` — `build_session_summary(session) -> dict` derived ONLY from: `status_payload()` fields, the session's committed EventRows (DAO read by session_id — dao.events read path exists for /api/events), and TrackStore aggregates flushed at finalize (session.py:369-378 rows already persist class/first/last/frames/conf).
- Shape (master prompt §35): `{session_id, source_id, duration_s, frames, people_detected, vehicles_detected, unique_tracks, events_by_severity, events_by_type, zones_breached, max_concurrent_people, first_event_ts, last_event_ts, notes[]}` — every number traces to a queryable row; `notes` = one deterministic clause per notable state ("ZONE_ENTRY HIGH committed in restricted zone 'X' at 00:12.4"). NO narrative invention, NO LLM. If MICHAEL later supplies an LLM, it may verbalize this dict ONLY (m8 Hermes rule, M8_CROSS_CAMERA_CONTRACT.md:143-148).
- **Endpoint:** `GET /api/sessions/{id}/summary` (inline in sources.py sessions_router region :159-200 — additive) — 404 clean for unknown id; null summary with honest message if the session has no flushed stats yet.

## 5.2 Frontend "agentic" summary surface
- **Files:** extend `frontend/src/components/EventSummary.tsx` with a per-SESSION summary block on Dashboard (renders the current session's summary when active, latest session's after stop); Investigation page gains the summary panel for any picked session.
- Empty/absent fields render as absent (never 0-when-unknown).

## 5.3 Investigation enrichment (trajectory view + related events)
- **Backend:** `GET /api/sessions/{id}/tracks` EXISTS (sources.py:181-200). ADD per-track trajectory when the session is COMPLETE: positions are NOT persisted per-sample today (only aggregates flush, session.py:369-378). **Decision (honest, no schema explosion):** during the finalize flush, ALSO persist a compact trajectory JSON per track — `positions` downsampled to ≤60 points — into a new `tracks.trajectory` TEXT column via ONE additive migration (backend/db/migrations.py pattern: migration 3 `ALTER TABLE tracks ADD COLUMN trajectory TEXT` — nullable, old rows NULL). Session loop change is zero (flush site only, session.py:372-376). DAO: extend flush_tracks with optional trajectory arg. (This is the single sanctioned DB change in the plan; additive + nullable.)
- **Frontend Investigation (`Investigation.tsx:100-135` tracks table):** add a per-track "view path" mini canvas — draws the persisted normalized trajectory polyline; related-events column: events filtered by track_id (client-side over loaded /api/events pages; honest "related events (loaded window)" label per C8 advisory).
- EventDetail: trajectory chips if the event's track has a persisted path (same session).

**Tests:** `tests/test_summary.py` — deterministic summary from a scripted session (assert every field against known inputs); migration-3 round-trip (old DB upgrades, NULL trajectories render absent); endpoint 404/empty; **suite green ≥207+all-new.**
**Test mapping:** §52 session summary + investigation trajectory + related events.

---

# PHASE 6 — ANPR (THE ONLY NEW-MODEL CAPABILITY)

**Status honesty:** nothing exists locally (audit §16, grep-verified zero plate/OCR pipelines; planner re-verified no LPD/OCR assets). ANPR = EXPERIMENTAL until real Indian-plate footage passes.

## 6.1 Plate detection model — SINGLE named recommendation
- **Recommendation:** fine-tune **yolov8n (the repo's own detector family, AGPL-consistent, no new dep)** on a public Indian-plate detection dataset — e.g. the open "Indian License Plates" Roboflow dataset (or Kaggle Indian-plate LPD), single class `plate`, ~2-4k images, 30-min fine-tune on the M4 (or Colab if dataset download is heavy). Result: `Trinetra/models/yolov8n_plate.pt` (~6MB), loaded by the SAME DetectorTracker machinery (a second DetectorTracker instance, lazy, gated on file presence — §44).
- **Rejected alternatives:** standalone LPD ONNX (adds a 2nd model family + dnn wiring for marginal gain; our tracker integration is already ultralytics-native); larger read-plate end-to-end models (black-box, unverifiable, dep risk).
- **If NO model can be acquired/trained before the deadline:** Phase 6 ships `PLATE_DETECTED`-ONLY via heuristic: vehicle-class tracks with a small bright/yellow rectangular region beneath (color+geometry crop heuristic, honestly labeled HEURISTIC PLATE REGION — no OCR), and the toggle reads "ANPR — plate detection only (no read)". NEVER fabricate.

## 6.2 OCR — PaddleOCR CPU (the one new-dep exception, MICHAEL-gated)
- **Recommendation:** PaddleOCR (PP-OCRv4 mobile det+rec, CPU, ARM wheel — VERIFY current Apache-2.0 runtime license + macOS ARM wheel availability before pip-install; audit §16 recommends evaluate-first). FALLBACK if wheel/license fails: EasyOCR (torch-based, already-compatible stack, heavier). LAST resort: none (ship detection-only).
- **Scheduling:** OCR ONLY when the plate-region crop ≥ ~64px wide (size-gating concept, audit §16). Trigger: on VEHICLE_DETECTED (once per track per cooldown) run plate-detect on the vehicle bbox; if a plate box ≥64px, crop → OCR.

## 6.3 Event semantics (three-state honesty)
- `ANPR_PLATE_DETECTED` — LOW — plate box found, OCR not run/failed. Metadata: `{vehicle_class, plate_bbox, crop_w_px, track_id}`.
- `ANPR_READ` — MEDIUM — OCR confidence ≥ `anpr.ocr_conf_min` (default 0.80) AND passes Indian-format regex: old `XX01XX1234`-ish `[A-Z]{2}\d{1,2}[A-Z]{0,3}\d{4}` + BH-series `^\d{4}BH\d{4}[A-Z]$` validation (new `backend/analytics/anpr.py` validators; regex config in default.toml). Metadata adds `{raw_text, ocr_conf, format:"IND_old"|"IND_BH"|"UNMATCHED"}`.
- `OCR_UNCERTAIN` — LOW — OCR ran but below conf or failed format validation. Metadata: `{raw_text?, ocr_conf, reason}`. **NEVER coerce; NEVER fabricate plates; uncertain stays uncertain.**
- Snapshot: shared-JPEG rule (the crop + full frame already annotated).

## 6.4 Test assets + honest gating
- **BLOCKING GAP:** obtain 5-10 real Indian plate clips/images BEFORE claiming ANPR works (audit §30). Until then the UI toggle reads "ANPR — EXPERIMENTAL (not validated on Indian plates)" and any demo of it is a calibration exercise, not a claim.
- **Tests:** `tests/test_anpr.py` — validator unit (all Indian formats + junk rejection); three-state transitions from scripted detector/OCR stubs (monkeypatch OCR outputs, assert the STATE machine, never the model); size-gating (crop <64px → no OCR call); honest-unavailable (no plate model → module no-op, health reports present:False).
**Test mapping:** §52 ANPR toggle with PLATE_DETECTED vs PLATE_READ distinction + OCR_UNCERTAIN handling.

---

# PHASE 7 — RTSP INGESTION + CAMERA MANAGEMENT / MAP POLISH

## 7.1 RtspSource (transport already verified: MediaMTX loopback 19.7fps, 1.6s TTFF — audit §21)
- **Files:** NEW `backend/sources/rtsp.py` implementing the VideoSource protocol (open/read/reopen/is_live + state enum — mirror webcam.py's shape); register in `backend/sources/__init__.py` factory + `make_source` (session.py:485-499 gains `type=="rtsp"` with `uri` field; StartRequest main.py:67-70 gains `uri: str = ""`).
- **Design:** `cv2.VideoCapture(uri, cv2.CAP_FFMPEG)` + `OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp` (TCP preferred); read-failure → reuse the webcam backoff ladder verbatim (session.py:237-262 — SOURCE_LOST → backoff 1→2→4→8s → reopen → SOURCE_RECONNECTED; it already dispatches on `is_live` so RtspSource just sets `is_live=True`); watchdog: first-frame timeout 10s → honest error. No ring buffer needed at MVP — the slot already decouples.
- **Test rig (not shipped):** `scripts/rtsp_test.py` — mediamtx (brew, installed) + ffmpeg publish a test video → RtspSource reads; asserts fps + reconnect after killing mediamtx. **Auth: UNTESTED (no camera with auth) — label honest.**
- **UI:** Live View source row gains "RTSP STREAM" input (uri field) with honest "network camera — transport verified, real-camera network untested" note (keep/extend the existing honest RTSP panel Sources.tsx:69-75); camera registry type "rtsp".
- **Tests:** `tests/test_rtsp_source.py` — unit with a fake URI (assert clean SourceError, backoff behavior via monkeypatched VideoCapture); the LIVE rig check is a script, not CI (honesty: not all machines have mediamtx).

## 7.2 Camera management polish
- `frontend/src/pages/Sources.tsx` → full table: camera_id, name, source_type, status (LIVE only when active session matches — backend-enforced map.py:95-96 pattern), lat/lng (— when NULL), location label. Small additions only; the registry data already flows from `/api/map/cameras` (map.py:81-108) + `/api/sources`.

## 7.3 Map polish
- Marker click → camera info card + selected-center (Geography.tsx/GeoMap.tsx selection already flows through store.selectCamera — extend the panel); light schematic verified (landed in P0/T0.3); satellite→roadmap→schematic chain untouched; maps.googleapis.com-blocked drill in the E2E (verify analytics unaffected).

**Acceptance:** rtsp://localhost test stream runs end-to-end with events + MJPEG; killing the server mid-stream fires SOURCE_LOST then RECONNECTED on restart; camera/map pages show only real state.
**Test mapping:** §52 RTSP source + camera registry + map.

---

# PHASE 8 — FULL E2E DEMO + FINAL REPORT

## 8.1 The 53-step flow (§53 mapping — executor converts the V3 §5 25-step checklist + all phase capabilities into ONE browser-scripted run)
- Extend `scripts/trinetra_e2e.py` (Phase 0 file) into the full demo drill: boot → health → light Command Center (4 cards zero-when-zero) → Live View → SCAN CAMERAS (honest result) → upload running_clip → START → MJPEG boxes/IDs/FPS → each toggle visibly changes the stream → create RESTRICTED zone via UI → ZONE_ENTRY fires (confirm + HIGH + evidence shows the fence) → FACE_DETECTED (Phase 3) → Re-ID identity matched + enriched alert (Phase 2) → SUSPECTED_RUNNING (Phase 4) on crowd running.mp4 session → NIGHT if a night clip exists (record honestly if absent) → EventDetail chain Event→Camera→Zone(+Geo)→Evidence→Identity→Trajectory → Event Log table row → EventSummary sentence diff = zero invention → session summary panel numbers == API → STOP → hard-reload persistence → Analytics runtime + charts → Map marker/sector select → Cameras registry LIVE-then-idle → RTSP local loop (Phase 7 rig, if mediamtx available) → restart-uvicorn persistence drill.
- Every step logs honest PASS/FAIL + observed value into `docs/TRINETRA_E2E_DEMO_LOG.md`.

## 8.2 TRINETRA_FINAL_INTEGRATION_REPORT.md skeleton (executor fills)
- **Create `docs/TRINETRA_FINAL_INTEGRATION_REPORT.md`** with sections: Verified state per phase (each claim = test name + measured number); Honesty ledger (per-capability label table: VERIFIED/HEURISTIC/EXPERIMENTAL/DISABLED + why); Benchmark table (FPS per configuration, this machine, this run); §52 checklist mapping (item → test/step); Open gaps (ANPR Indian-plate validation, 2-camera reid, night footage, RTSP auth — carried forward honestly); Reproduction commands (uvicorn line, pytest, build, e2e scripts).

**Final gates (every phase, enforced):** `pytest -q` full suite green ≥207 + all new files, 4 skips unchanged · `npx tsc --noEmit` + `npm run build` clean · `scripts/m7_e2e.py` 24/24 regression · no fake data (grep-gate: no Math.random/lorem/sample in src; spot-check every UI number traces to an API field) · all changes left UNCOMMITTED for MICHAEL.

---

## RISK REGISTER (binding)

| # | Risk | Mitigation |
|---|---|---|
| R1 | **AGPL contamination** (crowd-repo) | Independent implementation only; no code/file/line copies from the repo; concepts cited to published math with our constants; grep-gate test that backend never imports/references it |
| R2 | No-fake-data | Every UI number traces to an API field; heuristic labels SUSPECTED; OCR_UNCERTAIN; "possible match" reid wording; EventSummary template omits-absent-fields |
| R3 | Shared-JPEG rule | Toggles affect evidence (documented A1 trade-off; defaults all-ON; second render pass REJECTED — re-encode cost) |
| R4 | Suite-green gate | ≥207 + new, 4 skips; NO existing test modified (if an annotate test seems to pin behavior, escalate to MICHAEL before touching it — handoff §6 rule) |
| R5 | tsc gate | 0 errors + vite build clean after every frontend task |
| R6 | Webcam honesty | No webcam on this machine → honest "no camera available"; file-source demo; NEVER fake |
| R7 | annotation.py uncommitted diff | Executor must not revert/commit the 2 hardening hunks (map.py +4, annotation.py +2); extend around them |
| R8 | reid.ts size/proxy | Not shipped; TorchScriptEmbedder retained class-only; MICHAEL may overrule (OPEN QUESTION §1 in inventory) |
| R9 | One-active-session | All camera-status surfaces derive from active_session; reid registers the running source as the single camera |
| R10 | Model-loading discipline (§44) | Every new model lazy + availability-gated (yunet, plate, reid onnx); health surfaces present/absent; missing model = honest no-op, never boot failure |
| R11 | MPS/CPU fallback | Existing device policy (config [device] auto) covers YOLO; all new modules are CPU-cheap (measured) |
| R12 | Commits out of scope | Executor leaves the tree UNCOMMITTED; final report lists every changed file for MICHAEL's review |

## FILE-MANIFEST (all changes, by phase — for MICHAEL's review pass)

| Phase | New files | Modified files |
|---|---|---|
| 0 | `scripts/trinetra_e2e.py`, `docs/PHASE0_E2E_LOG.md` | (none expected; fixes only if a real break is proven) |
| 1 | `tests/test_layers.py`, `frontend/src/components/EventSummary.tsx` | `backend/services/session.py`, `backend/main.py` (inline routes), `config/default.toml` (no — Phase 1 needs none), frontend: Cameras.tsx, Analytics.tsx, Dashboard.tsx, SourcePicker.tsx (labels), LiveFeed.tsx (remove client zone draw), api.ts, types.ts |
| 2 | `backend/reid/` (11 modules ported), `backend/api/reid.py` (or inline), `tests/test_m8_reid.py` (ported), `tests/test_reid_port.py`, `scripts/m8_reid_bench.py` (ported), `models/fast-reid_mobilenetv2.onnx` (copied) | `backend/core/config.py` (+ReIdCfg), `config/default.toml` (+[reid]), `backend/core/errors.py` (ApiState reid slot), `backend/main.py` (lifespan init + include line + health), `backend/services/session.py` (loop wiring), `frontend/src/components/EventDetail.tsx`, `frontend/src/pages/Investigation.tsx`, `frontend/src/pages/Cameras.tsx` (toggle), `frontend/src/types.ts`, `frontend/src/api.ts`, `.gitignore` (if any model path needs it) |
| 3 | `backend/vision/face.py`, `tests/test_face.py`, `models/yunet.onnx` (copied), `tests/assets/face_frame*.jpg` | `backend/vision/annotation.py` (+faces kwarg, AROUND the uncommitted diff), `backend/services/session.py` (trigger wiring + layers["faces"]), `backend/main.py` (health models.face), `frontend/src/pages/Cameras.tsx` (toggle) |
| 4 | `backend/analytics/behavior.py`, `backend/analytics/crowd.py`, `tests/test_behavior.py`, `tests/test_crowd.py`, `docs/BEHAVIOR_CALIBRATION.md` | `backend/analytics/__init__.py`, `backend/services/session.py` (chain append), `backend/core/config.py` + `config/default.toml` ([behavior],[crowd]), `frontend/src/pages/Cameras.tsx` (toggles), EventSummary type labels |
| 5 | `backend/services/summary.py`, `tests/test_summary.py` | `backend/db/migrations.py` (migration 3, additive), `backend/db/dao.py` (flush_tracks trajectory), `backend/services/session.py` (flush trajectory), `backend/api/sources.py` (+GET summary), `frontend/src/components/EventSummary.tsx`, `frontend/src/pages/Investigation.tsx`, `frontend/src/pages/Dashboard.tsx` |
| 6 | `backend/analytics/anpr.py`, `tests/test_anpr.py`, (model acquisition: `models/yolov8n_plate.pt` — MICHAEL-gated) | `backend/core/config.py` + `config/default.toml` ([anpr]), `backend/services/session.py` (vehicle-trigger wiring), `backend/main.py` (health), `frontend/src/pages/Cameras.tsx` (toggle) |
| 7 | `backend/sources/rtsp.py`, `tests/test_rtsp_source.py`, `scripts/rtsp_test.py` | `backend/sources/__init__.py`, `backend/services/session.py` (make_source), `backend/main.py` (StartRequest.uri), `frontend/src/components/SourcePicker.tsx` (RTSP input), `frontend/src/pages/Sources.tsx`, `frontend/src/pages/Geography.tsx` + `GeoMap.tsx` (polish) |
| 8 | `docs/TRINETRA_E2E_DEMO_LOG.md`, `docs/TRINETRA_FINAL_INTEGRATION_REPORT.md` | `scripts/trinetra_e2e.py` (full-flow extension) |
