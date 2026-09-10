# TRINETRA — FULL ARCHITECTURE HANDOFF (V3.5 Capability Build)

**Author:** ARCHITECT · **Date:** 2026-09-10 · **Executor:** EXECUTOR1 (the ONLY implementer)
**Inputs validated:** TRINETRA_RESOURCE_INVENTORY.md + TRINETRA_FULL_IMPLEMENTATION_PLAN.md (PLANNER, 2026-09-10), TRINETRA_ARCHITECTURE_HANDOFF.md (V3), TRINETRA_IMPLEMENTATION_PLAN.md (V3), full code-seam verification (every claim below re-checked against the tree with file:line, suite RE-RUN).
**Base:** HEAD `3d0c7e2` + uncommitted work (see §2.1 — the tree MOVED after MICHAEL's fact-recording; re-baseline first).
**Target machine:** MacBook Air M4 16GB. Governing rules: no fake data, no feature theater, honest labels, lazy model loads (§44), one active session (frozen §17), ByteTrack sole tracker, shared-JPEG (A1).

---

## 1. VERDICT: **APPROVED** — with binding corrections in §2–§11. EXECUTOR1 may start at Phase 1 immediately; no further architecture input required.

The PLANNER's plan is sound: model decisions verified (fast-reid ONNX loads + infers via cv2.dnn in the main venv — I re-ran the load myself: `[32,3,128,256]→[32,1280]`, md5 `77a97e84aac88bdb3eeaa17dd6c57180` matches; YuNet present at the temp path, 232,589 bytes, `cv2.FaceDetectorYN` exists in cv2 5.0.0), the m8 package structure confirmed (11 modules, 23 tests, `analytics/base.py` byte-identical to main tree — diff-verified; `engine.py` differs only by M6 additions), phase sequencing correct. The corrections below are staleness + one design error (crowd density units) + one plan gap (Event Log page) — none block the start.

---

## 2. TREE-TRUTH CORRECTIONS to the plan (verified 2026-09-10, ~02:00–03:00)

### 2.1 THE TREE MOVED AFTER MICHAEL'S FACT-RECORDING — re-baseline before anything

MICHAEL's ground truth said "V3 P1 FRONTEND is NOT landed." That was true when he recorded it, but **the frontend P1 surfaces have landed (uncommitted) in the hours since** — I watched a file appear *during* my own inspection. Verified present NOW:

| Plan claim | Reality (file:line) | Consequence |
|---|---|---|
| "NO toggle UI" | `frontend/src/components/LayerToggles.tsx` EXISTS (untracked) and is MOUNTED in `Cameras.tsx:8,43` — full 5-toggle bar, real POSTs, disabled-with-reason when idle | Phase 1.3 toggle work = DONE |
| "NO EventSummary" | `frontend/src/components/EventSummary.tsx` EXISTS (untracked), MOUNTED at `Dashboard.tsx:6,83` — deterministic template, C6 zone-name resolution, absent-clause omission — implements plan §1.4 fully | Phase 1.4 = DONE |
| "NO per-class stat strips" | `Cameras.tsx:22-32` Session Stats strip (People/Vehicles/Active/Frames/FPS/Device/Uptime from `status_payload`); `Dashboard.tsx:20-24` cards read `s?.people_detected`/`vehicles_detected` (landed diff) | DONE |
| Phase 1.2: "REMOVE client zone canvas draw in LiveFeed.tsx:21-73" | ALREADY REMOVED — current `LiveFeed.tsx:1-5` documents the C2 removal; no canvas overlay exists | Phase 1.2 frontend half = DONE |
| "api.ts has sessionLayersGet/Post but nothing else" | Also true: `api.ts:36-46` both methods land; `types.ts:35-38` the 4 per-class fields; `types.ts:60-61` `severity_reason` for EventSummary | DONE |

**BINDING:** Phase 1 execution starts with a re-baseline: `git status`, run the gates (§11), and reconcile against this table. Do not re-do landed work. STILL MISSING from Phase 1: `Analytics.tsx` runtime panel (current file has charts only — no Runtime/Fence/Trajectory Info panel, no shared toggle mount), the Event Log page (§2.4), Alerts filters (§2.4), SourcePicker label pass. If further files appear mid-run, same rule: verify, don't duplicate.

### 2.2 Suite gate is STALE: 214 passed, not ≥207

I ran the full suite: **218 collected / 214 passed / 4 skipped / 2 warnings** (85.75s, includes uncommitted V3 P1 + test_layers.py). The plan's "≥207" gate (and the inventory's "207 collected") is stale — `test_layers.py` + growth since. **Gate = green at ≥ current collected count (re-check at each phase land; today 218) + all new tests, 4 skips unchanged, 2 warnings unchanged, zero existing tests deleted/weakened.** Frontend gate: `npx tsc --noEmit` 0 errors (verified clean NOW — it transiently failed at 02:20 because types.ts was mid-write; if you see errors, someone is writing, wait and re-run) + `npm run build` clean.

### 2.3 Phase 0 is ABSORBED — no standalone phase

Per MICHAEL (ground truth, verified: `scripts/phase0_upload_chain.py` exists, 20+ live checks, `data/trinetra.db` holds PERSON_DETECTED 271 / ZONE_ENTRY 41 / SESSION_COMPLETED 25 across runs, uploads/ chain proven): **the upload chain is NOT broken. Do not create `scripts/trinetra_e2e.py` now, do not fix anything.** The Playwright-in-real-Chromium confirmation folds into Phase 8's demo drill. Phase 0's only artifact: keep `phase0_upload_chain.py` green as a regression (run it after Phases 1–7, before Phase 8).

### 2.4 PLAN GAP — Event Log page + Alerts filters exist in NO phase

MICHAEL's ground truth lists "NO EventLog page" among the missing surfaces; V3 P2 specced it (T2.1 alerts filters, T2.2 Event Log table) and the V3 plan's §5 demo step 18 depends on it — but the FULL plan dropped both. **BINDING ADDITION to Phase 1** (§4 below): land `frontend/src/pages/EventLog.tsx` (nav "Event Log", 8th page: Event ID truncated-uuid copyable, Time, Source, Type, Severity chip, Track ID, Metadata key:value chips from real JSON; client-side substring search over loaded pages; "Load older 50" keyset pagination via existing `api.events`; row click selects for EventDetail) + Alerts filters on `Events.tsx` (type dropdown of real types present in loaded data, source dropdown of real `source_id`s — both client-side, honest). Zero backend change (events API verified sufficient, `events.py:43-71` keyset pair-cursor).

### 2.5 Factual line-ref corrections (minor, executor uses these)

