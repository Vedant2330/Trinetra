"""TRINETRA core configuration loader.

Reads config/default.toml (stdlib tomllib) — zero parse dependencies.
Secrets (Maps key, Hermes gateway key) live in .env at the repo root —
never in this repo's source, never logged; loaded here once per process.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "default.toml"


def _load_env_file() -> dict[str, str]:
    """§19 reserved loader: parse the repo-root .env (chmod 600,
    gitignored) into a dict. Missing file / malformed lines are ignored
    (never a boot dependency)."""
    out: dict[str, str] = {}
    env_file = ROOT / ".env"
    try:
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            if key:
                out[key.strip()] = value
    except OSError:
        pass
    return out


_ENV_FILE = _load_env_file()


def _env(name: str, default: str = "") -> str:
    """Environment lookup: real env var first, then the .env file."""
    return os.environ.get(name, _ENV_FILE.get(name, default))


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
    classes: list[int] = field(
        default_factory=lambda: [0, 1, 2, 3, 5, 7, 24, 26, 28, 39, 41, 56, 57, 58, 60, 62, 63, 67, 73]
    )


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


@dataclass(frozen=True)
class ReIdCfg:
    """Phase 2 cross-camera Re-ID knobs (M8 port, embedder upgraded to
    the fast-reid ONNX via cv2.dnn — the plan-sanctioned PRIMARY).

    confirm_similarity >= links identities; candidate_similarity is the
    review-only floor and NEVER links (mandate: 0.55 must not merge).
    embedder='cv2dnn' + onnx_path: fast-reid_mobilenetv2.onnx under
    models/ — the honest availability gate means a missing file simply
    disables Re-ID (no fabricated identities, ever)."""

    embedder: str = "cv2dnn"
    onnx_path: str = "fast-reid_mobilenetv2.onnx"
    model_path: str = "reid.ts"          # TorchScriptEmbedder seam (retained)
    enabled: bool = False                # capability toggle (§3.4 — off by default)
    confirm_similarity: float = 0.80
    candidate_similarity: float = 0.55
    max_gap_s: float = 600.0
    exemplars_per_camera: int = 8
    sample_interval_ticks: int = 25
    sample_min_frames_seen: int = 5
    sample_min_gap_s: float = 10.0


@dataclass(frozen=True)
class HermesCfg:
    """Phase 7 / P-HERMES Grounded LLM reasoning assistant settings."""
    enabled: bool = True
    base_url: str = "http://127.0.0.1:20128/v1"
    model: str = "auto/glm"
    api_key: str = ""
    timeout_s: float = 60.0
    connect_timeout_s: float = 5.0
    max_context_events: int = 5
    status_cache_s: float = 60.0


def _build() -> tuple:
    d = _RAW.get("device", {})
    v = _RAW.get("vision", {})
    t = _RAW.get("tracking", {})
    f = _RAW.get("fence", {})
    e = _RAW.get("events", {})
    s = _RAW.get("stream", {})
    p = _RAW.get("paths", {})
    so = _RAW.get("sources", {})
    r = _RAW.get("reid", {})
    h = _RAW.get("hermes", {})

    # Environment overrides take precedence for Hermes
    hermes_enabled = os.getenv("HERMES_ENABLED", "").lower()
    if hermes_enabled in ("1", "true", "yes"):
        h_enabled = True
    elif hermes_enabled in ("0", "false", "no"):
        h_enabled = False
    else:
        h_enabled = bool(h.get("enabled", True))

    h_base_url = _env("HERMES_BASE_URL", h.get("base_url", "http://127.0.0.1:20128/v1"))
    h_model = _env("HERMES_MODEL", h.get("model", "auto/glm"))
    # The gateway requires a Bearer key for /v1/models (status); without
    # it status reports a false 401 even when chat works. Key lives in
    # .env — never in source, never logged.
    h_api_key = _env("HERMES_API_KEY", h.get("api_key", ""))

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
        ReIdCfg(
            embedder=str(r.get("embedder", "cv2dnn")),
            onnx_path=str(r.get("onnx_path", "fast-reid_mobilenetv2.onnx")),
            model_path=str(r.get("model_path", "reid.ts")),
            enabled=bool(r.get("enabled", False)),
            confirm_similarity=float(r.get("confirm_similarity", 0.80)),
            candidate_similarity=float(r.get("candidate_similarity", 0.55)),
            max_gap_s=float(r.get("max_gap_s", 600.0)),
            exemplars_per_camera=int(r.get("exemplars_per_camera", 8)),
            sample_interval_ticks=int(r.get("sample_interval_ticks", 25)),
            sample_min_frames_seen=int(r.get("sample_min_frames_seen", 5)),
            sample_min_gap_s=float(r.get("sample_min_gap_s", 10.0)),
        ),
        HermesCfg(
            enabled=h_enabled,
            base_url=h_base_url,
            model=h_model,
            api_key=h_api_key,
            timeout_s=float(h.get("timeout_s", 60.0)),
            connect_timeout_s=float(h.get("connect_timeout_s", 5.0)),
            max_context_events=int(h.get("max_context_events", 5)),
            status_cache_s=float(h.get("status_cache_s", 60.0)),
        ),
    )


DEVICE, VISION, TRACKING, FENCE, EVENTS, STREAM, PATHS, SOURCES, REID, HERMES = _build()

MODELS_DIR = ROOT / "models"
DB_PATH = PATHS.data_dir / "trinetra.db"
EVIDENCE_DIR = PATHS.data_dir / "evidence"
