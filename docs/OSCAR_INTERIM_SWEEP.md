# OSCAR INTERIM SWEEP — GATE-0 .. Phase 4 (read-only adversarial review)

- **Reviewer:** oscar-mtt8m47c (stage-5 verifier), dispatched by god 2026-09-10T07:14Z (conv-25e522, re-send of dropped 13:05Z copy); protocol changed to FILE-REVIEW-ONLY by god 07:57Z sign-off #2 (runtime evidence supplied by god; my earlier single-run evidence retained and consistent)
- **Surface:** HEAD `3d0c7e2` + uncommitted tree at review time; executor mid-flight on P6 — NOT disturbed; repo untouched by me except this file (mandated deliverable). No commits, no reverts, :8000 untouched.
- **Verdict: FAIL — 2 blockers.** Both are the SAME root cause (analytics reading `.bbox` on `TrackState`, which only has `last_bbox`) killing two capabilities (faces, ANPR) on the product path, both suite-blind via mock-type divergence. Everything else verified green, including all 7 dispatched scope items' claims. ~6 lines total fixes + 2 must-fail composition tests; a delta-only re-review after the executor fix pass can flip this to PASS (M5 precedent).

---

## 1. Independent verification runs (one each, god-approved shape-variance discipline)

| Check | Result |
|---|---|
| Full test suite (unsandboxed, venv) | **319 passed / 4 skipped / 0 failed** — 109.09s, 323 collected |
| `tsc --noEmit` | PASS |
| `npm run build` (vite) | PASS — 49 modules, 227.9 kB js |
| `scripts/phase0_upload_chain.py` | **ALL CHECKS PASS** — live upload→session→MJPEG→browser chain on ephemeral port; 60 real MJPEG frames decoded, annotation pixels burned in (15,392), layers GET/POST live, 50 events persisted, event kinds include real V3.5 types (SUSPECTED_RUNNING, CROWD_DENSITY_*) |

**Suite-claim note (attribution):** god's dispatch cited the executor claim "276P/4S/0F at 280 collected". The tree moved forward DURING my review (P6 deterministic summaries + Phase 6 ANPR + Phase 7 RTSP + their tests landed 07:17Z+, mtimes verified). My run on the current tree: 319P/4S/0F. Zero failures either way; no test weakening found (the `test_m5_db` churn 2→3 migrations is legitimate C5 update churn). The banked claim is superseded, not falsified.

## 2. Scope items — adversarial re-verification (all god-spot-verified claims re-checked by me)

1. **V3 sprint (P0-P3)** — VERIFIED: light theme real (index.css delta only adds focus rings; zero dark tokens in diff), LayerToggles honest-disabled when no session (no dead controls), EventSummary/EventLog additive, layers API contract exact (partial merge, unknown key → 400, 404 no-session), `test_layers.py` strict byte-identity test (boxes+fps off == pristine frame) is genuine. Per-class status fields snapshot-derived (C5 discipline).
2. **F3/F4** — VERIFIED: `map.py` lat/lng ±90/±180 bounds (400); `_draw_zone` except-tuple now includes OverflowError + cv2.error.
3. **M8 Re-ID port** — VERIFIED vs V1/V-bindings: dynamic-batch PRIMARY with batch-32 zero-pad fallback; invariance acceptance test (cosine ≥ 0.99999 vs padded) present with honest skip-if-no-model; frozen preprocessing contract shared by all embedders; honest-unavailable gates everywhere (missing ONNX = clean NO-OP, never fabricated identity); CANDIDATE never links (0.55 never merges); class guard; per-(identity,camera) transition suppression; bounded exemplars; sampling policy reduces embeds (pinned by test); session shape-B wiring post-analytics/pre-annotate with capability-must-not-kill-tick guards; `enabled=false` default honored (lifespan constructs service only when enabled).
4. **Phase 3 YuNet** — claims VERIFIED (detection-only, honest UNAVAILABLE, default-OFF byte-identity, dimension sync, 80px gating, 5s cooldown). **BUT see Blocker 1: the capability is dead on the product path.**
5. **Phase 4 clean-room** — VERIFIED: crowd is pure count-based (4/8, 2-frame sustain, zone purge, 10s cooldown; pixel-area absent); kinematics is first-principles math over `TrackState.positions` (window-10 velocity/displacement/straightness, dwell+radius loitering); zero AGPL contact (import scan clean); `_NEW_TYPE_BASE` in `events/engine.py` matches the V4 dict verbatim (+additive `FACE_DETECTED: LOW`), RESTRICTED/night +1 escalation with HIGH cap implemented in `_severity_for`.
6. **Migration 3 + DAO trajectory (V5)** — VERIFIED: `ALTER TABLE tracks ADD COLUMN trajectory TEXT` as migration 3; `_has_trajectory_column()` pragma degrade pre-hunk; `upsert_track_trajectories` + 7-tuple `flush_tracks` with `trajectory=COALESCE(excluded, tracks)`; session finalize downsamples to ≤60 normalized waypoints; tracks API serves them (`json` import present — my initial diff-fragment concern retracted).
7. **phase0 drill** — re-run by me: ALL PASS (table above). Upload chain NOT broken — confirmed live.