| Plan says | Correct ref (verified) |
|---|---|
| session loop wiring region ":304-319" for reid | analytics chain `session.py:358-373`; `_annotate` call `:376`. Wire reid/face AFTER `:373`, BEFORE `:376` |
| `status_payload` :414-428 / `_stats_payload` :402-410 | `session.py:470-503` / `:456-466` (already landed — read-only now) |
| `annotate` signature ":98-106" ✓, layer parse ":124-130" ✓, traj ":81-95" ✓ | confirmed current |
| config exports "7 groups at :140" | **8 groups** (`config.py:140`: DEVICE, VISION, TRACKING, FENCE, EVENTS, STREAM, PATHS, SOURCES) — append REID et al., keep all |
| `_model_status` main.py:73-82 ✓ | confirmed |
| webcam backoff ladder "session.py:237-262" | `session.py:291-316` |
| make_source "session.py:485-499" | `session.py:560-574` |
| zones accessor "zones.py:207-223" ✓ | confirmed (`ZoneStore.zones(source_id, active_only)`) |
| fence zone counts "fence.py:281" ✓ | confirmed (`zone_person_counts()`, `fence.py:281-292`) |
| m8 `config.py:82-101` ReIdCfg, `:141-150` export ✓ | confirmed; m8 `[reid]` toml `:39-54` ✓ |
| engine "generic INFO branch :235-237" ✓ | confirmed (`engine.py:235-238` else → INFO) — BUT see §2.6 |
| integration.py:139-175/257-287/291-306 ✓ | confirmed `process_tick`/`enrich_drafts`/`person_summary`+`all_persons` (:295-306) |

### 2.6 DESIGN ERROR — Phase 4's "engine ladder stays as-is" claim is FALSE

`EventEngine._severity_for` (`engine.py:204-238`) computes severity per TYPE; unknown types fall to the else branch → **INFO**. SUSPECTED_RUNNING wants MEDIUM, FACE_DETECTED wants LOW, CROWD_DENSITY wants MEDIUM/HIGH, ANPR_READ wants MEDIUM — none of these types exist in the ladder. The plan's "zone_type metadata key" trick only works for ZONE_ENTRY (the ladder reads `zone_type` in the ZONE_ENTRY branch, `engine.py:211-220`). **BINDING FIX:** executor1 extends `_severity_for` with an ADDITIVE lookup inserted AFTER the existing if/elif chain, BEFORE the system/unknown else:

```python
# engine.py — additive (Phases 3/4/6 append their types here)
_NEW_TYPE_BASE = {
    # severity per type; night raises +1 (existing pattern); a RESTRICTED
    # zone_type in metadata raises +1 (cap HIGH) — same modifier semantics
    # as the ZONE_ENTRY branch. Values are policy, owned by the engine.
}
# elif d.type in _NEW_TYPE_BASE:
#     sev = _NEW_TYPE_BASE[d.type]
#     reasons.append(<per-type reason>)
#     if is_night: sev = _raise(sev, 1) ...
#     if ztype == "RESTRICTED": sev = _raise(sev, 1) ...
```

Rules: existing branches (`engine.py:211-234`) byte-untouched; system types still INFO via the else; `PERSON_IDENTITY_MATCHED`/`PERSON_CAMERA_TRANSITION` = INFO (add them to the dict anyway for explicitness). Cooldown backstop (`engine.py:190-201`) applies to all new types automatically. `engine.py` is NOT executor2-owned (§4 routing) — this edit is executor1-sanctioned, additive-only, no existing test touched.

### 2.7 DESIGN ERROR — CROWD_DENSITY "0.15 persons/unit²" is unit-confused

Zone geometry is NORMALIZED frame coordinates (§12): a full-frame polygon has area 1.0, a 10%-of-frame zone area 0.1. `density = count/area` at threshold 0.15 fires on ONE person in any zone smaller than 6.6× the frame — i.e., always. **BINDING FIX:** severity bands on per-zone PERSON COUNT (authoritative, perspective-independent, explainable); density (count ÷ normalized polygon area) rides in metadata as informational only. Config: `[crowd] medium_count=4, high_count=8, sustained_ticks=2` (values chosen by us — provenance comment in config). Event CROWD_DENSITY, MEDIUM base / HIGH at high_count, sustained ≥2 consecutive ticks (state-transition emit; cooldown backstop still applies). Count source: §7 (FenceAnalytic — ONE counting path).

### 2.8 ANPR corrections (detail in §8)

Detection recommendation VALIDATED. OCR amended: PP-OCRv4 mobile ONNX (det+rec) via **cv2.dnn** as PRIMARY — zero new deps, honoring R10's "avoid" default; PaddleOCR pip = MICHAEL-gated FALLBACK only. BH-series regex is WRONG in the plan (`^\d{4}BH\d{4}[A-Z]$` — 4 leading digits): real BH format is 2-digit code + "BH" + 4 digits + 1–2 letters → `^\d{2}BH\d{4}[A-Z]{1,2}$` (e.g. 32BH1234AB). Old format `^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}$` acceptable. Both live in config (never hardcoded in the validator), format field honestly reports `IND_old|IND_BH|UNMATCHED`.

### 2.9 RTSP detail the plan missed — source TYPE registration

`session.py:183` derives the DB source type from the id string: `src_type = "webcam" if "webcam" in self.source_id else "file"` — an RtspSource would be registered as "file". The schema is already ready (`migrations.py:18` CHECK includes `'rtsp'`). **BINDING:** add a `type_name` class attribute to sources (`webcam.py` → `"webcam"`, `file.py` → `"file"`, new `rtsp.py` → `"rtsp"`) and change `session.py:183` to `src_type = getattr(self._source, "type_name", "file")`. Additive; existing behavior identical (webcam/file get the attr with same values).

### 2.10 Stale/misc

- m8 bench port: DROP the InceptionV3/TorchScript EXPORT machinery (reid.ts rejected per R2). Ported bench = load the committed onnx via `OpenCVDnnEmbedder`, measure single+batch latency, then FPS reid-ON vs reid-OFF on `tests/assets/running_clip.mp4`.
- `sources` table already accepts type `rtsp` — NO migration needed for Phase 7.
- `api/sources.py:181-200` `GET /api/sessions/{id}/tracks` verified — R8's trajectory source exists; Phase 5 only adds the trajectory column data to it.
- Playwright 1.63.0 present OUTSIDE venv (CLI + npx) — verified; use as subprocess, never pip-install.

---

## 3. CANONICAL PIPELINE CONTRACT — how new analytics plug into ProcessingSession

### 3.1 The three plug-in shapes (frozen — do not invent a fourth)

