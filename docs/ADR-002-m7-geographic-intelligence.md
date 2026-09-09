# ADR-002 — M7 scope: Geographic Intelligence layer (mandate update 2026-09-09)

**Status:** accepted · **Supersedes:** original M7 "Command Center UI" scope (extends it) · **Author:** god (Michael), per user mandate

## Context
M0–M5 accepted as frozen baseline. M7 must not end as a video-analytics dashboard only. The final system provides three separated but correlated intelligence layers: (1) Video-space intelligence (M4: normalized zones, tripwires, foot points, debounce, ByteTrack identities), (2) Event intelligence (M5: generation, severity, cooldown, persistence, evidence, ack, SSE), (3) **Geographic/Operational intelligence — NEW, added in M7**.

## Decision — M7 adds an interactive operational map Command Center
- **Map:** satellite base layer when available → standard map fallback → graceful operational-schematic fallback when remote tiles unavailable. External map availability is NEVER a critical dependency: the detection/event pipeline stays fully functional in all cases.
- **Camera model (minimal, real-coords-ready):** `camera_id, latitude, longitude, label` — no GIS backend overengineering. Demo coordinates are explicitly labeled "Demo Operational Area" / "Simulated Camera Deployment" and NEVER presented as real border deployment data. §15's reserved `sources.lat/lng` (P3 Maps, ARCHITECTURE §14 future-migrations) is the natural landing spot — migration adds the columns; no fabricated values.
- **Coordinate-system separation (MANDATORY):** VIDEO ZONES (normalized frame-space, M4) vs GEOGRAPHIC/OPERATIONAL ZONES (map polygons, M7) are distinct concepts, distinct storage, distinct UI layers. Never merged, never conflated. §12's rule stands: frame-space geometry is never geo-represented.
- **Event geographic context:** correlatable fields (event_id, camera_id, source_id, object_class, track_id, video_zone_id, tripwire_id, direction, geographic_zone_id, timestamp, severity) — absent/null when not applicable; NO fabricated values.
- **Intelligence chain:** Tracked Object → Video Zone/Tripwire → Event → Camera → Geographic Sector → Command Center Investigation.
- **UI hierarchy:** PRIMARY live feed + operational map; SECONDARY active alerts + investigation context + camera status; TERTIARY history/ack/zones/health. Interactions: select camera→focus feed; select event→context (camera, video zone/tripwire, geo sector, evidence); select sector→associated cameras/events; live updates via EXISTING SSE (no polling).
- **Detection scope FROZEN:** person/bicycle/car/motorcycle/bus/truck only. NO new models (face/weapon/LPR/action recognition) without explicit approval.

## Consequences
- Planner's M7 decomposition must include: geo zone storage (new table via migration per §14 pattern), camera geolocation config/data path, map frontend with offline fallback, event-correlation endpoint(s), SSE-driven map/live markers, ADR-001's ledgered M7 endpoint reconciliation (sources GET, webcam scan, uploads, sessions list/by-id, start-by-source_id, frame.jpg clean-frame semantics for the zone editor), zone-overlay-on-annotated-frames (Oscar M5 ruling: server-side optional `zones=None` annotate param so snapshots show the breached zone).
- Final gate: full chain VERIFIED end-to-end (Real Source → ... → Geographic Context); report honestly separates VERIFIED / NOT TESTED / SIMULATED / DEMO-ONLY. No fabricated numbers or geographic intelligence.
- Single-flight workflow unchanged: PLANNER → ARCHITECT → EXECUTER → OSCAR → god gate → commit, one agent at a time, explicit outbox dispatches.