## 3. Findings

### BLOCKER 2 — ANPR is DEAD on the product path (identical root cause to Blocker 1)

- Found under god's 07:57Z FILE-REVIEW-ONLY extension (ANPR ruled in-scope as landed code).
- `backend/analytics/anpr.py:242` reads `bbox = getattr(t, "bbox", None)`; the session invokes every analytic via `module.process(ctx, view)` where `view.active_tracks` are **`TrackState`** objects — `last_bbox` only, no `.bbox` → `bbox is None → continue` for every vehicle track.
- Effect: no ANPR_READ / OCR_UNCERTAIN / ANPR_PLATE_DETECTED event can EVER fire on the real path, model or heuristic mode notwithstanding. The `/api/health` `anpr_mode` field reports "heuristic_fallback" honestly, but the capability itself is unreachable — same no-feature-theater violation as face.
- **Suite blindness (same M5-F1 class):** `tests/test_anpr.py` calls `analytic.process_tracks(...)` directly with `TrackedObject` instances (the vision dataclass, which DOES define `.bbox`) — not the type the session passes. All ANPR tests green while the product path never reaches them.
- Live corroboration: my phase0 drill's committed event kinds (SUSPECTED_RUNNING, CROWD_DENSITY_*, ZONE_ENTRY/EXIT, PERSON_DETECTED, SOURCE_*, SESSION_COMPLETED) include ZERO ANPR_* / FACE_DETECTED events — consistent with both dead paths (weak evidence for face/ANPR specifically since that clip has small people and no vehicles, but the code reading is conclusive).
- Contrast: kinematics reads `track.positions`, crowd reads `zone_person_counts()`/`class_name`, fence reads foot-points — all TrackState-real attributes, all LIVE (SUSPECTED_RUNNING + CROWD_DENSITY_* fired live in the drill).
- **Fix (≤3 lines):** read `last_bbox` (same fix as face.py), + ONE composition test constructing a real `TrackState` that FAILS on current wiring.

### BLOCKER 1 — Face detection is DEAD on the product path; suite is blind to it (M5-F1 class)

- `backend/vision/face.py:164` reads `getattr(obj, "bbox", None)`.
- The session calls it with `self._store.active_tracks` (`backend/services/session.py:434-436`) — **`TrackState` objects**, whose `__slots__` (`backend/state/tracks.py`) define **`last_bbox` only; there is no `.bbox` attribute**.
- Therefore `bbox is None → continue` for EVERY real track, always: no `FaceDetection` ever returns, no `FACE_DETECTED` event ever fires, the `faces` layer never renders anything even when toggled ON with `yunet.onnx` present.
- **Suite blindness:** all 7 `tests/test_face.py` gating/cooldown tests use a local `DummyTrack` class that *does* define `.bbox` — the mock diverges from the real type, so 319 passing tests include a dead product capability (the recurring "green suite ≠ shipped product" lesson; here the unit tests constructed the object graph directly, exactly like M5 F1).
- Re-ID does it right (`integration.py` reads `track.last_bbox`) — the mismatch is only in face.py.
- **Fix (≤3 lines + 1 test):** read `last_bbox` (or `getattr(obj, "bbox", None) or getattr(obj, "last_bbox", None)`), and add ONE composition test that constructs a real `TrackState` (or uses a live session) and asserts a face/landmark actually flows when the model is present — the test must FAIL on the current wiring.

### MAJOR 1 — Crowd drafts never carry `zone_type` → V4 RESTRICTED escalation is dead for CROWD_DENSITY_* (binding deviation, delivered-but-unwired)

- V4 binding: `metadata.get("zone_type") == "RESTRICTED"` elevates +1. `EventEngine._severity_for` implements it correctly, but `CrowdDensityAnalytic` drafts set `zone_id` only — no `zone_type` — so crowd in a RESTRICTED zone stays MEDIUM (never HIGH). Same delivered-but-unwired class as M7 F2 (not gate-blocking alone; frozen surfaces intact; night escalation DOES work since crowd metadata carries `is_night`).
- **Fix (≤5 lines):** look up the zone's type via the `fence_analytic` reference (already injected) and put `zone_type` in the draft metadata; +1 test asserting CROWD_DENSITY_MEDIUM in a RESTRICTED zone commits as HIGH.

### Advisories (numbered, non-blocking)

