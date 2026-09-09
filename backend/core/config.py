"""TRINETRA core configuration loader.

Reads config/default.toml (stdlib tomllib) — zero parse dependencies.
Env overrides reserved for future secrets (Maps key, Phase 3+); none exist in MVP.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "default.toml"


def _load_toml() -> dict[str, Any]:
    with open(CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


_RAW = _load_toml()


@dataclass(frozen=True)
class DeviceCfg:
    policy: str = "auto"


@dataclass(frozen=True)
class VisionCfg:
    model: str = "yolov8n.pt"
    conf: float = 0.35
    imgsz: int = 640
    max_frame_width: int = 1280
    classes: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 5, 7])


@dataclass(frozen=True)
class TrackingCfg:
    min_confirm_frames: int = 3
    lost_timeout_frames: int = 30
    history_len: int = 60


@dataclass(frozen=True)
class FenceCfg:
    confirm_frames: int = 3
    exit_grace_frames: int = 10


@dataclass(frozen=True)
class EventsCfg:
    cooldown_seconds: int = 10
    snapshot_min_severity: str = "MEDIUM"


@dataclass(frozen=True)
class StreamCfg:
    mjpeg_quality: int = 70
    max_fps: int = 20


@dataclass(frozen=True)
class PathsCfg:
    uploads: str = "uploads"
    data: str = "data"
    retention_days: int = 7
    min_free_mb: int = 200

    @property
    def uploads_dir(self) -> Path:
        return ROOT / self.uploads

    @property
    def data_dir(self) -> Path:
        return ROOT / self.data


@dataclass(frozen=True)
class SourcesCfg:
    """M6 §20 hardening knobs — webcam backoff ladder + file decode-fail
    abort limit (C10). Ladder is capped at backoff_cap_s; delays are
    interruptible (session stop event), never time.sleep."""
    backoff_base_s: float = 1.0
    backoff_cap_s: float = 8.0
    decode_fail_limit: int = 60


def _build() -> tuple:
    d = _RAW.get("device", {})
    v = _RAW.get("vision", {})
    t = _RAW.get("tracking", {})
    f = _RAW.get("fence", {})
    e = _RAW.get("events", {})
    s = _RAW.get("stream", {})
    p = _RAW.get("paths", {})
    so = _RAW.get("sources", {})
    return (
        DeviceCfg(policy=d.get("policy", "auto")),
        VisionCfg(
            model=v.get("model", "yolov8n.pt"),
            conf=float(v.get("conf", 0.35)),
            imgsz=int(v.get("imgsz", 640)),
            max_frame_width=int(v.get("max_frame_width", 1280)),
            classes=[int(c) for c in v.get("classes", [0, 1, 2, 3, 5, 7])],
        ),
        TrackingCfg(
            min_confirm_frames=int(t.get("min_confirm_frames", 3)),
            lost_timeout_frames=int(t.get("lost_timeout_frames", 30)),
            history_len=int(t.get("history_len", 60)),
        ),
        FenceCfg(
            confirm_frames=int(f.get("confirm_frames", 3)),
            exit_grace_frames=int(f.get("exit_grace_frames", 10)),
        ),
        EventsCfg(
            cooldown_seconds=int(e.get("cooldown_seconds", 10)),
            snapshot_min_severity=str(e.get("snapshot_min_severity", "MEDIUM")),
        ),
        StreamCfg(
            mjpeg_quality=int(s.get("mjpeg_quality", 70)),
            max_fps=int(s.get("max_fps", 20)),
        ),
        PathsCfg(
            uploads=str(p.get("uploads", "uploads")),
            data=str(p.get("data", "data")),
            retention_days=int(p.get("retention_days", 7)),
            min_free_mb=int(p.get("min_free_mb", 200)),
        ),
        SourcesCfg(
            backoff_base_s=float(so.get("backoff_base_s", 1.0)),
            backoff_cap_s=float(so.get("backoff_cap_s", 8.0)),
            decode_fail_limit=int(so.get("decode_fail_limit", 60)),
        ),
    )


DEVICE, VISION, TRACKING, FENCE, EVENTS, STREAM, PATHS, SOURCES = _build()

MODELS_DIR = ROOT / "models"
DB_PATH = PATHS.data_dir / "trinetra.db"
EVIDENCE_DIR = PATHS.data_dir / "evidence"
