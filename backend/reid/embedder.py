"""TRINETRA Re-ID embedder seam — one preprocessing contract, four
implementations (M8 port + Phase 2 cv2.dnn PRIMARY).

The audited FastReID preprocessing contract (architect audit, frozen):

    BGR -> RGB
    resize 256x128 (w x h), INTER_CUBIC
    float32
    HWC -> CHW
    add batch dimension
    raw scale (0-255 — FastReID models embed their own normalization;
    do NOT divide by 255 unless the model card says otherwise)

`preprocess_crop` implements EXACTLY this and is shared by every
embedder so the contract cannot drift between real and test paths.

Embedders:
  - OpenCVDnnEmbedder: PRIMARY (Phase 2). fast-reid MobileNetV2 ONNX
    via cv2.dnn.readNetFromONNX — zero new runtime deps (no
    onnxruntime). Dynamic batch forwarding is PRIMARY (true batch-n,
    e.g. batch-1 for single crop inference at ~5.5ms). Zero-padded
    batch-32 is retained as fallback on cv2.error. Model provenance:
    fast-reid_mobilenetv2.onnx (MIT, from the DeepCamera workspace
    repo), md5 77a97e84aac88bdb3eeaa17dd6c57180, audit-measured
    discrimination margin 0.638 (same-track cosine 0.84 vs diff 0.20).
  - TorchScriptEmbedder: the M8 seam, retained for provenance. Nothing
    points at it by default (reid.ts was the REJECTED InceptionV3
    proxy — false-confirms 2/5 different subjects at the 0.80 bar).
  - DummyEmbedder: deterministic test embedder — hashes the crop's raw
    bytes into a stable pseudo-embedding, optionally modulated by a
    per-subject seed. For unit tests ONLY (unit tests must not require
    a GPU/model download). It is NOT a Re-ID model and produces no
    appearance semantics; tests use synthetic subjects to construct
    controlled similarity structure.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from backend.core.config import MODELS_DIR, REID

log = logging.getLogger("trinetra.reid.embedder")

# The audited contract (frozen) — FastReID OSNet-family export.
CROP_W, CROP_H = 256, 128          # width x height input size

# The fixed-shape ONNX graph batch (audit §8 #11: batch-1 is
# INVALID_ARGUMENT; the graph demands exactly 32 rows).
BATCH_SIZE = 32


def preprocess_crop(crop_bgr: np.ndarray) -> np.ndarray:
    """BGR uint8 crop -> (1, 3, 128, 256) float32 CHW, RAW 0-255 scale.

    Exactly the audited steps, order preserved. A crop smaller than a
    few pixels is rejected (appearance garbage in, garbage out).
    """
    if crop_bgr is None or crop_bgr.ndim != 3 or crop_bgr.shape[2] != 3:
        raise ValueError("crop must be HxWx3")
    if crop_bgr.shape[0] < 2 or crop_bgr.shape[1] < 2:
        raise ValueError("crop too small to embed")

    import cv2
    rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (CROP_W, CROP_H), interpolation=cv2.INTER_CUBIC)
    chw = np.transpose(resized, (2, 0, 1)).astype(np.float32)   # HWC->CHW
    return chw[np.newaxis, ...]                                  # batch dim


def l2_normalize(vec: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(vec))
    if n == 0.0:
        return vec
    return vec / n


class ReIDEmbedder:
    """Common embedder interface: embed(crop) -> normalized 1-D vector."""

    name = "base"

    def embed(self, crop_bgr: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def embed_batch(self, crops: list[np.ndarray]) -> list[np.ndarray]:
        return [self.embed(c) for c in crops]

    @property
    def available(self) -> bool:
        """Honest gate: can this embedder produce real embeddings?"""
        return True


class TorchScriptEmbedder(ReIDEmbedder):
    """M8-era real-model wrapper (torch.jit). Retained for PROVENANCE
    ONLY — nothing points at it by default (reid.ts was the rejected
    InceptionV3-ImageNet proxy; see module docstring).

    The model file is expected as a TorchScript export at
    models/reid.ts (config [reid] model_path, default "reid.ts").
    Output convention: the model's forward returns a (1, d) or (d,)
    tensor of RAW features (no softmax); we L2-normalize so cosine
    similarity == dot product downstream.
    """

    name = "torchscript"

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._path = Path(model_path) if model_path else \
            MODELS_DIR / REID.model_path
        self._model = None                    # lazy
        self._dim: Optional[int] = None
        self._load_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self._try_load()

    def _try_load(self) -> bool:
        if self._model is not None:
            return True
        if self._load_error is not None:
            return False
        if not self._path.exists():
            self._load_error = f"model file not found: {self._path}"
            return False
        try:
            import torch
            self._model = torch.jit.load(str(self._path))
            self._model.eval()
            return True
        except Exception as e:               # noqa: BLE001 — honest gate
            self._load_error = f"{type(e).__name__}: {e}"
            log.warning("Re-ID model load failed: %s", self._load_error)
            return False

    def embed(self, crop_bgr: np.ndarray) -> np.ndarray:
        if not self._try_load():
            raise RuntimeError(
                f"Re-ID model unavailable — {self._load_error}")
        import torch
        x = preprocess_crop(crop_bgr)          # the frozen contract
        with torch.no_grad():
            out = self._model(torch.from_numpy(x))
        vec = out.detach().cpu().numpy().reshape(-1)
        return l2_normalize(vec)

    def embed_batch(self, crops: list[np.ndarray]) -> list[np.ndarray]:
        if not self._try_load():
            raise RuntimeError(
                f"Re-ID model unavailable — {self._load_error}")
        if not crops:
            return []
        import torch
        batch = np.concatenate(
            [preprocess_crop(c) for c in crops], axis=0)
        with torch.no_grad():
            out = self._model(torch.from_numpy(batch))
        mat = out.detach().cpu().numpy()
        if mat.ndim == 1:
            mat = mat.reshape(1, -1)
        return [l2_normalize(mat[i]) for i in range(mat.shape[0])]


class OpenCVDnnEmbedder(ReIDEmbedder):
    """PRIMARY Re-ID embedder (Phase 2): fast-reid MobileNetV2 ONNX
    loaded through cv2.dnn — zero new runtime deps (onnxruntime is
    FORBIDDEN by the binding plan; cv2.dnn is the sanctioned path).

    Dynamic batch forwarding is PRIMARY: cv2.dnn directly accepts
    arbitrary batch dimensions [n,3,128,256] float32 RAW scale, outputting
    [n,1280] without padding (single-crop ~5.5ms). Zero-padded 32-row batch
    is retained as fallback on cv2.error. Lazy-load on first use (§44: never at boot); a
    missing model file is an HONEST unavailable gate (the
    TorchScriptEmbedder pattern) — never a boot failure, never a
    fabricated identity.
    """

    name = "cv2dnn"

    def __init__(self, onnx_path: Optional[str] = None) -> None:
        self._path = Path(onnx_path) if onnx_path else \
            MODELS_DIR / REID.onnx_path
        self._net = None                    # lazy
        self._load_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self._try_load()

    def _try_load(self) -> bool:
        if self._net is not None:
            return True
        if self._load_error is not None:
            return False
        if not self._path.exists():
            self._load_error = f"model file not found: {self._path}"
            return False
        try:
            import cv2
            self._net = cv2.dnn.readNetFromONNX(str(self._path))
            return True
        except Exception as e:               # noqa: BLE001 — honest gate
            self._load_error = f"{type(e).__name__}: {e}"
            log.warning("Re-ID ONNX load failed: %s", self._load_error)
            return False

    def _forward_batch(self, batch: np.ndarray, n: int) -> np.ndarray:
        """Run the graph with dynamic batch forwarding as PRIMARY.
        `batch` is (n,3,128,256) with n<=32. Returns (n,1280).
        Falls back to zero-padded 32-row batch if dynamic forward fails."""
        import cv2
        try:
            self._net.setInput(batch[:n])
            out = self._net.forward()
            if out is not None and out.shape[0] == n:
                return out
        except Exception as e:
            log.debug("Dynamic batch forward error (%s), fallback to padded batch-32", e)

        # Fallback: zero-padded batch of 32
        padded = np.zeros((BATCH_SIZE, 3, CROP_H, CROP_W),
                          dtype=np.float32)
        padded[:n] = batch[:n]
        self._net.setInput(padded)
        out = self._net.forward()               # (32, 1280)
        return out[:n]

    def embed(self, crop_bgr: np.ndarray) -> np.ndarray:
        if not self._try_load():
            raise RuntimeError(
                f"Re-ID model unavailable — {self._load_error}")
        x = preprocess_crop(crop_bgr)          # (1,3,128,256) frozen contract
        out = self._forward_batch(x, 1)
        return l2_normalize(out[0].reshape(-1))

    def embed_batch(self, crops: list[np.ndarray]) -> list[np.ndarray]:
        if not self._try_load():
            raise RuntimeError(
                f"Re-ID model unavailable — {self._load_error}")
        if not crops:
            return []
        if len(crops) > BATCH_SIZE:
            # honest chunking — more than 32 crops runs in 32-slices
            out: list[np.ndarray] = []
            for i in range(0, len(crops), BATCH_SIZE):
                out += self.embed_batch(crops[i:i + BATCH_SIZE])
            return out
        batch = np.concatenate(
            [preprocess_crop(c) for c in crops], axis=0)
        out = self._forward_batch(batch, len(crops))   # (n, 1280)
        return [l2_normalize(out[i].reshape(-1))
                for i in range(len(crops))]


class DummyEmbedder(ReIDEmbedder):
    """Deterministic TEST embedder (mandate §13: no model downloads).

    Two surfaces, both honest:
      - embed(crop): content-hash vector — the same crop BYTES always
        produce the same vector (stability contract; no appearance
        semantics claimed).
      - subject_vector(subject, variant): a synthetic 'appearance'
        for a named test subject. Same subject (+variant) -> near-
        identical vectors (high cosine); different subjects -> near-
        orthogonal (low cosine); higher variant -> more intra-subject
        noise. Tests use this to construct controlled similarity the
        way a real Re-ID model would behave, without pretending to
        be one.
    """

    name = "dummy"

    #: fraction of the vector that is the subject anchor (rest = variant noise)
    SUBJECT_ANCHOR_WEIGHT = 0.92

    def __init__(self, dim: int = 64) -> None:
        self._dim = dim

    def embed(self, crop_bgr: np.ndarray) -> np.ndarray:
        # Content hash: same bytes -> same vector (stability).
        content = hash(crop_bgr.tobytes()) & 0xFFFFFFFF
        rng = np.random.default_rng(content)
        return l2_normalize(rng.standard_normal(self._dim))

    def subject_vector(self, subject: str, variant: int = 0) -> np.ndarray:
        """Synthetic 'appearance of subject' test vector."""
        anchor_rng = np.random.default_rng(
            (hash(subject) & 0xFFFFFFFF) ^ 0xA5A5)
        anchor = anchor_rng.standard_normal(self._dim)
        if variant:
            noise_rng = np.random.default_rng(
                ((hash(subject) & 0xFFFFFFFF) * 31 + variant) & 0xFFFFFFFF)
            noise = noise_rng.standard_normal(self._dim)
            vec = (self.SUBJECT_ANCHOR_WEIGHT * anchor
                   + (1.0 - self.SUBJECT_ANCHOR_WEIGHT) * 3.0 * noise)
        else:
            vec = anchor
        return l2_normalize(vec)