**(A) AnalyticModule** (`analytics/base.py:50-67`) — for analytics that need ONLY `(ctx, tracks)`:
```python
class AnalyticModule(abc.ABC):
    id: str
    def process(self, ctx: FrameContext, tracks: TrackView) -> list[EventDraft]: ...
    def reset(self, session_id: str) -> None: ...
```
Constructor MAY take shared stores (the `FenceAnalytic(zones)` precedent, `fence.py:79`). Modules read `TrackView.active_tracks` (current-tick only, `tracks.py:137-147`) and `view.get(tid)` → `TrackState` (positions deque of `(x, y, tick)` maxlen 60, `tracks.py:51-67`; `first_seen/last_seen/frames_seen/class_name/active/max_conf`). NEVER mutate; NEVER track/detect/spawn threads. Applicable: crowd, running, abnormal, loitering, night.

**(B) Frame-consuming service** (the m8 reid precedent, `integration.py:1-35`) — for analytics needing PIXELS (crops): NOT an AnalyticModule; a service the session calls per tick next to the chain. Exact wiring point — `session.py` `_run`, after the analytics chain (`:373`), before `_annotate` (`:376`):
```python
# after: for module in self._analytics: drafts += module.process(ctx, view)
# before: annotated = self._annotate(pkt.frame, objects)
if <capability-enabled>:
    drafts += <svc>.process_tick(self.source_id, ctx, view, pkt.frame)
    drafts  = <svc>.enrich_drafts(self.source_id, drafts)   # reid only
```
Applicable: reid (`MultiCameraReIdService.process_tick/enrich_drafts`, signatures pinned `integration.py:139-175/257-287`), face (`YuNetFaceDetector.detect(frame)` + session-side trigger policy, §6).

**(C) Render layer** — additive kwargs on `annotate()` (`annotation.py:98-106`, current signature already carries `zones/layers/trajectories`). New visual capabilities join the SAME pattern: optional kwarg, `None` default = byte-identical frozen surface, per-item degrade-on-malformed (the `_draw_zone`/`_draw_trajectory` discipline). Phase 3 adds `faces: Optional[list] = None`.

### 3.2 Draft flow (pinned — zero new paths)

Drafts (any shape A/B) → the ONE `self._commit(drafts, jpeg, ctx)` (`session.py:270-273`) → `EventEngine.commit` (`engine.py:129-140`) → cooldown (`:190-201`) → severity via `_severity_for` (`:204-238` + §2.6 `_NEW_TYPE_BASE`) → snapshot iff severity ≥ MEDIUM (`:157-160`) → writer row + SSE. New types are plain strings — events table `type TEXT` has no CHECK (verified `migrations.py:57`). `EventDraft` fields: `type, track_ids, zone_id, direction, confidence, metadata` (`base.py:33-47`) — behavior/face/anpr drafts carry the full explainable breakdown in `metadata` (§7).

### 3.3 Session chain composition rule

`self._analytics` (`session.py:108`) — **FenceAnalytic MUST remain index 0** (`status_payload:471` and `_stats_payload:457` read `self._analytics[0]` for `zone_person_counts`). New AnalyticModules APPEND: `[FenceAnalytic, CrowdAnalytic(fence, zones), RunningAnalytic(), AbnormalMovementAnalytic(), LoiteringAnalytic(zones), NightMovementAnalytic()]`. Each gets `reset(source_id)` at start (the `:108-109` pattern extended). Capability gates (config on/off + model presence) decide membership AT session construction — a disabled module is not in the chain (cheapest honest gating).

### 3.4 Capability toggles ≠ render layers

Render layers = `self._layers` dict + `update_layers` (`session.py:253-268`, valid keys today `{boxes, labels, fps, trajectories, zones}`) — Phase 3 ADDS `"faces": False` to the defaults dict AND the valid set (`:262`). Capability toggles (Re-ID, Face detect, ANPR, Behavior pack) are CONFIG + model-presence gated booleans on the session (e.g. `self._reid_enabled`), surfaced via health/status, flipped via a config-backed mechanism or a small additive status field — NOT via the layers endpoint (a disabled model must never look like a render toggle). Keep the two concepts separate in UI copy too.

---

## 4. PER-PHASE BINDING CORRECTIONS & ROUTING

**Ownership (binding):** executor1 owns everything EXCEPT: `backend/api/map.py`, `backend/db/dao.py`, `backend/db/migrations.py` (**GOD-ROUTED — executor1 must NOT edit these three**; the two needed hunks are specced in §4-Phase5/§9 for MICHAEL). `backend/vision/annotation.py` is executor1-**swappable, additive-only, hardening-hunk-preserved** (the uncommitted `:76-77` widen must survive verbatim; defaults byte-identical). Executor1 also must not touch `Trinetra-m8/` (read-only source), `BorderSurvaillance/`, `DeepCamera-master/`, `crowd-abnormal-behavior-detection-main/` (read-only references), or `scripts/m7_e2e.py` / `phase0_upload_chain.py` (regression harnesses — RUN only).

### Phase 1 — V3 P1 completion + Live View/Analytics/EventLog surfaces (re-scoped)

- **Landed, verify-only:** layers backend (`session.py:122-126/253-268`, `main.py:171-194`), per-class counts (`session.py:477-498`), LayerToggles + Cameras stats strip + Dashboard cards + EventSummary + LiveFeed C2 removal + api.ts/types.ts (§2.1). Run gates; fix only real breaks.
- **Build now:** (a) `Analytics.tsx` Runtime panel: People/Vehicles/Active/Frames/FPS/Device/Uptime from `status.session`, zero/— when idle; Trajectory Info = `history_len` 60 pts × active tracks (capability statement); Fence Status = active zone count + `zone_person_counts`; mount shared `LayerToggles`. (b) **NEW** `EventLog.tsx` page + nav "Event Log" (§2.4 spec). (c) `Events.tsx` type + source filters (client-side, real values only). (d) `SourcePicker.tsx` labels. (e) `App.tsx` NAV 8th entry.
- **Tests:** none new beyond what `test_layers.py` covers (already landed) — Phase 1's gate is tsc + build + Playwright-eyeball via `phase0_upload_chain.py` staying green. If any EventSummary/EventLog rendering bug surfaces, fix in place (all executor1 files).
- **Acceptance:** every Analytics runtime number traces to `status_payload`/`/api/events`; Event Log row count matches `GET /api/events?limit` count; search "ZONE_ENTRY" narrows; zero-when-zero everywhere; gates green.

### Phase 2 — M8 Re-ID port + fast-reid-via-cv2.dnn (as planned, with these pins)

