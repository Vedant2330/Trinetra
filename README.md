# TRINETRA

AI-Based Intelligent Video Analytics Platform for Border Surveillance
Using Existing CCTV Infrastructure.

**Phase 2 (MVP) — implementation in progress.** Current milestone: M0 — Project Foundation.

## Status

| Milestone | Scope | Status |
|---|---|---|
| M0 | Foundation: venv, deps, config, model, health | ✅ verified |
| M1 | Webcam + File sources (unified `VideoSource`) | pending |
| M2 | YOLOv8n detection + ByteTrack tracking | pending |
| M3 | Annotated MJPEG live stream | pending |
| M4 | Virtual fence (polygon + line, true geometry) | pending |
| M5 | Events + SQLite + SSE + Command Center UI | pending |

Architecture: `../ARCHITECTURE.md` (frozen) · Plan: `../IMPLEMENTATION_PLAN.md` ·
Dependency rules: `../DEPENDENCY_DECISIONS.md`.

## Quick start

```bash
cd Trinetra
./venv/bin/pip install -r requirements.txt   # already installed
./venv/bin/python tests/m0_verification.py  # foundation verification
./venv/bin/uvicorn backend.main:app --port 8000
# -> http://localhost:8000/api/health
```

## Layout (only what exists — no future-empty folders)

```
Trinetra/
├── backend/          # FastAPI app (main.py) + core/ (config)
├── config/           # default.toml — process-level settings
├── models/           # committed weights (yolov8n.pt) + manifest (M2)
├── data/             # SQLite + evidence (gitignored)
├── tests/            # m0_verification.py — real execution tests
├── docs/             # ADRs / benchmark records
├── requirements.txt  # 8 pinned runtime deps
└── venv/             # python 3.11.9 (gitignored)
```

## Rules (binding)

- Reference repos under `../` are read-only. Never modify.
- One detector (yolov8n), one tracker (ByteTrack), one backend, one SQLite DB.
- No LLM, no brokers, no Docker, no vector DB, no fake widgets.
- Every displayed number must come from a real measurement.
- Devices: MPS preferred (`device.policy=auto`), CPU fallback verified.
