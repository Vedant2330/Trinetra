"""TRINETRA — M0 foundation application.

Minimal FastAPI app proving the boot path: config loads, model manifest
checks, health endpoint. Vision pipeline arrives in M2+.

Run:  ./venv/bin/uvicorn backend.main:app --port 8000
"""

from __future__ import annotations

import time

from fastapi import FastAPI

from backend.core.config import DEVICE, MODELS_DIR, VISION

app = FastAPI(title="TRINETRA", version="0.1.0-m0")
_STARTED = time.time()


def _model_status() -> dict:
    target = MODELS_DIR / VISION.model
    return {
        "detector": {
            "file": VISION.model,
            "present": target.exists(),
            "size_mb": round(target.stat().st_size / 1e6, 1) if target.exists() else None,
        }
    }


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "app": "TRINETRA",
        "phase": "M0",
        "uptime_s": round(time.time() - _STARTED, 1),
        "device_policy": DEVICE.policy,
        "models": _model_status(),
    }