1. **Pinned-name deviation (accepted):** architect §3.1 pinned `PersonGallery.match_or_create/batch_match`; implementation is `IdentityGallery` + separate `Matcher`/`GlobalIdentityCorrelator`. Functionally equivalent-and-cleaner (stateless decision core, gallery = only id minter), all V1 semantics honored. Record as sanctioned deviation.
2. **Night-threshold discrepancy (documented, impl correct):** V3-binding text says luminance < 60; impl uses `ctx.is_night` ← session `_IS_NIGHT_LUMA = 40.0` (frozen §3). Frozen-architecture constant correctly wins; the V3.5 binding text is stale — docs-only fix.
3. **Mixed time base in reid history:** `first_seen`/`camera_transition` use wall_ts, but `enrich_drafts` zone entries record `ctx_ts()` = draft `video_ts` (0.0 fallback) — one timeline mixes clocks. Deterministic but inconsistent; unify in a later pass.
4. **Face cooldown map unbounded:** `_last_event_ts` grows per track for the session lifetime (no `forget()` on track end). Session-bounded, trivial at MVP scale; same class as M4 `_MAX_DRAFTS`.
5. **`test_layers.py` vestigial helper:** `_hudless_differs_only` returns True (placeholder) — dead weight next to the genuine strict byte-identity test; cosmetic.
6. **Kinematics scene-wide speed baseline:** `_speed_samples` pools all tracks in one session (intended "scene baseline" semantics, single-camera MVP) — fine; document when multi-camera arrives.
7. **Drift during review (process note):** P6 summaries (`backend/services/summary.py`, `test_summary.py`, EventSummary.tsx, eventSummary.ts, Investigation.tsx), Phase 6 ANPR (`analytics/anpr.py`, `test_anpr.py`), Phase 7 RTSP (`sources/rtsp.py`, `test_rtsp_source.py`) landed at 07:17Z+ — AFTER the 07:14Z dispatch. Per the 07:57Z protocol change these are NOW reviewed (§4 above): summaries + tests + RTSP VERIFIED; ANPR carries BLOCKER 2. P6 deterministic summaries (the executor's in-flight work itself) remain final-review scope — the on-disk files I read are verified, but the executor may still be touching them.
8. **Frontend/backend summary parity:** `eventSummary.ts` fills `class_names` with a `'target'` literal per track (backend resolves real class names from track rows). Cosmetic display gap only.

## 4. P5/P6/ANPR/RTSP extension (07:57Z protocol, pure code-read)

- **`backend/services/summary.py`** — VERIFIED deterministic + honest: session summary computed solely from DB rows (sessions/tracks/events/zones/stats), duration from real timestamps with fps fallback, `max_concurrent_people` via real interval-overlap sweep-arrival algorithm (correct arrival-before-departure tie sort), factual template notes only, no LLM, no invention. Event summary answers WHAT/WHO/WHERE/WHEN/MOVEMENT/WHY/EVIDENCE with every absent field explicitly "Not available"; geo-sector resolution via honest PIP over active sectors; `severity_reason` echoed verbatim when present. Kinematics fields only surface when metadata actually carries them (no fabricated velocity numbers).
- **`frontend/src/utils/eventSummary.ts` + `EventSummary.tsx` + `EventLog.tsx` + `Investigation.tsx`** — VERIFIED: faithful mirror of the backend summary contract (same clauses, same Not-available honesty); EventLog maps 1:1 to /api/events fields with keyset cursor; Investigation draws trajectories ONLY from persisted DB waypoints (no invented data), honest empty states everywhere. Minor parity gap (advisory 8): frontend `class_names` uses a `'target'` placeholder where the backend resolves real classes from track rows.
- **`tests/test_summary.py`** (469 lines, 8 tests) — VERIFIED genuine: real DB fixtures, real roundtrips (trajectory JSON persist/load), real interval math, API endpoint tests incl. 404s; no tautologies.
- **`backend/analytics/anpr.py`** — three-state machine + regexes honest, zero fabricated plates, offline-gated — **but dead on the product path (BLOCKER 2)**.
- **`backend/sources/rtsp.py`** — VERIFIED vs V7: TCP transport env set pre-capture, `type_name="rtsp"` + `is_live=True`, credential sanitization in source_id, disconnect-streak ERROR → session backoff ladder, `reopen()`. Advisory: `except (SourceError, Exception)` in `reopen()` is redundant tuple (Exception subsumes) — cosmetic.

## 5. Commit guidance

- Blockers 1+2 make a clean PASS impossible under the no-feature-theater mandate (committing claimed-working capabilities that are silently dead + test-blind). One shared fix pattern (read `last_bbox`, one helper) resolves both.
- Both code fixes are ~6 lines total, one executor pass, plus 2 composition tests that must fail on the old wiring. I will re-review delta-only (fast flip, M5 precedent).
- If god chooses commit-then-fix anyway: both blockers must be routed to the executor queue IMMEDIATELY and the Faces/ANPR claims struck from any report until fixed — my verdict stands as FAIL for the gate record.

— oscar-mtt8m47c, 2026-09-10
