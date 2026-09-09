# TRINETRA — GAP-CLOSURE + LIGHT-THEME IMPLEMENTATION PLAN

Planner: generated 2026-09-09 from a full READ-ONLY inspection of the repo.
Executor: EXECUTOR1. Scope: gap closure + UI restyle ONLY. The CV pipeline,
events engine, DB, SSE, MJPEG, and map integration EXIST and are verified
(195 pytest pass) — nothing here rebuilds them.

---

## 1. EXECUTIVE SUMMARY

The backend is demo-ready: sources (webcam + uploaded file), YOLOv8n +
ByteTrack, video zones/fence with true geometry, event engine with
severity/cooldown/evidence, SQLite persistence, SSE, MJPEG, Google Maps with
schematic fallback, and a camera/geo registry are all real and tested. The
frontend command center exists with real-data wiring everywhere, BUT it is
currently in three states the milestone reports do not reflect: (1) the
TypeScript build is BROKEN — `App.tsx` imports a nonexistent `Settings` page
and `GeoMap.tsx` has regressed to calling Google Maps constructors without
`new` (the exact bug M7_REPORT claims was fixed); (2) the UI is a dark
"cyberpunk-adjacent" slate theme, while the target is a LIGHT professional
command-center theme; (3) several target surfaces are missing — analytics
layer toggles (Detections/Track IDs/Trajectories/FPS/Virtual Fence), an
AI/event summary, an Event Log table, and a spec-shaped Command Center
(header subtitle, 4 summary cards, live-alerts side panel). This plan fixes
the build first, restyles to light, restructures pages to the target
spec, and adds the one backend surface genuinely required (server-side
render-layer toggles + per-class detection counts in the status payload).
No new dependencies, no schema changes, all backend edits additive so the
195-test suite stays green.

---

## 2. GAP ANALYSIS

