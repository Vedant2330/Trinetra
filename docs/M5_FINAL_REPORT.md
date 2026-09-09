# M5 — EVENT ENGINE: FINAL REPORT

STATUS: **PASS**

## STATUS
M5 implemented, independently reviewed (FAIL→fix→PASS cycle), committed (`66404f3`). Suite: **162 passed / 4 skipped / 0 failed** (57 new M5 tests). Verified by three independent suite executions (executer 159P pre-fix → 162P post-fix, god 162P, Oscar 162P).

## WHAT WAS IMPLEMENTED
- `backend/db/` — connection.py (per-thread conns via threading.local; pragmas WAL/synchronous=NORMAL/busy_timeout=5000/foreign_keys=ON; transactional migration runner — statement-by-statement inside BEGIN IMMEDIATE, not executescript), migrations.py (001 = §14 schema verbatim: 6 tables + 5 indexes), dao.py (sources upsert, sessions insert/update, tracks flush, zones CRUD deterministic order, events batch insert/query/ack-idempotent, evidence row-checked lookup, retention sweep), writer.py (single writer thread, bounded queue default 2000 BLOCKS producer, catch-all per batch — DB error drops batch with logged error + dropped_batches counter, kills neither thread nor session).
- `backend/events/` — engine.py (commit(drafts, annotated_jpeg, ctx); cooldown STRICTLY <10s keyed (type,track,zone); PERSON/VEHICLE_DETECTED structural once-per-track via take_newly_confirmed; severity ladder INFO<LOW<MEDIUM<HIGH capped at HIGH with concatenated severity_reason; snapshot iff ≥MEDIUM — evidence bytes = the exact slot JPEG, no re-encode; per-session reset), sse.py (per-client bounded 100 drop-oldest, keepalive 5s, prune-on-disconnect).
- `backend/api/` — routers into the ONE app: zones CRUD (uuid ids, works with NO active session, typed+bare geometry errors → clean 400), events query (filters/DESC/keyset pagination) + ack (double-ack 200, unknown 404), evidence (DB-row-checked serving; ../, absolute, symlink, mismatch → 404), SSE stream.
- `backend/core/errors.py` — ApiState composition seam.
- Wiring: lifespan (migrations + retention + writer + app-scoped ZoneStore(dao) + install); session_start endpoint passes zones/dao/writer/hub into start_session (the F1 composition fix); session loop full §3 order (read→detect→state→ctx→chain→annotate→commit(same JPEG)→publish); sessions-row INSERT at start + UPDATE at end; sources upsert; SOURCE_CONNECTED after open+first-read; SOURCE_LOST before status=error; EOF finalize flush→SESSION_COMPLETED→drain→status-flip; finalize in finally for all stop paths; status_payload events_committed + zone_person_counts.
- Modified: analytics/zones.py (SQLite-backed, app-scoped), analytics/fence.py (per-tick zone-diff → implicit ZONE_EXIT on deactivate/delete + purge + fresh confirm on reactivate; tripwire state dropped after >lost_timeout absence; track_class in LINE_CROSSING metadata; thread-safe zone_person_counts), state/tracks.py (last_conf/max_conf, confirmed property, take_newly_confirmed), requirements.txt (httpx==0.28.1 pinned — TestClient hard-import).

## ARCHITECTURE
§13 two-layer dedup (structural in fence + cooldown in engine) composes — one in-out cycle = exactly 2 committed events. §14 verbatim schema, WAL/FK pragmas, single writer. §15 one app + routers, M3 endpoints VERBATIM (m3_fullstack green). §16 in-process SSE hub, no broker. §3 order exact; annotate-before-commit frozen; snapshot = operator's JPEG. §7 substrate minimal — no ID generation in analytics (grep-verified); ByteTrack sole authority. §20 writer catch-all (retry×3 correctly deferred to M6).

## FILES CREATED
backend/db/{__init__,connection,migrations,dao,writer}.py · backend/events/{__init__,engine,sse}.py · backend/api/{__init__,zones,events,evidence,stream}.py · backend/core/errors.py · tests/test_m5_{db,engine,api,sse,integration}.py

## FILES MODIFIED
analytics/zones.py · analytics/fence.py · state/tracks.py · services/session.py · main.py · requirements.txt