- **Copy** (read-only source): `Trinetra-m8/backend/reid/` (11 modules), `tests/test_m8_reid.py` (23 tests — port VERBATIM; imports verified compatible: `backend.analytics.base`, `backend.state`, `backend.vision` all exist byte-compatible in main tree), `scripts/m8_reid_bench.py` (port minus the export machinery, §2.10), `[reid]` toml block.
- **Config:** `config.py` — add `ReIdCfg` (mirror m8 `config.py:82-101` minus `model_path`-torchscript bits, plus `onnx_path="fast-reid_mobilenetv2.onnx"`, `embedder="cv2dnn"`, `enabled=false`) + extend `_build()` (keep all 8 existing groups; append REID) + export. `default.toml` gains the plan's `[reid]` block (plan §2 values: confirm 0.80, candidate-never-merge 0.55, max_gap 600, exemplars 8, interval 25 ticks, min_frames 5, min_gap 10s — matches m8 `config/default.toml:39-54`, verified).
- **NEW `OpenCVDnnEmbedder`** (embedder.py, port + add): `name="cv2dnn"`; `_try_load` = `cv2.dnn.readNetFromONNX(MODELS_DIR/onnx_path)` (file-missing → `available=False`, honest, the `embedder.py:107-127` pattern); `embed(crop)` = `preprocess_crop` (frozen `embedder.py:46-61`: BGR→RGB→resize (256,128) W×H INTER_CUBIC→float32 raw 0-255 NO /255 NO ImageNet-norm→HWC→CHW→batch dim) → **zero-pad to batch 32** (fixed-shape graph — batch-1 is INVALID_ARGUMENT per audit; pad with ZEROS, pure-conv graph is batch-independent so row 0 is the crop's true embedding — verified output `[32,1280]`) → `net.forward()[0]` → `l2_normalize`. `embed_batch` pads once. `make_embedder` (`integration.py:77-86`) gains the `"cv2dnn"` branch.
- **Model:** COPY `fast-reid_mobilenetv2.onnx` (8.5MB, MIT) from `DeepCamera-master/src/yolov7_reid/src/models/` → `Trinetra/models/`; manifest comment carries md5 `77a97e84aac88bdb3eeaa17dd6c57180`. **Do NOT copy reid.ts** (R2). `TorchScriptEmbedder` class ports for provenance, nothing points at it.
- **Wiring:** app-scoped `MultiCameraReIdService` — instantiate in `main.py` lifespan after the ZoneStore install (`:260`), `ApiState` (`errors.py:24-42`) gains an additive `reid_service` slot + `get_reid_service()` accessor (errors.py is executor1-swappable, additive). Session fetches via start path; registers `self.source_id` as camera_id on start, unregisters in `_finalize` (single-session MVP; R9 plan note endorsed as the default). Per-tick wiring at §3.1-B. `FrameContext`/`EventDraft` identical between trees (verified) — zero `analytics/base.py` changes.
- **Endpoints:** `GET /api/reid/persons` (`all_persons`) + `GET /api/reid/persons/{pid}` (`person_summary` — shape pinned `M8_CROSS_CAMERA_CONTRACT.md:93-119`) — **INLINE in `main.py` after the layers routes** (C7-clean: no new router file, no include-block edit; 404-clean, honest empty when no identities). This OVERRIDES the plan's optional `backend/api/reid.py` router.
- **Tests:** 23 ported (DummyEmbedder — no model needed) + `tests/test_reid_port.py`: (a) OpenCVDnnEmbedder shape/scale test on the committed onnx (skip-with-reason if file absent); (b) stub-session wiring: reid enabled → PERSON_IDENTITY_MATCHED once, enriched ZONE_ENTRY carries `global_person_id` only when CONFIRMED, CANDIDATE never links (T9 semantics); (c) FPS on/off measure.
- **UI:** EventDetail chips (`metadata.global_person_id`, `identity_cameras` — absent → nothing); Investigation identity strip consuming the two endpoints; Live View "Re-ID" capability toggle — enabled only when health reports the onnx present, OFF default, label **"EXPERIMENTAL — possible-match semantics"**; single-video re-entry = "match", cross-camera = "POSSIBLE MATCH (score)" (audit §15/§32 wording).
- **Health:** `_model_status()` (`main.py:73-82`) gains `models.reid = {file, present, size_mb}`.
- **Acceptance:** 218+23+new green; FPS drop <15% measured (not guessed); identity chips only when real.

### Phase 3 — YuNet face detection (as planned, with these pins)

- **Model:** copy yunet.onnx (232,589 bytes) from `/var/folders/gj/xmn351s52wg2crpnx5wvpz080000gp/T/opencode/trinetra_audit/yunet.onnx` → `Trinetra/models/yunet.onnx` (verified present today; if the temp swept, escalate to MICHAEL — never substitute silently).
- **NEW `backend/vision/face.py`** — module, shape B: `YuNetFaceDetector` lazy `cv2.FaceDetectorYN.create(str(path), "", (320,320), score_threshold=0.6, nms_threshold=0.3)` (API verified present in venv cv2 5.0.0); honest `available` (file-existence gate, embedder pattern); `detect(frame) -> [{bbox, conf, landmarks5}]`; NO recognition, NO gallery, NO identity DB (R4).
- **Scheduling (R4/R6):** trigger-gated, never per-frame: run when a person track (a) was just newly-confirmed, (b) entered a zone, or (c) is reid-enrolled — AND bbox height ≥80px — AND ≥5s since last face run for that track (cooldown dict, engine pattern). Session-side policy in `_run`; results stashed for the annotate call.
- **Layers + annotate:** `self._layers` gains `"faces": False` default + valid-key extension (§3.4); `annotate(..., faces=None)` additive kwarg — thin cyan box + `FACE 0.xx` chip near the person box, per-item degrade, `None` = byte-identical (same contract as zones/trajectories; extension goes AROUND the uncommitted hardening hunk — preserved verbatim).
- **Events:** FACE_DETECTED, LOW (`_NEW_TYPE_BASE` §2.6) — no snapshot (LOW < MEDIUM floor; the face is already burned into the operator frame — endorsed), metadata `{track_id, face_conf, landmarks_count, bbox, trigger_reason}`, cooldown per (track, face).
- **Health:** `models.face = {file, present, size_mb}`.
- **Tests (`tests/test_face.py`):** commit 1-2 real frames extracted from `crowd-abnormal-behavior-detection-main/assets/intrusion.mp4` as small test assets (audit measured 334 detections/60 frames there — sanctioned); module unit on those frames; trigger-gating (count `detect()` calls via monkeypatch — event-only, cooldown respected); annotate-faces unit (additive, defaults byte-identical); honest-unavailable (model dir absent → `available=False`, sessions unaffected, health present:False).
- **Acceptance:** FACE_DETECTED only after person triggers, not per frame; faces burned into MJPEG when the layer is ON; FPS impact <3% measured; toggle honest.

### Phase 4 — Crowd / behavior / night (AGPL-safe reimplementations; corrected)

- **License discipline (R9):** NO imports, file copies, or line-level translation from the AGPL repo. Standard geometry/statistics reimplemented; every constant carries a provenance comment: "value chosen by us, informed by published running-detection behavior; calibrated on real footage (docs/BEHAVIOR_CALIBRATION.md)". A grep-gate test asserting `backend/` never references the repo path is REQUIRED.
- **Files:** NEW `backend/analytics/behavior.py` (running + abnormal + loitering), NEW `backend/analytics/crowd.py`; `analytics/__init__.py` exports; session chain append (§3.3 — fence stays `[0]`).
- **CrowdAnalytic (§2.7 FIX governs):** `CrowdAnalytic(fence, zones)` — consumes `fence.zone_person_counts()` (ONE counting path — authoritative tracker + confirm-3 occupancy; recomputing PIP would be a second path, banned) + ZoneStore polygon areas (shoelace over §12 normalized points — reuse `analytics/geometry.py` helpers where applicable). Emits CROWD_DENSITY on count ≥ band sustained ≥2 ticks; MEDIUM ≥4, HIGH ≥8 (config `[crowd]`); metadata `{person_count, polygon_area_normalized, density, band}`; zone_id set → engine cooldown keys per zone.
- **RunningAnalytic:** per person track over last W=10 samples: `speed_score=min(1, avg_px_per_s/80)`, `displacement_score=min(1, total_px/150)`, `direction_score`= resultant length of unit move vectors (moves >2px only). `confidence=0.5·s+0.3·d+0.2·dir`. Gate: alive ≥5 ticks, trigger ≥0.50 for ≥3 consecutive ticks (hysteresis). SUSPECTED_RUNNING MEDIUM (+1 if RESTRICTED zone context — foot-point PIP via public geometry, NOT fence private state). Once per track per cooldown. Metadata: the full breakdown. Config `[behavior]` (planner values endorsed with provenance comments).
- **AbnormalMovementAnalytic:** per-camera EWMA baseline of median person speed (60s); event when speed > max(2×baseline, 1.5×running-gate) AND direction_score <0.3 for ≥3 ticks; LOW; <5 person-observations → NO-OP (under-calibrated, honest). Metadata `{baseline_px_s, observed_px_s, direction_score}`.
- **NightMovementAnalytic:** person track active AND `ctx.is_night` (session computes it, `session.py:63/355`, luma<40) for ≥5 consecutive ticks → NIGHT_MOVEMENT LOW, once per track (cooldown), metadata `{mean_luminance, ticks_in_dark}`. No enhancement claims.
- **LoiteringAnalytic:** dwell = `last_seen - first_seen` ≥20s wall AND spatial σ(positions) <80px → LOITERING LOW (MEDIUM inside a zone — public-geometry PIP). Once per track, hysteresis release. Config knobs.
- **Engine:** add the Phase-4 types to `_NEW_TYPE_BASE` (§2.6): SUSPECTED_RUNNING=MEDIUM, SUSPECTED_ABNORMAL_MOVEMENT=LOW, LOITERING=LOW, NIGHT_MOVEMENT=LOW, CROWD_DENSITY=MEDIUM (+modifiers).
- **UI:** Analytics Layers area gains a "Behavior" capability toggle group (per-pack enable mirrors config; disabled-with-reason when no session); EventSummary/EventLog type labels use "SUSPECTED —" prefixes (NEVER "action recognition").
- **Tests:** `tests/test_behavior.py` + `tests/test_crowd.py` — scripted synthetic TrackStore/TrackView (fast straight line → RUNNING; slow arc → not; erratic → ABNORMAL; stationary 25s → LOITERING; is_night ctx → NIGHT; count band → CROWD_DENSITY); real geometry math, no cv2 mocks; AGPL grep-gate. **Real-footage validation (honest log):** `crowd-abnormal-behavior-detection-main/assets/running.mp4` → expect ≥1 SUSPECTED_RUNNING (record actual, including misses) into `docs/BEHAVIOR_CALIBRATION.md`.
- **Acceptance:** every event carries an explainable breakdown; FPS with all behavior modules ON ≥85% of Phase-1 baseline (measured); suite green.

### Phase 5 — Deterministic summary + investigation enrichment (with the GOD-routing ruling)

- **`backend/services/summary.py`** (NEW): `build_session_summary(session) -> dict` from ONLY `status_payload()`, the session's committed EventRows (existing DAO read path), flushed track aggregates. Shape per plan §5.1 (every number traces to a row; `notes[]` = one deterministic clause per notable state; NO LLM). Endpoint `GET /api/sessions/{id}/summary` INLINE in `sources.py` sessions_router region (`:159-200`, additive) — sources.py is executor1-swappable.
- **GOD-ROUTED MICRO-HUNK (MICHAEL-executed, ~10 minutes — executor1 does NOT touch dao.py/migrations.py):**
  1. `backend/db/migrations.py` — append migration 3: `ALTER TABLE tracks ADD COLUMN trajectory TEXT;` (nullable; old rows NULL — mirrors the migration-2 ALTER pattern `migrations.py:97-99`).
  2. `backend/db/dao.py` — add ONE method (existing `flush_tracks` untouched): `def upsert_track_trajectories(self, session_id: str, trajs: dict[int, str]) -> None` — `INSERT INTO tracks(session_id, track_id, trajectory) VALUES(?,?,?) ON CONFLICT(session_id, track_id) DO UPDATE SET trajectory=excluded.trajectory` executemany + commit.
  **Executor1's code degrades honestly pre-hunk:** session finalize builds `trajs = {t.track_id: json.dumps(downsampled ≤60 pts)}` but calls the DAO method via `hasattr`/column-pragma check (the `dao._geo_columns` pattern, `dao.py:308-314`); `sources.py` `session_tracks` SELECTs trajectory only when the pragma shows the column; absent → field omitted (never fabricated). **Phase 5 does NOT block on the hunk.**
- **Frontend:** EventSummary gains the per-session summary block (Dashboard active/latest; Investigation picked); Investigation track table gains a "view path" mini-canvas drawing the persisted normalized polyline + related-events filter by track_id over loaded pages, labeled "(loaded window)" (C8 advisory); EventDetail trajectory chip when the path exists.
- **Tests (`tests/test_summary.py`):** deterministic summary from a scripted session (every field asserted against inputs); trajectory round-trip post-hunk (skip-with-reason pre-hunk); endpoint 404/empty; degradation test (no column → absent, honest).
- **Acceptance:** summary numbers == API/status verbatim; migration-3 round-trip green (post-hunk); no narrative invention.

### Phase 6 — ANPR (decision in §8; gated)

Files per plan §6 (NEW `backend/analytics/anpr.py`, `tests/test_anpr.py`, `[anpr]` config, vehicle-trigger wiring, health, UI toggle) with the §8 contract. **GATED on model acquisition — if not acquired by demo, ship the honest COMING SOON/plate-only states and say so in the final report. Never fabricate.**

### Phase 7 — RTSP + camera management/map polish (with §2.9 fix)

- **NEW `backend/sources/rtsp.py`** mirroring `webcam.py`'s shape (`base.py:81-122` protocol + `is_live=True` + `type_name="rtsp"` + read-fail-streak→ERROR + `reopen()`); `cv2.VideoCapture(uri, cv2.CAP_FFMPEG)` with `OPENCV_FFMPEG_CAPTURE_OPTIONS="rtsp_transport;tcp"` set BEFORE first capture (module-level env set is fine — before any VideoCapture creation); first-frame watchdog 10s → honest SourceError. Register in `sources/__init__.py` factory; `make_source` (`session.py:560-574`) gains `type=="rtsp"` + `uri`; `StartRequest` (`main.py:67-70`) gains `uri: str = ""`; `session.py:183` fix per §2.9. Session reconnect = the existing ladder (verified it dispatches on `is_live`, `session.py:291-316`) — RtspSource just sets the flag.
- **Test rig (not CI):** `scripts/rtsp_test.py` — mediamtx (brew, installed) + ffmpeg publish loop → RtspSource reads; asserts fps + SOURCE_LOST→RECONNECTED after killing mediamtx; honest "auth untested" label.
- **UI:** Live View/SourcePicker gains an RTSP uri input with the honest note (transport verified loopback; real-camera network + auth untested); Sources page registry columns (id/name/type/status LIVE-only-when-matching/lat-lng — when NULL/location); Map marker click info card.
- **Tests (`tests/test_rtsp_source.py`):** fake URI → clean SourceError; backoff via monkeypatched VideoCapture; unit-only (mediamtx rig stays a script).
- **Acceptance:** rtsp://localhost loop end-to-end with events+MJPEG; kill-server-mid-stream → SOURCE_LOST then RECONNECTED; pages show only real state.

### Phase 8 — Full E2E demo + final report

- **Create `scripts/trinetra_e2e.py` NOW (this is its first appearance — Phase 0 was absorbed, §2.3):** boot → health → light Command Center 4 cards zero-when-zero → Live View → SCAN CAMERAS (honest) → **Playwright-in-real-Chromium upload drill (MICHAEL's required confirmation: drop running_clip through the REAL UI drop zone, MJPEG `<img>` decodes ≥10 real frames >2KB, session pill RUNNING, PERSON_DETECTED in LIVE ALERTS ≤5s, cards increment)** → toggles each visibly change the stream → create RESTRICTED zone via UI → ZONE_ENTRY HIGH + evidence shows the fence → FACE_DETECTED → Re-ID match + enriched alert → SUSPECTED_RUNNING on crowd running.mp4 → NIGHT (record honestly if no night footage) → EventDetail chain Event→Camera→Zone(+Geo)→Evidence→Identity→Trajectory → Event Log table row → EventSummary sentence diff = zero invention → session summary == API → STOP → hard-reload persistence → Analytics runtime+charts → Map marker/sector → Cameras registry LIVE-then-idle → RTSP local loop (rig, if mediamtx up) → restart-uvicorn persistence. Honest PASS/FAIL + observed values per step → `docs/TRINETRA_E2E_DEMO_LOG.md`.
- **`docs/TRINETRA_FINAL_INTEGRATION_REPORT.md`:** verified-state-per-phase (claim = test name + measured number), honesty ledger (VERIFIED/HEURISTIC/EXPERIMENTAL/DISABLED per capability), benchmark table, §52 mapping, open gaps (ANPR Indian-plate validation, 2-camera reid, night footage, RTSP auth), reproduction commands.

---

## 5. RE-ID PORT CONTRACT (m8 → main tree)

1. **Embedder swap:** port `embedder.py` whole (TorchScriptEmbedder + DummyEmbedder + frozen `preprocess_crop`/`l2_normalize`); ADD `OpenCVDnnEmbedder` per §4-Phase2 (interface `embed(crop)->1-D unit vector`, `embed_batch`, `available` — pinned `embedder.py:71-85`). `make_embedder` gains `"cv2dnn"`. Default `embedder="cv2dnn"`.
2. **EventEngine integration deltas M7-vs-m8 (verified):** `analytics/base.py` byte-identical; `engine.py` differs ONLY by M6 additions (disk-low gate `engine.py:249-257`, SOURCE_RECONNECTED in `_SYSTEM_TYPES` `:41-43`) — both already in main. Reid types flow through the generic INFO branch (`:235-238`) — with §2.6's dict they land explicitly as INFO (same behavior, explicit policy). Cooldown backstop applies. **Zero engine behavior change for reid types.**
3. **Global id scheme:** `P-0001…` minted by `IdentityGallery.mint` under lock (`gallery.py:41-53`) — the single allocation point; port unchanged. CANDIDATE never links (matcher `:16-18` policy: confirm ≥0.80 links; 0.55 ≤ sim < 0.80 = CANDIDATE review-only; below = UNMATCHED — never merged).
4. **Config block:** §4-Phase2 (defaults: embedder cv2dnn, onnx_path, confirm 0.80, candidate 0.55, max_gap_s 600, exemplars 8, interval 25, min_frames 5, min_gap 10s, enabled false).
5. **Test port list (23, verbatim):** T1 same-embedding→same-identity; T2 different→different; T3 ambiguous→CANDIDATE; T3b below-candidate never matches; T4 two-camera chain; T5 three-camera chain; T6 same local track retains; T7 different people stay separate; T8 identity survives track-id change; T9 zone intrusion attaches global_person_id; T10 global history ordered; T11 duplicate obs no duplicate transitions; T12 concurrent gallery integrity; T12b concurrent distinct no cross-links; T13 selective sampling reduces inference; T14 no identity fabricated without embedding; T14b unavailable embedder honest; T15 event payload engine-compatible; clip summary from real state; preprocess contract; history rejects invented kinds; gallery minting monotonic; matcher temporal veto. Plus `test_reid_port.py` (§4-Phase2).
6. **Wording rules (R2/audit §15/§32):** single-video re-entry = "match"; cross-camera = "POSSIBLE MATCH (score)"; never "same person". UI label "EXPERIMENTAL — possible-match semantics" until 2-camera footage validates.

---

## 6. FACE MODULE CONTRACT

Wrapper `YuNetFaceDetector` (§4-Phase3): lazy `cv2.FaceDetectorYN.create(str(path), "", (320,320), score_threshold=0.6, nms_threshold=0.3)`; `available` property (file-existence, honest False, sessions unaffected); `detect(frame) -> list[dict]` each `{bbox:[x1,y1,x2,y2], conf: float, landmarks5: list}`. Scheduling = event-triggered only (newly-confirmed person / ZONE_ENTRY / reid-enrolled; bbox ≥80px tall; ≥5s per-track cooldown; count detect calls in tests to prove no per-frame inference). Render: `annotate(..., faces=None)` additive kwarg — cyan (255, 255, 0 BGR-ish family consistent with existing palette) thin box + `FACE 0.xx` chip; per-item degrade; `None` default byte-identical; hardening hunk preserved. Events: FACE_DETECTED LOW via `_NEW_TYPE_BASE`; no snapshot (LOW < floor; the operator frame shows the face); metadata `{track_id, face_conf, landmarks_count, bbox, trigger_reason}`. Layer `"faces": False` default + valid-key extension + LayerToggles entry "Face Detection" (enabled-only-when-model-present; disabled shows why). Health `models.face`. Config: `[face] enabled=false, score_threshold=0.6, nms_threshold=0.3, min_person_bbox_px=80, cooldown_s=5.0, model="yunet.onnx"`. NO recognition/gallery/identity DB (master-prompt ban).

---

## 7. BEHAVIOR / CROWD / NIGHT CONTRACTS

- **Constants + evidence basis (R9):** each constant documents "chosen by us, informed by published behavior" + calibration reference. Running weights 0.5/0.3/0.2 (standard evidence fusion), speed norm 80 px/s, displacement norm 150 px, window 10, trigger 0.50, min-alive 5 — CALIBRATED on real footage, actuals recorded in `docs/BEHAVIOR_CALIBRATION.md` (misses logged, not hidden). Loitering 20s/80px; night = `ctx.is_night` (luma<40, session-owned `session.py:63`); abnormal = EWMA baseline deviation (no-op under <5 observations). Crowd bands = COUNT-based per §2.7 (medium 4 / high 8 / sustained 2) — density in metadata only.
- **Event types + severity ladder entries (`_NEW_TYPE_BASE` §2.6):** SUSPECTED_RUNNING=MEDIUM (+1 RESTRICTED, +1 night, cap HIGH), SUSPECTED_ABNORMAL_MOVEMENT=LOW, LOITERING=LOW (+1 in-zone), NIGHT_MOVEMENT=LOW, CROWD_DENSITY=MEDIUM (HIGH at high_count). All carry explainable metadata breakdowns (§4-Phase4). All SUSPECTED-labeled in every UI surface.
- **Per-zone count source of truth:** `FenceAnalytic.zone_person_counts()` (`fence.py:281-292`) via injected fence instance — the ONE counting path (authoritative ByteTrack tracks + confirm-3 occupancy). NO module recomputes PIP for counting. Fence stays `_analytics[0]` (§3.3).
- **AGPL-safe provenance notes:** independent implementation from standard geometry/statistics; no code/file/line copies from `crowd-abnormal-behavior-detection-main/`; concepts cited, not code; grep-gate test forbidding any backend reference to the repo path.

---

## 8. ANPR DECISION (architect ruling on the planner's recommendation)

- **Detection: VALIDATED.** Fine-tuned `yolov8n` single-class `plate` → `models/yolov8n_plate.pt` (~2-4k-image Indian-plate LPD dataset, e.g. open Roboflow/Kaggle Indian-plate sets; 30-min M4 fine-tune or Colab). Same ultralytics stack, zero new deps, loads via the same DetectorTracker machinery (a second lazy instance gated on file presence, §44). Rejected alternatives concurred (standalone LPD ONNX family; end-to-end black-box readers).
- **OCR: AMENDED (planner said PaddleOCR CPU).** PRIMARY = **PP-OCRv4 mobile det+rec ONNX via cv2.dnn** — zero new runtime deps (R10's exception stays unused), fixed-shape handling via resize-to-fixed + scale-back, CTC decode + char dict is standard deterministic math. 4-hour feasibility timebox: if the rec model can't be wired cleanly in-box, FALLBACK = PaddleOCR pip — **MICHAEL-gated dep approval required (record it in the final report's dep ledger)**; last resort = detection-only. EasyOCR rejected (heavier, torch-model downloads).
- **Acquisition gate:** no plate model by demo → ship honest "ANPR — plate detection only (no read)" or full COMING SOON; never fabricate.
- **Three-state semantics (R5):** `ANPR_PLATE_DETECTED` LOW (box found, OCR not run/failed; metadata `{vehicle_class, plate_bbox, crop_w_px, track_id}`); `ANPR_READ` MEDIUM (OCR conf ≥ `anpr.ocr_conf_min` 0.80 AND passes an Indian-format regex; metadata adds `{raw_text, ocr_conf, format}`); `OCR_UNCERTAIN` LOW (below conf or format-fail; `{raw_text?, ocr_conf, reason}`). NEVER coerce; uncertain stays uncertain.
- **Indian-plate validation (regex in config, never hardcoded):** old `^[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}$`; BH-series **`^\d{2}BH\d{4}[A-Z]{1,2}$`** (plan's 4-leading-digits version is WRONG — §2.8). Format values: `IND_old|IND_BH|UNMATCHED`.
- **Scheduling:** on VEHICLE_DETECTED (once per track per cooldown) → plate-detect on the vehicle bbox → OCR only if plate crop ≥64px wide (size-gating). Trigger wiring in `_run` (shape B).

---

## 9. RTSP CONTRACT

`backend/sources/rtsp.py` — `RtspSource(uri)`: `is_live=True`, `type_name="rtsp"` (§2.9), `source_id=f"rtsp:{sanitized-uri-or-host}"`; open = `cv2.VideoCapture(uri, cv2.CAP_FFMPEG)` after setting `OPENCV_FFMPEG_CAPTURE_OPTIONS="rtsp_transport;tcp"` env (before ANY capture in the process); read-fail streak (10, webcam's `_DISCONNECT_STREAK` precedent) → `SourceState.ERROR` → the session's existing backoff ladder (1→2→4→8s, one-shot SOURCE_LOST, SOURCE_RECONNECTED on reopen — verified `session.py:291-316`, dispatch is `is_live`-based so zero session-ladder changes); first-frame 10s watchdog → honest SourceError. Factory + `make_source` (`type=="rtsp"` + `uri`) + `StartRequest.uri` (§4-Phase7). Config: `[rtsp] enabled=false (toggle for the UI input), first_frame_timeout_s=10, transport="tcp"`. NEVER a boot dependency; the mediamtx rig is a script, not CI. Auth honestly labeled UNTESTED. Sources page keeps/extends the honest RTSP panel (today's copy at `Sources.tsx:69-75` says NOT AVAILABLE — Phase 7 updates it to the real input with the honest caveat).

---

## 10. UI SURFACE CONTRACTS (per page)

| Page | Components | API calls | Honesty rules |
|---|---|---|---|
| Command Center (Dashboard) | 4 summary cards (session fields), LiveFeed, EventTimeline (LIVE ALERTS), ALERTS SUMMARY counts, EventSummary (landed), session-summary block (P5) | `sessionStatus` (poll), SSE, `events` | zero-when-zero; every number from status/events; summary sentences diff-able against rows |
| Live View (Cameras) | SourcePicker (upload/scan/start/stop + RTSP input P7), stats strip (landed), LiveFeed, LayerToggles (landed + faces P3), camera grid, capability toggles (Re-ID P2, Behavior P4, ANPR P6) | `uploadVideo`, `webcamScan`, `sessionStart/Stop/Status`, `sessionLayersGet/Post`, `reidPersons*` (P2) | toggles disabled-with-reason when idle/model-absent; capability toggles enabled-only-when-model-present; experimental labels per §5.6/§6 |
| Alerts (Events) | severity chips, type+source filters (P1), keyset pagination, SSE/REST merge | `events` | filters over REAL loaded values; "no events match" empty state |
| Event Log (NEW, P1) | full-width table, search, Load-older-50, row-select → EventDetail | `events` (keyset) | every cell 1:1 an API field; row count == API count |
| Investigation | session list, clip summary + per-session summary (P5), tracks table + trajectory mini-canvas + related-events (P5), identity strip (P2) | `sessions`, `sessionTracks`, `sessions/{id}/summary` (P5), `reidPersons/{pid}` (P2) | absent fields render absent (never 0-when-unknown); "(loaded window)" labels |
| Map (Geography) | GeoMap chain (satellite→roadmap→schematic), marker info card (P7 polish) | `mapConfig`, `mapCameras`, sectors | LIVE only when active session matches (backend-enforced); degrade never touches the CV pipeline |
| Analytics | charts (landed), Runtime panel + Fence Status + Trajectory Info + shared LayerToggles (P1) | `sessionStatus`, `events` | runtime numbers trace to status_payload; zero when idle |
| Cameras (Sources) | registry table (P7 polish), honest RTSP panel, uploads note | `sources`, `mapCameras` | LIVE backend-driven only; unplaced → "—" |

Global: no dead controls (every toggle hits a real endpoint); no Math.random/lorem/sample anywhere in src (grep-gate); deleted zones render raw zone_id, never a fabricated name (C6); Re-ID/ANPR/Face/Behavior labels carry VERIFIED/EXPERIMENTAL/HEURISTIC per the honesty ledger.

---

## 11. TEST-GATE + BENCHMARK REQUIREMENTS (per phase → master §52)

Every phase lands ONLY with: **full suite green at ≥ current collected count (re-verify at land; 218 as of this handoff) + its new tests; 4 skips + 2 warnings unchanged; NO existing test file modified/deleted** (if one seems to pin behavior you must change, STOP and escalate to MICHAEL — V3 handoff §6 rule carries). Frontend: `npx tsc --noEmit` 0 errors + `npm run build` clean. Regression: `scripts/m7_e2e.py` 24/24 + `scripts/phase0_upload_chain.py` all-PASS after any backend-affecting phase.

| Phase | New tests | Benchmarks (§45, via `scripts/bench.py` pattern) |
|---|---|---|
| 1 | (EventLog/filters are UI-only — Playwright-verified in P8) | FPS baseline snapshot (the reference for later phases) |
| 2 | +23 ported + test_reid_port.py | FPS reid ON vs OFF on running_clip (<15% drop); embed latency single/batch |
| 3 | +test_face.py | FPS faces ON vs OFF (<3%); face detect latency (2.8ms known) |
| 4 | +test_behavior.py +test_crowd.py + AGPL grep-gate | FPS all-behavior ON ≥85% of P1 baseline; real-footage calibration log |
| 5 | +test_summary.py (+migration round-trip post-hunk) | summary build latency (trivial; assert <50ms) |
| 6 | +test_anpr.py (validator, three-state machine via stubs, size-gate, honest-unavailable) | plate-detect + OCR latency per trigger (gated run) |
| 7 | +test_rtsp_source.py | rig log: loopback fps + reconnect timings (script, honest) |
| 8 | — (drill + logs) | final benchmark table for the report |

---

## 12. SEQUENCING + COMMIT BOUNDARIES

**All executor1 changes stay UNCOMMITTED for MICHAEL's review** (commits NOT in executor scope). Order: Phase 1 → 2 → 3 → 4 → 5 → 6 (gated; skip gracefully to 7 if the model isn't acquired) → 7 → 8. Phase 2 and 3 are independent (both touch session.py `_run` — land 2 first, its wiring is the shape-B precedent 3 copies). The §4 god-hunk (migration 3 + DAO trajectory method) is requested from MICHAEL at Phase 5 START (Phase 5 code degrades honestly pre-hunk, so no blocking dependency).

**Logical commit grouping for MICHAEL's review pass** (he commits; executor lists every changed file in the final report):
1. V3-P1 backend remainder + test_layers (already uncommitted — review first, as-is)
2. V3-P1 frontend remainder + EventLog + alerts filters + Analytics runtime (Phase 1)
3. Re-ID: models/reid onnx + backend/reid port + config + engine INFO entries + main.py wiring/health/inline endpoints + UI + 23+new tests + bench (Phase 2)
4. Face: yunet.onnx + vision/face.py + annotate faces kwarg + layers["faces"] + engine LOW entry + UI + tests (Phase 3)
5. Behavior/crowd/night: analytics modules + engine severity entries + config + UI + tests + calibration doc (Phase 4)
6. Summary/investigation: summary.py + endpoint + migration-3 god-hunk (MICHAEL's own commit) + trajectory flush/read + UI + tests (Phase 5)
7. ANPR (if landed): model + module + engine entries + config + UI + tests (Phase 6)
8. RTSP + camera/map polish + rig (Phase 7)
9. E2E drill + logs + final report (Phase 8)

---

## OPEN ITEMS FOR MICHAEL (none block Phase 1-4)

1. **God-dispatch (Phase 5):** migration 3 + `DAO.upsert_track_trajectories` — spec pinned in §4; ~10 minutes. Request at Phase 5 start.
2. **ANPR OCR path:** confirm PP-OCRv4-ONNX-via-cv2.dnn as PRIMARY (zero deps) — and pre-approve the PaddleOCR pip fallback ONLY if the 4-hour feasibility timebox fails (dep must be recorded).
3. **ANPR model acquisition timing:** yolov8n LPD fine-tune needs dataset+training time (M4 or Colab). If not landed by demo → honest COMING SOON (R5).
4. **Tree drift acknowledgment:** the V3-P1 frontend surfaces (LayerToggles/EventSummary/stats strips/LiveFeed C2 removal) landed UNCOMMITTED after your fact-recording (timestamps 2026-09-10 ~02:13-02:23) — confirm that work is your sanctioned executor's and review it with the rest of the tree.
5. reid.ts OPEN QUESTION (inventory §6 Q1) is RESOLVED by R2 — rejected, not shipped; no action needed.

---

**Final state required at sprint close:** suite green ≥ current+new (4S/2W unchanged) · tsc + vite build clean · m7_e2e 24/24 + phase0_upload_chain all-PASS · every UI number traces to an API field · every capability honestly labeled · benchmarks recorded per phase · all changes uncommitted, listed for review.