| # | Area | Current state (file refs) | Target | Gap size | Phase |
|---|------|---------------------------|--------|----------|-------|
| G1 | Build integrity | `frontend/src/App.tsx:13` imports `./pages/Settings` — FILE DOES NOT EXIST (TS2307). `npx tsc --noEmit` fails: 13 errors. `GeoMap.tsx:66,119,151` calls `maps.Map/Marker/Polygon` WITHOUT `new` against constructor-typed shims (`mapTypes.ts:44,50,57`); `GeoMap.tsx:71,98,125,133` uses `MapTypeId/SymbolPath/AddListener` missing from the `GMaps` interface. `Dashboard.tsx:14,17,39` unused locals fail `noUnusedLocals`. The M7 report claims these were fixed — the fixes are NOT in the tree. | Clean `tsc -b && vite build` | BLOCKER | **P0** |
| G2 | Theme | Dark slate palette baked into `tailwind.config.js:8-19` (`cc.bg #0b0f14`, panels `#11161d`, neon accent `#3ddc97`), `index.css:5-15` (dark body, dark scrollbars, dark sev chips), `index.html:2` (`class="dark"`), hardcoded dark colors in `GeoMap.tsx` schematic (lines 22-27, 242-287: `#0e141b` bg, `#1f2833` grid, `strokeColor '#0b0f14'` markers) | LIGHT professional theme: white/off-white bg, near-black text, restrained green/red/orange/blue accents, rounded cards, subtle borders/shadows | LARGE (mechanical) | **P0** |
| G3 | Header | `App.tsx:55-80`: "TRINETRA COMMAND CENTER", NOMINAL/DEGRADED health text, clock (ok) | "TRINETRA" + "Intelligent Border Video Analytics Platform" + System ONLINE/OFFLINE + timestamp | Small | **P0** |
| G4 | Command Center structure | `Dashboard.tsx`: 8 mixed metric cards; primary row = LiveFeed + GeoMap; right rail = SessionControl + CameraStatus + EventTimeline; second row = EventDetail + Zone Occupancy | 4 summary cards (People Detected, Vehicles Detected, Active Alerts, System Status); main = LIVE CAMERA; side = LIVE ALERTS; below = ALERTS SUMMARY + AI/EVENT SUMMARY | Medium (rearrange, all data exists) | **P0/P1** |
| G5 | People/Vehicles counts | `Dashboard.tsx:26-31` counts PERSON/VEHICLE_DETECTED events in the client-side 500-event window — undercounts (windowed), not true session state | Real session-level counts, zero when zero — requires per-class counts in `status_payload()` (`backend/services/session.py:414-428` has `active_tracks`/`total_tracks` only; `TrackStore.count_active(class)` exists at `state/tracks.py:202`) | Small backend addition | **P1** |
| G6 | Analytics layer toggles | NOTHING exists. `backend/vision/annotation.py:80-124` always draws boxes+labels+FPS HUD (no flags); `session.py:205-214` never passes zones/trajectories; trajectories live in `TrackState.positions` (`tracks.py:51`) but are NEVER rendered anywhere; zone overlay is client-canvas only (`LiveFeed.tsx:21-64`) | Detections / Track IDs / Trajectories / Virtual Fence / FPS toggles that ACTUALLY change the rendered stream | Backend flags + endpoint + UI | **P1** |
| G7 | Live View page | `Cameras.tsx`: feed + camera grid + SourcePicker. Upload/webcam scan/start/stop all EXIST (`SourcePicker.tsx`, `backend/api/sources.py:53-117`). No stats strip, no layer toggles | Live View to spec: source UX + stats + toggles | Medium | **P1** |
| G8 | Analytics page | `Analytics.tsx`: real event-log charts (severity/type/hour) — good, but NO runtime info (people/vehicles/tracks/FPS/fence status/trajectory info), no working visualization controls | Runtime info panel + controls that work | Medium | **P1** |
| G9 | AI/Event Summary | DOES NOT EXIST anywhere. Note: "M6 advisories" (`tests/test_m6_advisories.py`) are HARDENING DRILLS — there is NO advisory/narrative generator in the backend (grep-verified). Per-event `severity_reason` metadata exists (`events/engine.py`) | Deterministic summary surface built ONLY from real `EventRow` fields — frontend-only, no invented facts | New component | **P1** |
| G10 | Alerts page | `Events.tsx`: severity filter + keyset pagination + SSE/REST merge (good base). NO event-type or source filters, NO timestamp filter | Filters by severity, type, source, time (where practical) | Small-Medium | **P2** |
| G11 | Event Log page | `Events.tsx` is a timeline list, NOT a table. No Event ID / Metadata columns, no search | Table: Event ID, Time, Source, Type, Severity, Track ID, Metadata + search | New page/view | **P2** |
| G12 | Camera Management | `Sources.tsx` = source registry (ID/Type/Status/Registered) + honest RTSP panel; `Cameras.tsx` grid shows live frame. Map API already serves name/label/type/lat/lng/status (`api/map.py:81-108`) | Registry with camera_id, name, source, source_type, status, latitude, longitude, location; LIVE only when running (already honest) | Small (mostly presentation) | **P2** |
| G13 | Map | `GeoMap.tsx` + `mapLoader.ts` + `api/map.py`: full chain (satellite→roadmap→schematic), markers, sectors, selection, graceful degrade — EXISTS, needs light-mode schematic + selection UX polish + the G1 constructor fix | Keep; polish only | Small | **P0 (fix) / P2 (polish)** |
| G14 | Future features | `SessionControl.tsx:57-62` has honest disabled PAUSE/RESTART; `App.tsx:105-108` "HERMES — NOT CONNECTED"; `Sources.tsx:69-75` honest RTSP panel. No consolidated COMING SOON surface for Pose/Face/ANPR/Re-ID/Behavior | Disabled placeholders with clear labels, no dead buttons | Small | **P3** |
| G15 | Nav/page naming | Nav: Dashboard/Cameras/Events/Investigation/Geography/Analytics/Sources/(Settings→broken) | Command Center / Live View / Alerts / Event Log / Investigation / Map / Analytics / Cameras. Settings REMOVED (broken import) | Small | **P0 (rename in P0, pages land P1/P2)** |
| G16 | Dead dependency | `frontend/package.json:12` ships `@visactor/react-vchart` — used NOWHERE (grep: 0 hits) | Remove (bundle hygiene) | Trivial | **P3** |
| G17 | Video upload | EXISTS and probe-validated: `POST /api/sources/upload` (`sources.py:72-117`) + XHR progress UI (`SourcePicker.tsx:44-55`, `api.ts:80-98`) | Keep — no gap | NONE | — |

