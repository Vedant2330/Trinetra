# ADR-003 — M7 map integration: Google Maps with non-critical fallback chain

**Status:** accepted · **Amends:** ADR-002 (M7 geographic scope) · **Author:** god (Michael), per user mandate

## Decision
M7's operational map integrates **Google Maps** (user-provided API key, held in gitignored `.env` as `GOOGLE_MAPS_API_KEY`, never committed; `.env` + `*.key` added to .gitignore). Layered presentation exactly as mandated:

1. **Primary:** Google satellite imagery
2. **Fallback 1:** Google standard/roadmap layer (same key)
3. **Fallback 2 (non-critical):** offline operational schematic — canvas/SVG sector rendering with camera markers when tiles/key unavailable

**Non-criticality rule (binding):** the CV/event pipeline (sources → detection → tracking → fence → events → persistence → SSE) must function 100% with Google Maps dead, blocked, key-invalid, or offline. Map failure degrades ONLY the map panel; the map must never block boot, sessions, or events. Frontend detects tile/key failure and swaps to the schematic without backend involvement.

**Map features (all real-data):** camera markers with identity/status from backend sources/sessions; selected-camera highlighting; geographic operational sectors as map polygons (distinct storage/layer from M4 video zones — never conflated); active event markers; Event → Camera → Sector correlation; map ↔ camera/live-feed bidirectional interaction (select camera on map → focus its feed; select event → highlight camera + sector + evidence). Simulated coordinates explicitly labeled "Demo Operational Area"/"Simulated Camera Deployment"; data model (`camera_id, lat, lng, label` on sources per §14 future-migration pattern) accepts real coordinates later with zero rework.

## Consequences
- Planner's M7 decomposition (after M6 closes) includes: `.env` loader (§19's reserved 10-line pattern), `/api/map/config` (serves key presence flag + fallback state — key itself goes straight from `.env` to frontend at build/runtime WITHOUT passing through git), geo-sectors storage (migration), camera geolocation fields, Google Maps JS integration with satellite→roadmap→schematic chain, marker/correlation UI.
- Key security: key is in `.env` (chmod 600, gitignored). RECOMMENDATION TO USER (outside repo control): add HTTP-referrer restrictions to this key in Google Cloud Console since it appeared in plaintext chat.
- §15's "key reserved, P3+" language is superseded by this ADR per direct mandate — the one case where Maps moves up a phase.
