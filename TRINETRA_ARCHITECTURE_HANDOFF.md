# TRINETRA — V3 (Light Theme + Gap Closure) Architecture Handoff

**Reviewer:** architect-mtt8l8dh · **Date:** 2026-09-09 · **Input:** TRINETRA_IMPLEMENTATION_PLAN.md (260 lines)
**Verdict: APPROVED** — with the binding corrections below. No blockers. The plan respects frozen
boundaries (MJPEG authoritative, no second detector/tracker, additive-only backend, no new deps);
its two factual errors are staleness, not design flaws.

---

## 1. Tree verification vs plan claims (what I checked in code)

| Plan claim | Verified reality | Consequence |
|---|---|---|
| G1: build BROKEN — `Settings` import missing, GeoMap no-`new`, 13 tsc errors | **STALE/FALSE for this tree.** `frontend/src/pages/Settings.tsx` EXISTS and is wired (`App.tsx:13,26,46`); GeoMap calls `new maps.Map/Marker/Polygon` (`GeoMap.tsx:69,127,164`); `mapTypes.ts:52-85` has `GSymbolPath`, `GEvent`, `MapTypeId`; `npx tsc --noEmit` → **0 errors** | T0.1 re-scopes to *verify + restructure* (see C1). Deletion of Settings is now a real deletion, not a broken-import fix |
| "195 pass / 4 skip" gate | `pytest --collect-only` = **207 tests** (V2's `test_v2_sources.py` added 12) | Test gate is "full suite green at ≥ current count + new tests, 4 skips unchanged" (C9) |
| annotate signature `annotate(frame, objects, pipeline_fps, device, zones)` | Confirmed (`annotation.py:80-84`) | Additive `layers`/`trajectories` kwargs are backward-compatible; M3 (`test_m3_units.py:29-67`) + M7 (`test_m7_geo.py:208-237`) call sites unaffected |
| No per-class counts | Confirmed — `status_payload()` (`session.py:414-428`) has `active_tracks`/`total_tracks` only; `TrackStore.count_active(class_name)` exists (`tracks.py:202-207`) | T1.1 shape below (C5) |
| Trajectories never rendered; `positions` = 60-pt deque | Confirmed — `TrackState.positions: deque[(x, y, tick)]` (`tracks.py:51-55, 72-80`) — **3-tuples** | Contract pinned in C4 (session converts to pixel 2-tuples) |
| Session never passes zones to annotate | Confirmed — `_annotate()` (`session.py:205-214`) passes fps/device only; comment says zone overlay is client-canvas | T1.3 wiring is the intended M7 completion; see C2 (single-renderer rule) |
| Dark palette audit | Confirmed 10 literal hits (`#0b0f14|#11161d|#3ddc97`) in tailwind.config.js, index.css, GeoMap schematic/marker strokes; favicon uses URL-encoded `%233ddc97` (not in that count); no `dark:` variants anywhere in src | T0.2/T0.3 sufficient; favicon + `darkMode:'class'` cleanup noted (C10) |
| Endpoints sufficient for all 7 pages | Confirmed — events keyset (`events.py:43-71`, C8 pair cursor), zones CRUD per-source (`zones.py:79-133`), map cameras registry incl. lat/lng/status/type/label (`map.py:81-108`), sources scan/upload/list (`sources.py:53-182`), sessions history + tracks (`sources.py:162,182`) | **No missing contracts.** Event Log / Cameras / Alerts pages need zero backend change |

## 2. Binding corrections (numbered — executor1 must follow)

**C1 — Re-scope T0.1 (G1 is stale).** The tree already builds clean. T0.1 becomes:
(a) verify `tsc --noEmit` + `vite build` clean (re-prove, don't trust the report), (b) restructure nav per
G15 — this now means DELETING the working `Settings.tsx` + its import/nav/`Page`-union entry
(`App.tsx:13,26,46`, `store.ts:12-14`). Only `App.tsx` imports Settings (grep-verified). Keep the
detector/model status info somewhere honest (a panel on Live View or footer) rather than losing it —
its facts are real.

**C2 — Single zone renderer (server-side authoritative).** T1.3 wires `zones=` into the session's
annotate call with default `zones: True`. That means zones are burned into the MJPEG **and** evidence
(desired: demo steps 12/17 — fence visible in snapshot). The client-canvas zone overlay in
`LiveFeed.tsx:21-64` then DOUBLE-DRAWS the same normalized geometry. Binding: the *existing-zones*
canvas draw in LiveFeed is REMOVED once server-side layers.zones is live; the Virtual Fence toggle
controls the server layer only. Keep the zone EDITOR's own draw-preview (`VideoZones.tsx`) — that is
authoring UX, not a second renderer. Note honestly: this default flips today's stream appearance
(currently no server-drawn zones) — intended M7 completion, must be stated in the commit message, not
smuggled.

**C3 — `_layers` state must be torn-frame-safe.** POST /api/session/layers mutates session state from
the API thread; the render thread reads it every tick. A multi-key `dict.update()` can interleave into
a half-applied frame. Binding: store layers as an immutable dict and swap atomically under a small
`threading.Lock` (`self._layers = {**self._layers, **valid_updates}`); render thread reads the
reference once per tick. No torn frames, no locks held across annotate.

**C4 — annotate() contract pinned (this hunk is GOD-ROUTED — see §5).**
`annotate(frame, objects, pipeline_fps=None, device="", zones=None, layers=None, trajectories=None)`:
- `layers: {"boxes": bool=True, "labels": bool=True, "fps": bool=True}` — partial-tolerant (missing
  key = default True). `boxes` gates rectangles AND the label chip; `labels` gates ONLY the `| ID n`
  suffix (class+conf text stays — that is the "Track IDs" toggle); `fps` gates the HUD text.
- `trajectories: {track_id: [(x, y), ...]}` — PIXEL foot-point 2-tuples. The session converts from
  `TrackState.positions` 3-tuples: `[(x, y) for x, y, _tick in t.positions]` (deque is (x, y, tick) —
  `tracks.py:72-80`). Draw thin polyline (thickness 2, dim class color), skip empty lists, never raise
  on malformed input (same degrade discipline as `_draw_zone`).
- Defaults (`layers=None`, `trajectories=None`, `zones=None`) reproduce the M3/M7 frozen surface
  byte-identically — existing tests untouched.

**C5 — Per-class counts: no dict-iteration race.** `status_payload()` runs on the API thread while the
session thread inserts track keys; a Python-level `for` over `self._store.tracks` can raise
"dictionary changed size during iteration" (GIL does not save you). This race already exists for
`count_active()` — T1.1 multiplies it. Binding: take one atomic snapshot
`tracks = dict(self._store.tracks)` (C-level copy is GIL-atomic) and compute all four counts from it;
or maintain increment counters in the session thread. Semantics pinned: `people_detected` /
`vehicles_detected` = cumulative unique tracks whose CURRENT `class_name` == "person" / in
`_VEHICLE_CLASSES` (`session.py:65` — reuse, never duplicate the set in frontend, plan risk 6
endorsed); `active_people` / `active_vehicles` via `count_active(class_name)` sums over the snapshot.
Zero when zero. Keys additive only.

**C6 — EventSummary zone-name resolution.** `EventRow` carries `zone_id` (uuid), NOT the zone name.
The template sentence "zone South Band" must resolve `zone_id → name` from the already-loaded
`store.zones` (`/api/zones` ZoneRow). Deleted zone → render the raw `zone_id` or omit the clause —
never fabricate a name. All other template fields (`direction`, `severity_reason`, `track_ids`) are
real row fields (verified in `engine.py:84-89`). Zero-fabrication rule endorsed; empty DB → empty state.

**C7 — main.py edit boundary.** Executor1 may ADD the two layers route defs **inline in the
session-endpoints region** (`main.py:115-171`, next to start/stop/status). It must NOT: create a new
router file (would require an include line in the M7 hunk at `main.py:50-56`), touch the include block,
lifespan, or `_DIST` mount (`main.py:263-267`). No new router = no include churn.

**C8 — Executor2-owned files untouched by executor1.** `backend/api/map.py`,
`backend/db/migrations.py`, `backend/db/dao.py`, `backend/vision/annotation.py` are executor2's M7
surface — verified none of them need changes for this sprint: T2.3's camera registry is fully served
by `/api/map/cameras` (id/label/type/status/lat/lng — `map.py:81-108`) + `/api/sources`. Any
perceived need to edit those files stops work and goes to god.

**C9 — Test gate (updated counts).** Gate = full suite green at **current collected count (207)** plus
new additive tests (`tests/test_layers.py`); 4 skips unchanged; 2 warnings unchanged; no existing
test file modified (additive kwargs make it unnecessary — plan risk 2's "extend a pinned test" path
should NOT trigger; if executor1 thinks it must, that goes to god first). Frontend gate = `tsc
--noEmit` + `vite build` clean, no console errors (Playwright).

**C10 — Token-swap completeness (minor adds).** Also: favicon stroke `%233ddc97` in `index.html:8`
→ light accent; `darkMode: 'class'` in tailwind.config can be dropped with the `class="dark"`
(`index.html:2`); GeoMap Google-marker strokes `#0b0f14` (`GeoMap.tsx:123,136`) → `#FFFFFF`.
Video-surface colors (LiveFeed canvas/overlay chips on the black video well, `LiveFeed.tsx:44,124`)
may stay bright — they sit on video, not page chrome (plan risk 7 endorsed).

## 3. Pinned API shapes (new/modified — all additive)

```
POST /api/session/layers            # no active session → 404 {"detail": "no active session"}
  req : {"boxes"?: bool, "labels"?: bool, "fps"?: bool,
         "trajectories"?: bool, "zones"?: bool}        # partial merge; UNKNOWN key → 400
  resp: {"layers": {"boxes": b, "labels": b, "fps": b,
                    "trajectories": b, "zones": b}}
GET  /api/session/layers            # 404 when no session; 200 shape above
```
Unknown-key 400 is binding: a typo'd toggle silently ignored = a dead control (violates the
no-dead-controls rule). Session defaults:
`{"boxes": true, "labels": true, "fps": true, "trajectories": false, "zones": true}` —
trajectories OFF default preserves today's rendering; zones ON default is the intended C2 change.

```
GET /api/session/status  (modified — 4 additive keys, nothing removed/renamed)
  + "people_detected": int, "vehicles_detected": int,
    "active_people": int, "active_vehicles": int
```

```
annotate() — see C4. No other endpoint signatures change (events/zones/map/sources/SSE/MJPEG
verified untouched by this plan).
```

## 4. Specific review answers (god's 8 points)

1. **Boundaries** — PASS. Frontend never draws detections (MJPEG authoritative; C2 even removes the
   client zone overlay in favor of the server). No second tracker/detector. Endpoints additive (C7).
   Dep count goes DOWN (@visactor removal; grep-verified unused by planner, re-verify at deletion).
2. **Layers API** — design sound with C3 (atomic swap) + C4 (pinned contract) + C7 (placement).
   Backward compat with the M5 evidence path: evidence JPEG IS the slot JPEG (one render) — toggles
   affecting evidence is a documented accepted trade-off (plan risk 3 endorsed; second render pass
   correctly REJECTED — re-encode cost + A1 violation). SSE/MJPEG untouched.
3. **Trajectory/fence rendering** — bandwidth-sane (burned pixels, no extra payloads); frame-time
   negligible (cv2.polylines µs-scale vs 25ms inference; FPS-drop <5% acceptance endorsed); graceful
   on empty (skip empty lists, C4). Zone fetch per tick already exists in the session (M6 C2 per-tick
   zone-diff) — reuse that ZoneStore access; convert to §12 normalized dicts as `test_m7_geo.py:221`
   shows.
4. **Per-class counts** — source of truth = session loop state via `status_payload` (C5), not client
   aggregation; no writer interaction (status is read-path). Snapshot-copy kills the API-thread/
   session-thread dict race (C5).
5. **EventSummary** — deterministic, frontend-only, DAO-fed via existing `/api/events`; no LLM; C6
   fixes the one field that ISN'T in the row (zone name). Empty-DB handled.
6. **Light theme** — token swap is sufficient (no `dark:` variants exist — verified); schematic
   light variant specced; behavior changes are phase-separated (P0 theme vs P1 backend) — keep them
   in separate commits where the plan already separates them; C2's zones-default flip must be called
   out in its commit message.
7. **7-page contracts** — verified sufficient; zero missing/changed contracts beyond §3. Client-side
   type/source filters (G10) and windowed "Active Alerts" count are honest at demo scale (advisory:
   the alerts card counts within the loaded event window; fine unless >500 unacked — don't present
   as global truth in copy, e.g. label it "unacked (latest 500)" if paranoid).
8. **Test surface** — 207 collected today (not 195 — plan stale); C9 is the gate. No signature
   changes anywhere; only additions.

## 5. Executor1 boundary — routing table

| Work | Owner | Channel |
|---|---|---|
| `frontend/**` (build fix verify, theme, pages, toggles UI, EventSummary, EventLog) | executor1 | direct |
| `backend/services/session.py` (per-class snapshot counts, `_layers` state, `_annotate` wiring, zone-dict conversion) | executor1 | direct — NOT an executor2 file |
| `backend/main.py` layers routes — inline, session-endpoints region ONLY (C7) | executor1 | direct |
| `tests/test_layers.py` + any new status-field tests | executor1 | direct |
| **`backend/vision/annotation.py`** — `layers`/`trajectories` kwargs (C4, ~25 lines) | **executor2/god** | **GOD-ROUTED** — executor1 must NOT edit this file |
| `backend/api/map.py`, `backend/db/dao.py`, `backend/db/migrations.py` | executor2 | untouched this sprint (C8) |

**Sequencing (god):** the annotation.py hunk must land FIRST (or in the same commit) — executor1's
`test_layers.py` annotate-units and the session wiring depend on the new signature. A 25-line
god-executed/executor2 micro-dispatch unblocks the whole P1 backend. Recommend god lands it before
or alongside executor1's start.

## 6. Endorsements (no action needed — recorded for the record)

Plan risks 3 (shared-JPEG), 4 (trajectory cost), 5 (no webcam — never fake), 6 (single class-set
source), 7 (video-surface colors), 8 (Maps key discipline), 10 (one active session) — all correct
and binding as written. Risk 1 (doc/code drift, code = truth, re-prove everything with Playwright)
is the sprint's operating rule. Risk 2's fallback (extending a frozen test) should NOT trigger —
if it seems to, escalate to god before editing any existing test.

**Final state required at sprint close:** suite green ≥207+new (4S/2W unchanged) · `tsc && vite
build` clean · light theme verified by Playwright screenshots (no `#0b0f14|#11161d|#3ddc97` in page
chrome) · toggles verifiably change the rendered stream (network-tab real) · every UI number traces
to an API field (fake-widget ban upheld) · zero-when-zero everywhere.