---

## 3. PHASED TASK LIST

### P0 — BUILD FIX + LIGHT THEME + COMMAND CENTER STRUCTURE

**T0.1 — Fix the broken frontend build** (BLOCKER, do first)
- Files: `frontend/src/App.tsx`, `frontend/src/components/GeoMap.tsx`, `frontend/src/mapTypes.ts`, `frontend/src/pages/Dashboard.tsx`
- Changes:
  - Remove the `./pages/Settings` import, the `settings` nav entry, and `settings` from the `Page` union (`store.ts:12-14`) and page map (`App.tsx:43-47`).
  - `GeoMap.tsx`: call `new maps.Map(...)`, `new maps.Marker(...)`, `new maps.Polygon(...)` (constructor-typed shims already demand it — `mapTypes.ts:44,50,57`).
  - `mapTypes.ts`: add `MapTypeId: { SATELLITE; ROADMAP; ... }`, `SymbolPath: { CIRCLE: number }`, and `AddListener(target, ev, cb)` to the `GMaps` interface so `GeoMap.tsx:71,125,133` type-check.
  - `Dashboard.tsx`: delete unused `VEHICLE_CLASSES`, `health`, `occupiedZones` (or use them where T0.5 needs them).
- Acceptance: `cd frontend && npx tsc --noEmit` → 0 errors; `npm run build` succeeds; app boots at `http://localhost:8000/` with no console errors (Playwright smoke).
- Dependencies: none.

**T0.2 — Light theme tokens**
- Files: `frontend/tailwind.config.js`, `frontend/src/index.css`, `frontend/index.html`
- Changes (redefine the SAME `cc-*` names so component churn stays minimal):
  - `tailwind.config.js` palette: `bg #F6F7F9` (app background), `panel #FFFFFF`, `panel2 #F2F4F6` (light-gray secondary surface), `line #E3E7EB`, `text #101418` (near-black), `dim #5C6672`, `accent #16A34A` (GREEN online/healthy), `red #DC2626` (critical/intrusion), `amber #D97706` (warning), `blue #2563EB` (informational). Keep `fontFamily.mono`.
  - `index.css`: `html, body, #root { background:#F6F7F9; color:#101418; }`; scrollbar thumb `#C9CFD6` (hover `#B4BCC5`), track transparent; sev chips light-mode: `.sev-INFO { color:#5C6672; border-color:#E3E7EB }`, `.sev-LOW { color:#2563EB }`, `.sev-MEDIUM { color:#D97706; border-color:#D97706 }`, `.sev-HIGH { color:#DC2626; border-color:#DC2626 }`.
  - `index.html`: drop `class="dark"`.
- Acceptance: computed background of the app root is `#F6F7F9`; primary text `#101418`; `rg "#0b0f14|#11161d|#3ddc97" frontend/src frontend/tailwind.config.js` → 0 hits (video surfaces may keep true black).
- Dependencies: none.

**T0.3 — UI kit restyle (ui.tsx + shared surfaces)**
- Files: `frontend/src/components/ui.tsx`, `frontend/src/App.tsx` (nav/footer/header chrome), `GeoMap.tsx` (schematic colors)
- Changes:
  - `Panel`: white bg, `border-cc-line`, `rounded-lg`, `shadow-sm` (subtle), keep header divider.
  - `Metric`/cards: `bg-white border-cc-line rounded-lg shadow-sm`; warn value stays `text-cc-red`.
  - `Pill`/`StatusDot`/`SevChip`: same tones, light-mode borders (they inherit the new palette — mostly free).
  - `GeoMap.tsx` schematic: background `#E9EDF1`, grid `#D8DEE4`, labels `#5C6672`, marker stroke `#FFFFFF`, note badge `bg-white/80 text-cc-dim`; Google marker `strokeColor: '#FFFFFF'` (line 128).
  - App shell: nav/footer/header already use `cc-*` tokens — verify contrast; the LiveFeed video backdrop (`bg-black`, `LiveFeed.tsx:88`) STAYS black (it is the video well).
