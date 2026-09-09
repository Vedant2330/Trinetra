# TRINETRA — M7 Milestone Report: Command Center + Geographic Intelligence

**Status:** verified (final closure pass) · **Date:** 2026-09-09 · **Scope:** ADR-002 + ADR-003

## What M7 delivers

Three correlated intelligence layers, per ADR-002:
1. **Video-space** (M4, frozen): normalized zones, tripwires, foot points
2. **Event** (M5/M6, frozen): severity, cooldown, persistence, evidence, ack, SSE
3. **Geographic/Operational** (NEW): camera lat/lng, geo sectors, map correlation

## Backend additions (M7)

| Piece | Where | Notes |
|---|---|---|
| Migration 2 | `backend/db/migrations.py` | `geo_sectors` table + `sources.latitude/longitude/label` columns (§14 future-migrations pattern) |
| Geo DAO | `backend/db/dao.py` | `sources_rows` (NULL coords = not geo-located, never fabricated), `set_source_geo`, geo sector CRUD — all degrade to empty/False on a v1 DB (non-criticality) |
| Map API | `backend/api/map.py` | `GET /api/map/config` (key from `.env` via §19 loader — never committed, never logged), `GET /api/map/cameras`, `PUT /api/map/cameras/{id}/geo`, `GET/POST/DELETE /api/map/sectors` |
| Zone overlay | `backend/vision/annotation.py` | `zones=` optional param (Oscar M5 ruling) — server-side video-zone drawing for operator snapshots; malformed geometry degrades cleanly |
| UI serving | `backend/main.py` | mounts `frontend/dist` at `/` when built; absent bundle = API-only, never a boot dependency |

## Frontend (Command Center)

React 18 + Vite 6 + TypeScript strict + Tailwind 3 — `frontend/`.

- **Layout** (ADR-002 hierarchy): PRIMARY live MJPEG feed + operational map; SECONDARY session/cameras/events; TERTIARY zones/sectors/event-detail; status bar with real health/SSE/session state
- **Live feed**: real `/api/stream.mjpg` + canvas overlay of the session's M4 video zones
- **Events**: SSE (`/api/stream/events`) live + `/api/events` backfill; severity chips; HIGH-lighting; ack
- **Event detail**: intelligence chain Event → Camera → Video Zone → Geo Sector + registered snapshot via `/api/evidence/{event_id}/{file}`; point-in-polygon sector correlation
- **Session control**: real start (file/webcam) / stop, real metrics (frames, FPS, tracks, events committed, zone occupancy)
- **Map** (ADR-003 chain): Google satellite → roadmap (`tiles_error` downgrade) → offline SVG schematic with the same real cameras/sectors; markers with live/idle/error status; sector polygons; simulated-coordinates banner

## Security (ADR-003)

- `GOOGLE_MAPS_API_KEY` lives in `.env` (gitignored, chmod 600) — read at request time by `/api/map/config`; never in frontend source, never in git, never in logs
- Tests never assert the key's value (presence only)
- Recommended (outside repo control): HTTP-referrer restriction on the key in Google Cloud Console

## Honesty ledger

| Item | Status |
|---|---|
| Map API endpoints (config/cameras/sectors CRUD) | VERIFIED (`tests/test_m7_geo.py` 12/12) |
| Migration 2 + geo DAO incl. v1-DB degradation | VERIFIED (unit + v1-DB drill) |
| annotate(zones=) + malformed-zone degradation | VERIFIED |
| M5 migration tests updated for v2 world (C5 churn) | VERIFIED (24P with test_m7_geo, god-confirmed) |
| Full suite (M6 + M7 additions) | VERIFIED — 195 passed / 4 skipped / 2 warnings, 89s, unsandboxed |
| Frontend TypeScript build | VERIFIED (god-executed: tsc -b clean, vite build, 39 modules, dist/ written) |
| E2E over real uvicorn socket | VERIFIED — scripts/m7_e2e.py ALL 24 CHECKS PASS: boot, health ok, map config (key PRESENT, never printed), UI bundle at /, real file session (mps device), one LIVE camera from the running session, camera geo PUT, sector create/list/delete, 61 MJPEG frames, SSE data: frames, events persisted (PERSON_DETECTED/SESSION_COMPLETED/ZONE_ENTRY), camera idle after stop, health green at end |
| Google Maps satellite rendering in real Chromium | **VERIFIED** — `google.maps` loads with the configured key; `.gm-style` container + 6 Google tile `<img>`s + camera marker + sector polygon render. Found + fixed a REAL bug: `Map/Marker/Polygon` invoked without `new` threw `this.set is not a function` (pre-fix the chain correctly degraded to schematic; post-fix satellite is primary as designed). Roadmap (`tiles_error`) downgrade: implemented, not exercised live (no tile errors with the working key) — verified by construction |
| Offline schematic fallback | VERIFIED — renders real cameras/sectors; simulated-coordinates banner present (was the active mode pre-fix) |
| UI E2E in real Chromium (Playwright) | VERIFIED — no blank page, no React crash, 0 console/page errors; layout/live feed/map/cameras/events/session controls/status metrics render; MJPEG `<img>` live; timeline rows with severity chips + NEW/ACK; EventDetail chain Event→Camera("North Gate Camera")→Video zone("South Band")→Geo sector("Demo Operational Area") + evidence `<img>` from `/api/evidence/` |
| Real GPS coordinates | SIMULATED — camera/sector coordinates explicitly labeled "Demo Operational Area (Simulated Camera Deployment)"; data model accepts real coordinates with zero rework |

## Known limitations

- Webcam drill on this machine: no camera (permission/busy) — M6 honesty note carries over. File-source session used for all live UI verification
- Google Maps roadmap downgrade + no-key schematic path: logic verified by construction + pre-fix live behavior; not artificially forced with the working key
- One active session at a time (frozen §17 architecture) — map reflects it via `active_session`

## Verification fixes (final closure pass, 2026-09-09 — genuine bugs only)

1. `backend/main.py` — `_DIST` used `parents[2]` (→ SIH26/) instead of `parents[1]` (→ Trinetra/): `frontend/dist` was NEVER served (GET / → 404). Fixed; UI now mounts at `/`
2. `frontend/src/components/GeoMap.tsx` + `src/mapTypes.ts` — Google Maps `Map/Marker/Polygon` invoked without `new` (threw `this.set is not a function` → permanent schematic). Fixed with `new` + constructor-typed shim
3. `frontend/src/types.ts` — stale types vs real backend payloads: `GeoCamera.type`, `EventRow.keepalive` added
4. `frontend/src/components/GeoMap.tsx` — sector polygon `[[lat,lng]]`→`{lat,lng}` conversion; unused `label` prop dropped
5. `frontend/src/components/LiveFeed.tsx` — unused `ZoneRow` import dropped

Final verified state: suite 195P/4S/2W/0F (90.03s) · frontend `tsc -b && vite build` PASS (dist/ 0.71 kB html + 174.46 kB js + 12.97 kB css) · server serving UI at `http://127.0.0.1:8000/` · live file session (mps, ~36–41 FPS, 13 events, ZONE_ENTRY HIGH w/ evidence) · satellite map rendering in Chromium.
