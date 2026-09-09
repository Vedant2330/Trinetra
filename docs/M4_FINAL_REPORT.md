# M4 — VIRTUAL FENCE: FINAL REPORT

STATUS: **PASS**

## STATUS
M4 implemented, tested, independently reviewed, committed (`039cbc2`). Suite: **105 passed / 4 skipped / 0 failed** (52 new M4 tests; skips = 4 pre-existing webcam-marker honest skips). Verified by three independent executions: executer, god, Oscar.

## WHAT WAS IMPLEMENTED
- `backend/analytics/geometry.py` — pure geometry: ray-cast point-in-polygon (concave-safe, on-edge deterministic = inside), segments_intersect (proper/touching/collinear-overlap), cross-product side-sign (±1/0 @ 1e-9), validators (reject <3-pt polygon, p1≈p2 line @ 1e-3, coords outside [0,1], NaN/inf).
- `backend/analytics/fence.py` — FenceAnalytic: per-(track,zone) occupancy {inside, confirm_counter, grace_counter}; ZONE_ENTRY after 3 consecutive inside (one outside resets), ZONE_EXIT after 10 outside; tripwire crossing = consecutive foot points on opposite side-signs AND trajectory-segment × line intersection (zero/touch/collinear = no event); direction from cross-product sign; direction_mode both|forward|reverse; structural dedup (no draft while state unchanged); confidence=1.0 rule-based; per-zone person counts byproduct; absent-track rule (missing = outside for grace-advance, no exit without prior confirmed entry, reappear-in-grace resumes without second entry, new ID = fresh).
- `backend/analytics/zones.py` — ZoneStore in-memory seam (M5 swaps backing to SQLite §14). Zone: id/source_id/name/kind(polygon|line)/type(WATCH|RESTRICTED — lines get type too)/geometry §12 JSON/active. direction_mode validated.
- `backend/analytics/base.py` — FrameContext (tick/wall_ts/video_ts/luminance/is_night/shape §4), EventDraft (metadata carries is_night + zone_type + direction_mode + zone_kind + tick/video_ts/luminance — M5's only seam), AnalyticModule ABC (§11).
- `backend/state/tracks.py` — positions deque now stores FOOT points (cx, y2) per §7 FROZEN; `foot_point` + `center` properties; TrackView read-only facade (active_tracks = tracks present at current tick — fixes stale-foot-point hazard; get, tick) + TrackStore.view().
- `backend/services/session.py` — FrameContext build (luminance = mean gray, is_night < 40 named constant), analytics chain [FenceAnalytic] inline on session thread (no new threads/locks), bounded drafts list (_MAX_DRAFTS=500 drop-oldest), status_payload additive: drafts_count + zone_person_counts.

## ARCHITECTURE
- §3 pipeline order preserved: read → detect+track → state.update → FrameContext (step 3) → analytics chain (step 6) → annotate (step 7) → JPEG → slot.
- ByteTrack sole ID authority — no ID generation in analytics (Oscar grep-verified). TrackStore passive. Analytics read via TrackView only (§11).
- One detection path, one YOLO call/frame; analytics import config only.
- Normalized [0,1] coords end-to-end (§12); resolution-independence proven at 640×360 vs 1920×1080.

## FILES CREATED
backend/analytics/{__init__,base,geometry,fence,zones}.py · tests/test_m4_{geometry,fence,integration}.py · docs/ADR-001-milestone-resplit.md · docs/M4_FINAL_REPORT.md

## FILES MODIFIED
backend/state/tracks.py · backend/state/__init__.py · backend/services/session.py

## FILES NOT MODIFIED (protected contracts intact)
vision/tracker.py (M2 authority, warm-up predict()) · sources/* (M1) · vision/annotation.py (M3) · main.py session/MJPEG endpoints (409 lock intact) · config/default.toml · all M0–M3 tests.

## DEPENDENCIES
None added (stdlib + cv2 already in stack).

## TESTS EXECUTED
- `venv/bin/python -m pytest -q` — executed 3× (executer, god, Oscar): 105P/4S/0F each run.

## ACTUAL TEST RESULTS
105 passed, 4 skipped, 0 failed (13.4s, 12.75s, 13.2s respectively). M4 adds 52: geometry 25*, fence 24, integration 3. (*executer reported 20 in --collect-only; 25 in file — Oscar verified 52 total.)

## INTEGRATION RESULTS
Real pipeline (FileSource running_clip.mp4 → DetectorTracker → TrackStore → FenceAnalytic, synthetic zone): ≥1 ZONE_ENTRY from real detections, 0 duplicate entries per occupancy cycle, stable IDs, foot_point == bbox bottom verified. Session-level e2e: completed, drafts_count=1, zone_person_counts live. MEASURED luminance cost: median 0.149–0.153 ms (gate <3 ms) — ~20× under.

## PERFORMANCE
Measured (not estimated): luminance/FrameContext ~0.15 ms/frame; chain inline, no new threads. B1 headroom preserved.

## BUGS FOUND AND FIXED
1. Stale foot points: TrackStore keeps absent-but-not-lost tracks active; naive view would feed stale positions to fence (a disappeared track could still 'confirm'). Fixed: TrackView.active_tracks exposes only tracks with last_tick == current tick; absence handling stays in FenceAnalytic.
2. Sign-convention + absent-track edge bugs during TDD (executer; root-cause fixes, converged green).

## KNOWN LIMITATIONS (documented, non-blocking — Oscar findings)
1. Tripwire prev-point state survives long absences (≤30-tick store window) → one crossing whose segment spans the absence. Fix parked for M5 (~5 lines).
2. Occupancy keyed (track,zone) persists across zone deactivate/reactivate → suppressed re-entry; unreachable until M5 CRUD lands — bound into M5 acceptance.
3. zone_person_counts is occupancy-derived (grace window keeps counts up to 10 ticks) — documented behavior, matches §12.
4. _MAX_DRAFTS pop(0) O(n) — trivial at MVP scale; M5 engine replaces the list.
5. Non-numeric coords raise bare ValueError instead of typed error — M5 CRUD maps both to 4xx.
6. Fast mover skipping a small zone between ticks → no zone events (PIP is per-observed-frame) — frozen-design limitation, documented in test; line crossings between ticks ARE detected.

## ARCHITECTURAL NOTES
Milestone re-split documented in docs/ADR-001-milestone-resplit.md (M4 = fence only; DB/SSE/engine/CRUD/UI → M5–M7; G2 items relocated, none dropped). Oscar's verdict: PASS, no ADR needed for the implementation itself.

## SUCCESS CRITERIA SCORECARD
[✓] Real tracked movement processed by fence logic (integration, real video)
[✓] Zone logic (confirm/grace/dedup — exact-boundary tests)
[✓] Tripwire logic (side-sign + segment intersection; vertical-line non-Y-threshold proof)
[✓] Direction (cross-product, both/forward/reverse matrix)
[✓] Debounce prevents spam (flapping → 0; state-unchanged → 0)
[✓] Unit tests (52)
[✓] Integration tests (real pipeline)
[✓] Existing tests green (105P/4S, none weakened)
[✓] Honest reporting (3 independent suite runs)

## COMMIT
`039cbc2` — 11 files, +1649/−10. Tree clean.

## NEXT CHECKPOINT
M5 — EVENT ENGINE: per ARCHITECTURE §13–§16 (EventEngine commit/dedup-backstop/severity+severity_reason/snapshot gating ≥MEDIUM, SQLite direct sqlite3 + WAL + migrations + writer thread, 6-table schema §14, zones CRUD + events query/ack + evidence serving, SSE /api/stream/events, session loop step 8 integration, zone-drawing on annotated frames, Oscar findings 1/2/5 bound in). Automatically continuing: planner re-dispatch for M5 decomposition next (single-flight sequence restarts: PLANNER → ARCHITECT → EXECUTER → OSCAR).