- Acceptance: no panel/card uses a dark surface; severity colors still read at a glance; Playwright screenshot review (light, professional, no neon).
- Dependencies: T0.2.

**T0.4 — Header to spec**
- Files: `frontend/src/App.tsx`
- Changes: brand block becomes `TRINETRA` (bold) + subtitle `Intelligent Border Video Analytics Platform`; replace `NOMINAL/DEGRADED/NO BACKEND` with a `SYSTEM ONLINE` pill (green, when `health?.ok`) / `SYSTEM OFFLINE` (red) / `CONNECTING` (dim, while null); keep the SSE/session pills, unacked count, and the 1s clock (already exists via `store.clock`).
- Acceptance: header renders exactly `TRINETRA`, `Intelligent Border Video Analytics Platform`, `SYSTEM ONLINE`, and a live timestamp when the backend is up; `SYSTEM OFFLINE` when the backend is down (stop uvicorn to verify).
- Dependencies: T0.2 (tokens).

**T0.5 — Command Center page structure (Dashboard)**
- Files: `frontend/src/pages/Dashboard.tsx` (+ reuse `LiveFeed`, `EventTimeline`, `EventDetail`)
- Changes:
  - Top: exactly 4 summary cards — **People Detected**, **Vehicles Detected** (interim: current event-derived counts; replaced by T1.2), **Active Alerts** (= unacked `status==='new'` count, exists), **System Status** (ONLINE/OFFLINE + uptime, from `health`).
  - Main area (largest): `LiveFeed` (real MJPEG) with compact stat overlay (frames/fps/tracks — already exists).
  - Side panel: **LIVE ALERTS** — `EventTimeline` (real SSE rows already carry type, timestamp, source, track ID, severity).
  - Below main: **ALERTS SUMMARY** — counts by severity from the loaded real event rows (reuse the `Stat` pattern from `Analytics.tsx`); "no alerts — zero events" empty state when zero.
  - Move GeoMap off the Command Center primary row (Map stays its own page per spec; keeps the page uncluttered). Keep EventDetail as the select-target.
- Acceptance: with no session and no events all four cards read `0`/OFFLINE truthfully; starting a session flips cards within one 5s poll; an SSE ZONE_ENTRY appears in LIVE ALERTS ≤2s and increments Active Alerts; layout = header / 4 cards / live camera + alerts rail / alerts summary.
- Dependencies: T0.1–T0.4.

### P1 — LIVE VIEW, ANALYTICS RUNTIME, AI/EVENT SUMMARY

**T1.1 — Backend: per-class counts in status payload** (additive only)
- Files: `backend/services/session.py` (`status_payload`, `_stats_payload`)
- Changes: add `people_detected`, `vehicles_detected` (cumulative unique tracks per class over `self._store.tracks` using the existing `_VEHICLE_CLASSES` set), and `active_people`, `active_vehicles` (via `TrackStore.count_active(class_name)`, `tracks.py:202`). Keys are ADDITIVE — nothing removed.
- Acceptance: `pytest -q` still 195 pass / 4 skip; `GET /api/session/status` during a `running_clip.mp4` session shows `people_detected > 0`; with no session `{active:false}` unchanged.
- Dependencies: none.

**T1.2 — Command Center cards consume real session counts**
- Files: `frontend/src/pages/Dashboard.tsx`, `frontend/src/types.ts` (add the 4 fields to `SessionPayload`)
- Changes: People/Vehicles cards read `session.people_detected` / `session.vehicles_detected` (0 when no session).
- Acceptance: card values equal `status_payload` numbers verbatim; zero when zero.
- Dependencies: T1.1, T0.5.

