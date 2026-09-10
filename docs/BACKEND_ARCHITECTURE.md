# TRINETRA Backend Architecture (v1, audited 2026-09-10)

## 1. Plane separation

```
INTELLIGENCE PLANE (Python — authoritative)          OPERATOR PLANE
VideoSource (file/webcam/rtsp)                        SwiftUI native app (parallel build)
  → FramePacket {frame, wall_ts, video_ts, idx}        legacy reference: React dist, Qt/QML
  → DetectorTracker (YOLOv8n + ByteTrack, MPS/CPU)   ← HTTP + SSE + MJPEG
  → TrackStore (foot-point history, confirm edge)
  → FenceAnalytic → CrowdAnalytic
  → KinematicTrajectoryAnalytic (FPS-calibrated)
  → ANPRAnalytic (set_frame pixel seam)
  → ReID service (shape-B) · Face (YuNet) · Pose (yolov8n-pose)
  → EventEngine (cooldown, severity ladder, shared-JPEG evidence)
  → SQLite (WAL) + EventWriter thread + SSE hub
  → API/streams → clients; Hermes; Maps key-holder
```

ONE authoritative interpretation of tracks/events/zones/trajectories lives in the
Python session + SQLite. Every consumer (REST, SSE, MJPEG, Hermes, maps,
investigation) projects from that single state — there are no parallel truths.

## 2. Processing loop (backend/services/session.py `_run`)

1. `source.read()` → EOF ⇒ status `completed` (NOT error); decode-fail streak ⇒ honest error; live sources back off 1→2→4→8s with one-shot SOURCE_LOST/RECONNECTED.
2. `detector.process(frame)` → `store.update(...)` (ByteTrack is the ONLY tracker; TrackStore keys by its IDs).
3. FrameContext built (luminance, is_night = luma<40, shape). Kinematic FPS calibration: container FPS after open (files); measured rate for metadata-less live sources.
4. Analytics chain `process(ctx, view)`: fence[0], kinematics, crowd, anpr. Pixel-needing capabilities get the frame via shape-B seams (`anpr.set_frame`, reid `process_tick`, face `detect_in_person_tracks`, pose `detect`).
5. Confirm-edge drafts (PERSON/VEHICLE_DETECTED once per track).
6. `annotate(frame, …)` BEFORE commit — the operator MJPEG and the evidence snapshot are byte-identical (A1).
7. `engine.commit(drafts, jpeg, ctx)`: cooldown (10s strict), severity ladder (+RESTRICTED, +night, cap HIGH), snapshot iff ≥MEDIUM (disk-low gate), writer row + SSE.
8. Publish slot; playback pacing to real source FPS × speed for files (a 30fps file displays at 30fps wall time, never "as fast as CPU").

## 3. Persistence (SQLite, WAL, user_version=3)

- Tables: sources, sessions, tracks (with trajectory JSON, ≤60 normalized waypoints), events, zones, geo_sectors. Per-thread connections (threading.local) + dead-thread reaping.
- Single writer thread, bounded queue, retry→pause machine, poison-event drop, restart-safe (events persist across process restarts — verified).
- Trajectories: foot-point (ground-contact) history downsampled deterministically at finalize; served via `/api/sessions/{id}/tracks`.

## 4. Capability gates (honest by construction)

| Capability | Gate | OFF behavior |
|---|---|---|
| Detector | yolov8n.pt present | health RED, sessions 503, server up |
| Face (YuNet) | yunet.onnx present | layer hidden, no FACE_DETECTED |
| Pose | yolov8n-pose.pt present | layer hidden, no keypoints |
| Re-ID | config enabled + ONNX present | empty gallery + explicit note |
| ANPR | plate model + OCR engine | heuristic localization → ANPR_PLATE_DETECTED only (never a fabricated read) |
| Hermes | gateway reachable | 503 taxonomy with reason |
| Maps | key in .env | schematic fallback, pipeline unaffected |

## 5. Timing model

`source_fps` (container truth) vs `inference_fps` (measured pure processing) vs
`pipeline_fps` (display rate incl. pacing) vs `latency_ms` (avg process time).
File playback is timestamp-paced to source FPS — processing speed never
redefines wall time. All four metrics are in every status payload.

## 6. Event taxonomy & severity

See INTEGRATION_CONTRACT.md §4. Ladder in `backend/events/engine.py::_NEW_TYPE_BASE`
+ modifiers; every event carries explainable metadata (speed_px_s, dwell_seconds,
person_count, plate state, …). Behavior events are SUSPECTED-prefixed by policy.

## 7. Known structural decisions

- One active session (409 otherwise) — single-operator MVP.
- Zones in normalized frame space; geo sectors are a separate table/concept.
- MJPEG/SSE are the only push channels; control is REST; polling fallback exists.
- Qt/QML desktop (`backend/desktop/`) is the legacy reference client; the
  SwiftUI app consumes the same contract and needs nothing from it.