## FILES NOT MODIFIED (protected)
vision/* (M2) · sources/* (M1) · vision/annotation.py (M3 frozen surface) · config/default.toml · all M0–M4 tests (except C9 drafts_count→events_committed rename in-commit).

## DEPENDENCIES
httpx==0.28.1 pinned (pre-existing transitively; declaring it — zero new install). Nothing else.

## TESTS EXECUTED
`venv/bin/python -m pytest -q` — 3× post-fix executions (executer, god, Oscar): 162P/4S/0F each. m3_fullstack re-verified PASS.

## ACTUAL TEST RESULTS
162 passed, 4 skipped (webcam markers, pre-existing), 0 failed (~36s). M5 adds 57 tests (12 db, 12 engine, 15 api incl. F1/F2/A1 regressions, 7 sse, 11 integration).

## INTEGRATION RESULTS
F1 live-path regression: lifespan app → POST /api/session/start (running_clip.mp4) → events rows in SQLite (PERSON_DETECTED + SESSION_COMPLETED + SOURCE_CONNECTED), session SAW the seeded SQLite zone (ZONE_ENTRY z-f1), SSE frames received, sessions+tracks rows, events_committed. B3 burst: 10,000 events, writer slowed, queue capped — producer-blocking OBSERVED, rows==commits==10,000 exact, drain to 0. Real-pipeline e2e: 61 frames → 13 committed events, all FK-resolve.

## PERFORMANCE
MEASURED: engine.commit 0.24 ms per 50-draft tick (0.005 ms/draft); evidence lookup 0.004 ms; luminance 0.153 ms (M4) — §3 step-3 budget holds ~17× margin.

## BUGS FOUND AND FIXED
1. **F1 (Oscar)**: REST sessions never received DAO/writer/hub/ZoneStore — the composition gap; unit tests constructed deps manually so 159P missed it. Fixed + composition-pinning regression test.
2. **F2 (Oscar)**: zone-id collision after delete → UNIQUE violation → 500. Fixed with uuid ids + real-cycle regression test.
3. **A1 (Oscar)**: bare dict iteration in zone_person_counts from API threads → RuntimeError race. Fixed with list() snapshot + thread-hammer test.
4. Executer-found: TestClient engine-hub subscribe() attribute quirk (fixed in tests).

## KNOWN LIMITATIONS (Oscar advisories, ledgered)
A2: sync SSE generators in anyio threadpool cap ~40 concurrent SSE clients (M7: async generator or capacity bump). A3: Database(':memory:') per-thread-connection trap (unused; document/reject later). A4: poison-batch drops orphan snapshot files until retention sweep (documented backstop). A5: source-type sniff duplication (M6+). A6: before/before_id cursor pairing footgun (document). Zone-overlay on annotated frames: deferred to M7 (Oscar ruling: server-side optional param so snapshots show the breached zone). In-memory ZoneStore path retains M4 counter ids (documented divergence; SQLite uniqueness binds DAO path only). Webcam LOST path testable with real camera only (M6 drill).

## ARCHITECTURAL NOTES
ADR-001 re-split honored: no M6 failure drills, no M7 UI in this milestone. §15 errata (18 routes vs "17" header) ledgered for ADR-002 with M7 endpoint reconciliation (sources GET, webcam scan, uploads, sessions list/by-id, start-by-source_id, frame.jpg clean-frame semantics).

## SUCCESS CRITERIA SCORECARD
[✓] Zones survive restart · [✓] Events query/ack (filters/DESC/pagination/idempotent) · [✓] SSE ≤2s in-process + real-uvicorn live path · [✓] B3 zero-loss, blocking observed · [✓] Snapshot gating + byte-identity · [✓] Severity matrix incl. RESTRICTED+night HIGH + dual reason · [✓] Restart persistence · [✓] One in-out = exactly 2 committed events · [✓] 105 pre-M5 tests green (rename-only touch) · [✓] PERSON/VEHICLE once-per-track + re-fire per session · [✓] SOURCE_CONNECTED/LOST (mock) · [✓] Oscar-1/2/5 fixed + tested · [✓] 8 event types · [✓] CRUD no-session · [✓] F1 composition pinned by test

## COMMIT
`66404f3` — 25 files, +3705/−130. Tree clean.

## NEXT CHECKPOINT
M6 — HARDENING: deliberate failure testing per §20 matrix (webcam unplug/replug, corrupt mid-file, model-missing boot, DB busy/poison retry×3 + queue pause, disk-low snapshot bypass, repeated start/stop, resource release, restart integrity) + scripts/bench.py + A2–A6 advisory resolution where in scope. Single-flight sequence restarts: planner decomposition → architect review → executer → oscar → gate → commit.
