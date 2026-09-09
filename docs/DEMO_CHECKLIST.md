# TRINETRA — Demo Checklist (M6)

Two-minute demo script + the failure rows that are **MANUAL-ONLY** (honestly
labeled — never faked as automated tests). RTSP is Phase 3 (P3) — noted
where relevant, not part of this demo.

## 2-minute happy-path demo (all REAL)

1. `./venv/bin/uvicorn backend.main:app --port 8000`
2. Open `http://localhost:8000/api/health` — green: `ok:true`, `db:{ok:true}`,
   `writer:{writer:"ok"}`, models present.
3. `POST /api/session/start` `{"type":"file","path":"tests/assets/running_clip.mp4"}`
   → 200; open `/api/stream.mjpg` in a browser tab — annotated MJPEG.
4. `POST /api/zones` (RESTRICTED polygon over the people band) → next tick
   the fence sees it; ZONE_ENTRY lands in `/api/events` (DESC) and any open
   `/api/stream/events` SSE tab within ≤2 s, with a snapshot thumbnail via
   `/api/evidence/{event_id}/{file}`.
5. Ack the event (`POST /api/events/{id}/ack`) → status `acked` (idempotent).
6. EOF → SESSION_COMPLETED; `GET /api/sessions`-equivalent via
   `/api/session/status` → `events_committed` + stats; SQLite rows persist
   across a server restart (zones, events, sessions, tracks).
7. Draw a line with `direction_mode:"forward"` → a reverse crossing is
   suppressed; a forward crossing fires LINE_CROSSING with `direction`.

## MANUAL-ONLY drills (cannot be automated honestly on this machine)

These §20 rows have NO automated substitute; each was rehearsed manually
where hardware allowed, and is marked with its coverage status:

| Drill | Steps | Status on this machine |
|---|---|---|
| Camera unplug mid-session (webcam) | Start webcam session → physically disconnect → expect: SOURCE_LOST once, stream freezes, UI red; reconnect → backoff ladder 1→2→4→8 s → SOURCE_RECONNECTED → stream resumes | **NOT RUN** — camera unavailable in this environment (permission/busy). The full ladder semantics ARE automated against a mock live source (`test_m6_drills.py::test_c2_*`). |
| Disk-full at OS level | Fill disk to < 200 MB free → expect: events persist without snapshots, flagged `snapshot_skipped_low_disk`, no crash | The GATE is automated via an absurd `min_free_mb` threshold (real `shutil.disk_usage` path) — `test_m6_advisories.py::test_c12_disk_low_skips_snapshot_flags_metadata`. Physical disk-full not run (shared machine). |
| Real MPS hardware death | Force MPS failure mid-session → CPU reload + system event + session continues | **NOT RUN** (no honest way to kill MPS hardware). Fallback branch selection unit-tested; CPU fallback path exercised by every cpu-policy run. |
| Corrupt truncated file MID-UPLOAD | Upload a truncated mp4 → 4xx at probe | Upload endpoint is M7 scope (§15 ownership); mid-FILE-decode drills are automated (`test_m6_drills.py` C3 tests: streak < limit → skip+count+complete; ≥ limit → error + health 200). |
| Model missing at boot | Rename `models/yolov8n.pt` → start server | **AUTOMATED** (`test_c7_model_missing_503_and_restore_without_restart`): health RED `ok:false` + `present:false`; start → 503 with actionable message; RESTORE the file → next start works WITHOUT server restart. |
| RTSP drop / reconnect | n/a | **P3** — RtspSource does not exist in Phase 2 (by design). |

## Rehearsal status

- Demo script steps 1–7: executed end-to-end repeatedly by the M5/M6 test
  suite (real app, real DB, real SSE) — PASS.
- Demo twice in a row, zero unrecovered failures: the automated suite is
  the rehearsal record (162+ tests green per milestone).
