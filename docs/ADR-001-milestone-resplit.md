# ADR-001 — Milestone re-split: M4 = fence analytics, persistence/events/SSE/UI deferred

**Date:** 2026-09-09 · **Status:** accepted · **Supersedes:** IMPLEMENTATION_PLAN.md M4/M5 split (partially)

## Context
The original IMPLEMENTATION_PLAN.md bundled into M4: fence geometry + event engine + DB + SSE + zones CRUD + events REST. The 2026-09-09 execution mandate re-split the milestones: M4 = virtual fence analytics only; M5 = event engine + persistence + live delivery; M6 = hardening; M7 = Command Center UI.

## Decision
Accept the re-split. No acceptance criterion is dropped — each item relocates:
- Zones survive restart / zones CRUD round-trip → M5 (SQLite zones table, ARCHITECTURE §14)
- Events query/ack, severity map, snapshot gating, SSE ≤2 s, B3 burst → M5 (§13–§16)
- Failure drills (camera unplug, corrupt file, model missing, DB busy) → M6 (§20)
- Operator UI loop, zone editor round-trip, no-fake-widget audit → M7 (§17)

## Consequences
- M4 shipped `ZoneStore` as an in-memory seam; `FenceAnalytic` consumes it via accessors only, so the M5 SQLite swap touches zones backing + REST, not fence logic.
- Oscar review findings 1/2/5 (tripwire state across long absence, occupancy lifecycle on zone deactivate/remove, validator error-type consistency) are bound into M5 acceptance where they become reachable (zone CRUD).
- The G2 gate items divide across M5/M7; the overall G4 = MVP-complete verdict is unchanged.