**T1.3 — Backend: render-layer toggles + trajectories + fence-in-evidence**
- Files: `backend/vision/annotation.py`, `backend/services/session.py`, `backend/main.py` (or a small `backend/api/session.py`), one new test file `tests/test_layers.py`
- Changes (all additive; defaults preserve current behavior byte-for-byte):
  - `annotate(..., layers: Optional[dict] = None, trajectories: Optional[dict[int, list[tuple]]] = None)` — `layers` keys `boxes` (default True), `labels` (track-ID part, default True), `fps` (HUD, default True); `trajectories` maps track_id → foot-point history; when a layer is off, that element is simply not drawn. Existing call sites unchanged (kwargs optional).
  - `ProcessingSession`: `self._layers = {"boxes": True, "labels": True, "fps": True, "trajectories": False, "zones": True}`; loop passes `layers=self._layers`, `trajectories={tid: list(t.positions) for active tracks}` (positions already retained, `history_len=60`), and `zones=<active zones for this source from the ZoneStore>` so evidence snapshots show the breached fence (the M7 `annotate(zones=)` capability that the session never wired up).
  - `POST /api/session/layers` body `{boxes?, labels?, fps?, trajectories?, zones?}` → merge + return current layers; `GET /api/session/layers` returns current; 404 with clear message when no active session.
- Acceptance: new pytest — start stub session, POST layers `{boxes: false}`, next rendered frame has no rectangles (assert via annotate unit test + endpoint 404-without-session); defaults keep all M3/M4/M5 tests green (195 total unchanged); trajectories ON draws polylines (unit test on `annotate` output shape is acceptable: verify no-raise + cv2 calls via monkeypatch, keep honest).
- Dependencies: none (parallel with T1.1).
- NOTE: the shared-JPEG rule (A1: snapshot == operator frame) means toggles affect evidence too. Defaults are all-ON so the demo is unaffected; documented in Risks.

**T1.4 — Live View page (Cameras → Live View)**
- Files: `frontend/src/pages/Cameras.tsx`, `frontend/src/components/LiveFeed.tsx`, `frontend/src/components/SourcePicker.tsx` (labels only), `frontend/src/api.ts` (add `sessionLayers` get/post), `frontend/src/App.tsx` (nav label "Live View")
- Changes:
  - Keep: `SourcePicker` (webcam scan / video upload with real progress / start / stop — already to spec), big `LiveFeed`, camera grid.
  - Add a stats strip above the feed: Detections (people/vehicles/active tracks), Frames, FPS, Device — all from `status.session` (fields exist; people/vehicles from T1.1).
  - Add **Analytics Layers** toggle bar: `Detections`, `Track IDs`, `Trajectories`, `FPS` → POST `/api/session/layers`; `Virtual Fence` → toggles the existing client-canvas zone overlay in `LiveFeed` (already real) AND mirrors `zones` in the server layers for evidence. Toggles disabled with "no active session" reason when idle.
  - On session end, toggles reset to defaults (GET refresh).
- Acceptance: with a session running, toggling `Detections` off visibly removes bounding boxes from the MJPEG within ~1–2s; `Trajectories` on shows paths; `Track IDs` off removes `| ID n` from labels; `FPS` off removes the HUD; `Virtual Fence` off hides the canvas polygons; every toggle hits the real endpoint (network tab) — no dead controls.
- Dependencies: T1.3, T0.3.

**T1.5 — Analytics page rebuild (runtime + controls)**
- Files: `frontend/src/pages/Analytics.tsx`
- Changes:
  - New **Runtime** panel: People Detected, Vehicles Detected, Active Tracks, Pipeline FPS, Frames Processed, Device, Uptime (all from `status.session`, zero/`—` when idle), **Trajectory Info** (history depth: `config tracking.history_len` = 60 points per track, stated as capability + active-track count), **Fence Status** (active zone count + `zone_person_counts` live occupancy, both exist).
  - Keep the REAL event charts (severity/type/hour) — they are truthful and useful.
  - **Visualization controls that actually work** = the same layer toggles as Live View (shared component), plus chart severity filter reuse.
- Acceptance: every runtime number traces to `status_payload`/`/api/events`; page shows zeros when nothing ran; layer toggles from this page also change the stream (same endpoint).
- Dependencies: T1.3, T1.1.

**T1.6 — AI/Event Summary surface (deterministic, frontend-only)**
- Files: NEW `frontend/src/components/EventSummary.tsx`; mounted on Command Center (below ALERTS SUMMARY) and optionally Alerts page
- Changes:
  - Consumes ONLY real `EventRow` fields. Template (no invention): for the latest event(s): `At {ts}, {Type label} — severity {severity} — source {source_id}{, Track #ids}{, zone {zone name}}{, direction {direction}}{. Reason: severity_reason}` — e.g. "At 14:32:21, Zone Entry — severity HIGH — source file:running_clip.mp4, Track #17, zone South Band, direction forward." Fills only from present fields; omits absent ones.
  - Shows the last 3–5 events as a feed; empty state "no events yet — run a session". Never mentions people/vehicles/locations/actions not present in the row. If an LLM is ever added, it must produce the same field-faithful sentences — this UI works without one.
- Acceptance: summary sentences, diffed against the corresponding event row in the Event Log, contain zero facts not present in the row (spot-check 3 events incl. one ZONE_ENTRY with track + zone + direction); empty when DB is empty.
- Dependencies: T0.5.

### P2 — ALERTS FILTERS, EVENT LOG, CAMERA MANAGEMENT, MAP POLISH

**T2.1 — Alerts page filters**
- Files: `frontend/src/pages/Events.tsx` (relabel nav "Alerts")
- Changes: keep severity chips + keyset pagination; ADD event-type filter (dropdown of types present in loaded data — real types only), source filter (dropdown of real `source_id`s), client-side time-order is already DESC (timestamp range filter optional — skip if time-boxed; mark "where practical"). Filter the live SSE section and the persisted page consistently.
- Acceptance: selecting `ZONE_ENTRY` + `HIGH` lists only matching rows; counts update; "no events match" empty state; no sample/fake alerts anywhere.
- Dependencies: none (after P0 theme).

**T2.2 — Event Log page (SQLite-backed table)**
- Files: NEW `frontend/src/pages/EventLog.tsx` (nav "Event Log"); reuses `api.events` keyset pagination
- Changes: full-width table — columns **Event ID** (truncated uuid, copyable), **Time** (`ts`), **Source**, **Type**, **Severity** (SevChip), **Track ID** (`track_ids`), **Metadata** (compact key:value chips from the real JSON). Search box: client-side substring across id/type/source/zone/metadata on loaded pages; "Load older 50" for more. Row click → selects the event (EventDetail drawer/panel on this page).
- Acceptance: after the demo session the row count matches `GET /api/events?limit=...` `count`; searching `ZONE_ENTRY` narrows correctly; every cell maps 1:1 to API fields.
- Dependencies: none.

**T2.3 — Camera Management page (Sources → Cameras)**
- Files: `frontend/src/pages/Sources.tsx` (relabel), `frontend/src/components/CameraStatus.tsx`
- Changes: registry becomes a full table per camera record: `camera_id`, name/label, source, `type` (source_type), `status` (LIVE only when the session's `source_id` matches — backend already enforces this in `api/map.py:95-96`), `latitude`/`longitude` (`—` when NULL), location/label. Keep the honest RTSP "not available" panel and the uploads note. Live frame tile (from `/api/frame.jpg`) only for the running source (already honest).
- Acceptance: statuses flip live→idle with session start/stop; unplaced cameras show `—` coordinates; no fake live cameras possible (backend-driven).
- Dependencies: none.

**T2.4 — Map page polish**
- Files: `frontend/src/pages/Geography.tsx`, `frontend/src/components/GeoMap.tsx`
- Changes: marker click → camera info card (label, id, status, coords) pinned next to the map (selection already flows through `store.selectCamera`); selected-camera map centering; light schematic (done in T0.3) verified; keep satellite→roadmap→schematic chain untouched.
- Acceptance: clicking a Google marker selects the camera and shows its metadata card; killing the API key still degrades to schematic with the same data and never affects the CV pipeline (verify by blocking maps.googleapis.com in Playwright).
- Dependencies: T0.1 (GeoMap fix), T0.3.

### P3 — POLISH + FUTURE FEATURES

**T3.1 — Future-capability placeholders (honest)**
- Files: `frontend/src/pages/Cameras.tsx` (Live View), `frontend/src/components/ui.tsx` (a `ComingSoon` chip)
- Changes: a "Roadmap" strip on Live View: `Pose Estimation`, `Face Detection`, `ANPR`, `Person Re-ID`, `Advanced Behavior` — each a disabled chip labeled `COMING SOON — not implemented in this build` (title tooltip with reason). Keep existing honest disabled PAUSE/RESTART and RTSP panels. Replace/keep the "HERMES — NOT CONNECTED" block (it is honest; restyle to fit).
- Acceptance: every disabled control carries a visible reason; no enabled-looking dead buttons.
**T3.2 — Visual polish pass** — spacing rhythm, focus rings (keyboard nav), empty-state copy, card hover states. Acceptance: Playwright screenshots of all 8 pages reviewed; no clipped text at 1440×900 (MacBook Air M4 target).
**T3.3 — Responsive polish** — nav collapses to icon rail < 1024px; grids stack. Acceptance: usable at 834×1112 (iPad) — demo device remains the laptop.
**T3.4 — Hygiene** — remove unused `@visactor/react-vchart` from `frontend/package.json` (grep-verified unused); rebuild; update `README.md` screenshots/notes and `docs/DEMO_CHECKLIST.md` to the light UI (docs only).

---

## 4. API / DATA REQUIREMENTS

New (all additive, no schema changes, no new dependencies):

| Endpoint | Method | Body / Response | Purpose |
|---|---|---|---|
| `/api/session/layers` | POST | `{boxes?, labels?, fps?, trajectories?, zones?}` → `{layers: {...}}`; 404 clear message when no session | Live View / Analytics layer toggles (T1.3/T1.4) |
| `/api/session/layers` | GET | `{layers: {...}}` | Toggle state refresh on session end |

Modified (additive fields only):

| Surface | Change |
|---|---|
| `GET /api/session/status` → `status_payload()` | + `people_detected`, `vehicles_detected`, `active_people`, `active_vehicles` (per-class TrackStore counts; session.py) |
| `annotate()` signature | + optional `layers`, `trajectories` kwargs — defaults reproduce current rendering exactly (annotation.py) |
| Session loop | passes layers/trajectories/zones into `annotate` (fence visible in evidence snapshots — uses the EXISTING M7 `zones=` param) |

Not needed: advisory endpoint (AI summary is deterministic frontend-only — no LLM exists and none is required); upload endpoint (exists, probe-validated); events `source` filter (client-side filtering is sufficient at demo scale — add later only if the log grows large).

---

## 5. FINAL DEMO FLOW CHECKLIST (25 steps)

1. `cd frontend && npm run build` then `./venv/bin/uvicorn backend.main:app --port 8000`
2. `GET /api/health` → `ok:true`, `db:{ok:true}`, `writer:{writer:"ok"}`, detector present
3. Open `http://localhost:8000/` → LIGHT Command Center: `TRINETRA` / `Intelligent Border Video Analytics Platform` / `SYSTEM ONLINE` (green) / live timestamp
4. Summary cards all read 0 / OFFLINE-state truthfully (zero-when-zero, no session yet)
5. Go to **Live View** → `SCAN CAMERAS` (real probe; on machines without a webcam it honestly reports none)
6. Drop `tests/assets/running_clip.mp4` into the upload zone → real metadata (size / resolution / fps / frames) after probe
7. `START ANALYSIS` → session pill flips RUNNING; camera registry row goes LIVE
8. Live MJPEG shows bounding boxes with `class conf` labels and `| ID n` track IDs
9. FPS HUD on the stream + stats strip shows real Frames / FPS / Tracks / People / Vehicles
10. Toggle `Trajectories` ON → foot-point paths render behind tracks
11. Toggle `Track IDs` OFF → `| ID n` vanishes from the stream (toggle verifiably works), then back ON
12. Create a RESTRICTED polygon video zone over the runner band (VideoZones / `POST /api/zones`) → fence overlay appears on the feed
13. A person enters the zone → `ZONE_ENTRY` fires (confirm frames + restricted → HIGH)
14. Red intrusion state: HIGH severity row highlighted red in LIVE ALERTS + header unacked flash
15. The SSE row appears in the side panel ≤2s (type, timestamp, source, Track #, severity chip)
16. **AI/Event Summary** renders the sentence for that event — every fact traceable to the row
17. Click the alert → Event Detail: camera → video zone → track chain + evidence snapshot (fence visible in the frame)
18. **Event Log** page: same event as a table row — Event ID, Time, Source, Type, Severity, Track ID, Metadata
19. `STOP` → `SESSION_COMPLETED`; camera flips to idle in the grid, the registry, and on the map marker
20. Hard-refresh the browser (F5) → all events still listed (SQLite persistence)
21. **Analytics** page: real session stats (frames/FPS/tracks/people/vehicles) + severity/type/hour charts from committed events
22. **Map** page: Google satellite renders; camera marker at its placed coordinates; sector polygon visible
23. Click the map marker → camera selected; metadata card (name, id, status, lat/lng)
24. **Cameras** (Camera Management): registry row with name, source type, status idle, latitude/longitude, location — LIVE only ever when a session runs
25. Restart uvicorn → reload → zones, events, sessions, tracks all persist (restart integrity)

---

## 6. RISKS / NOTES

1. **Doc/code drift (real)**: `M7_REPORT.md` claims the `new maps.Map` fix and a passing `tsc -b`, but the tree has the bug BACK plus a missing `Settings` page. Treat CODE as truth; T0.1 re-fixes and re-verifies with Playwright. Any "it used to pass" claim must be re-proven.
2. **"Frozen" surfaces**: `annotation.py` is documented as the M3 frozen surface, but M7 already legitimately extended it (`zones=`). The T1.3 extension follows the same pattern: optional kwargs, defaults byte-identical → 195 tests stay green. If EXECUTOR1 finds an annotate test that pins the exact signature, extend that test additively (do not delete assertions).
3. **Shared-JPEG rule (A1)**: layer toggles change the ONE JPEG used for both the live stream and evidence snapshots. Defaults are all-ON; the demo flow never toggles during the fence-crossing capture. If evidence must always be fully annotated, an alternative is a second render pass — REJECTED here (re-encode cost + A1 violation); documented trade-off.
4. **Trajectory rendering cost**: 60 points × ~dozens of tracks per frame via cv2.polylines is negligible vs YOLO inference; still, benchmark FPS before/after on the M4 Air (acceptance: FPS drop < 5%).
5. **No webcam on the demo machine** (M6/M7 honesty notes) — the demo runs on the file source; the webcam path stays implemented and honestly reports "no camera available". Do not fake a webcam.
6. **Per-class counts depend on class labels** — `_VEHICLE_CLASSES` already exists in `session.py`; reuse it (single source of truth), do not duplicate the set in the frontend.
7. **Light theme vs server-drawn JPEG overlays**: box/HUD colors are burned into the video pixels — unaffected by page theme (good). The client-canvas zone overlay colors (`LiveFeed.tsx:35` `#ff5c5c`/`#4da3ff`) may stay as-is (they sit on video, not on page surfaces).
8. **Google Maps key discipline**: the key comes from `/api/map/config` at runtime — never hardcode, never log; keep the `.env` loader untouched.
9. **Suite green is a gate**: every backend task lands only with `pytest -q` at 195 pass / 4 skip (plus the new layer tests). Every frontend task lands only with `tsc --noEmit` + `vite build` clean.
10. **One active session** (frozen §17) — all camera status surfaces derive from `active_session`; nothing may imply multi-camera concurrency.
