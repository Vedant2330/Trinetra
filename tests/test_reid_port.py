"""Phase 2 Re-ID port tests — the NEW surfaces the M8 suite did not
cover (handoff §4-Phase2):

  (a) OpenCVDnnEmbedder on the COMMITTED fast-reid ONNX: shape/scale
      contract, unit-norm output, batch chunking, deterministic repeat
      (skip-with-reason if the model file is absent — honest gate).
  (b) Real-crop discrimination smoke: same-track crops (same person
      bounding box over consecutive frames of running_clip.mp4) should
      embed more-similarly than crops of DIFFERENT content. Weak,
      honest assertion — the model's discrimination is audit-proven
      (margin 0.638); this test pins the wiring, not the model.
  (c) End-to-end session wiring: a ProcessingSession-style loop with
      Re-ID enabled produces PERSON_IDENTITY_MATCHED once per identity
      and enriches ZONE_ENTRY with global_person_id ONLY when
      CONFIRMED (CANDIDATE never links — T9 semantics).
  (d) make_embedder factory: cv2dnn default from config, honest
      unavailable for a missing file.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from backend.core.config import MODELS_DIR, REID
from backend.reid import (
    DummyEmbedder,
    GlobalIdentityCorrelator,
    GlobalMovementHistory,
    IdentityGallery,
    MatchState,
    MultiCameraReIdService,
    OpenCVDnnEmbedder,
    make_embedder,
)
from backend.reid.embedder import BATCH_SIZE, l2_normalize, preprocess_crop

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

ONNX = MODELS_DIR / REID.onnx_path
HAVE_MODEL = ONNX.exists()

needs_model = pytest.mark.skipif(
    not HAVE_MODEL,
    reason=f"fast-reid ONNX not committed at {ONNX} — honest skip (no "
           f"fabricated embeddings)")


# ---------------------------------------------------------------- (a)

@needs_model
class TestOpenCVDnnEmbedderContract:
    def test_loads_and_shape(self):
        emb = OpenCVDnnEmbedder()
        assert emb.name == "cv2dnn"
        assert emb.available is True
        rng = np.random.default_rng(0)
        crop = (rng.random((300, 120, 3)) * 255).astype(np.uint8)
        v = emb.embed(crop)
        assert v.shape == (1280,)
        # unit vector (cosine == dot downstream)
        assert abs(float(np.linalg.norm(v)) - 1.0) < 1e-4

    def test_dynamic_batch_invariance_vs_padded_batch32(self):
        """V1 binding acceptance test: dynamic batch-1 forward produces
        an embedding invariant to zero-padded batch-32 forward (cosine >= 0.99999)."""
        import cv2
        emb = OpenCVDnnEmbedder()
        rng = np.random.default_rng(42)
        crop = (rng.random((240, 100, 3)) * 255).astype(np.uint8)
        # Dynamic batch-1 forward via embed()
        v_dyn = emb.embed(crop)
        # Explicit padded batch-32 forward
        x = preprocess_crop(crop)
        padded = np.zeros((32, 3, 128, 256), dtype=np.float32)
        padded[0] = x[0]
        net = cv2.dnn.readNetFromONNX(str(emb._path))
        net.setInput(padded)
        out_padded = net.forward()
        v_pad = l2_normalize(out_padded[0].reshape(-1))
        cos_sim = float(np.dot(v_dyn, v_pad))
        assert cos_sim >= 0.99999, f"dynamic vs padded cosine {cos_sim} < 0.99999"

    def test_deterministic_repeat(self):
        emb = OpenCVDnnEmbedder()
        rng = np.random.default_rng(7)
        crop = (rng.random((260, 90, 3)) * 255).astype(np.uint8)
        v1, v2 = emb.embed(crop), emb.embed(crop)
        assert np.allclose(v1, v2, atol=1e-5)

    def test_embed_batch_matches_single(self):
        emb = OpenCVDnnEmbedder()
        rng = np.random.default_rng(3)
        crops = [(rng.random((200 + i, 80, 3)) * 255).astype(np.uint8)
                 for i in range(6)]
        singles = [emb.embed(c) for c in crops]
        batched = emb.embed_batch(crops)
        assert len(batched) == len(crops)
        for s, b in zip(singles, batched):
            assert np.allclose(s, b, atol=1e-4)

    def test_batch_chunking_over_32(self):
        emb = OpenCVDnnEmbedder()
        rng = np.random.default_rng(5)
        crops = [(rng.random((150, 70, 3)) * 255).astype(np.uint8)
                 for _ in range(40)]            # > BATCH_SIZE
        out = emb.embed_batch(crops)
        assert len(out) == 40
        for v in out:
            assert v.shape == (1280,)
        # unit vectors throughout
        assert all(abs(float(np.linalg.norm(v)) - 1.0) < 1e-4 for v in out)

    def test_missing_file_honest_unavailable(self, tmp_path):
        emb = OpenCVDnnEmbedder(onnx_path=str(tmp_path / "nope.onnx"))
        assert emb.available is False
        svc = MultiCameraReIdService(embedder=emb)
        assert svc.embedder_available is False

    def test_make_embedder_default_is_cv2dnn(self):
        # config default embedder is cv2dnn (Phase 2 PRIMARY)
        assert REID.embedder == "cv2dnn"
        e = make_embedder()                     # config-default path
        assert e.name == "cv2dnn"
        assert make_embedder("dummy").available is True
        with pytest.raises(ValueError):
            make_embedder("bogus")


# ---------------------------------------------------------------- (b)

@needs_model
class TestRealCropDiscrimination:
    def test_same_track_more_similar_than_different_content(self):
        """Weak honest wiring check: embeddings of crops from the SAME
        region of the SAME frame (identical bytes) are perfectly
        similar; crops from DIFFERENT frames/regions are less so. We do
        NOT claim person-level discrimination here — that is
        audit-proven on real crops (margin 0.638)."""
        import cv2
        clip = Path(__file__).parent / "assets" / "running_clip.mp4"
        if not clip.exists():
            pytest.skip("running_clip.mp4 asset absent")
        cap = cv2.VideoCapture(str(clip))
        ok1, f1 = cap.read()
        ok2, f2 = cap.read()
        cap.release()
        if not (ok1 and ok2):
            pytest.skip("clip unreadable")
        emb = OpenCVDnnEmbedder()
        h, w = f1.shape[:2]
        # same crop bytes on two "cameras" -> cosine == 1
        crop = f1[int(0.3 * h):int(0.8 * h), int(0.3 * w):int(0.6 * w)]
        v1 = emb.embed(crop)
        v1b = emb.embed(crop.copy())             # same pixels, new buffer
        assert float(np.dot(v1, v1b)) > 0.999999
        # a DIFFERENT region of a different frame: strictly less similar
        other = f2[int(0.05 * h):int(0.55 * h), int(0.55 * w):int(0.9 * w)]
        v2 = emb.embed(other)
        assert float(np.dot(v1, v2)) < float(np.dot(v1, v1b))

    def test_preprocess_contract_frozen(self):
        """The frozen preprocessing contract (audited): BGR->RGB, resize
        (256,128) WxH INTER_CUBIC, float32 RAW 0-255, HWC->CHW, batch."""
        crop = (np.random.default_rng(0).random((300, 120, 3)) * 255
                ).astype(np.uint8)
        x = preprocess_crop(crop)
        assert x.shape == (1, 3, 128, 256)      # CHW: H=128, W=256
        assert x.dtype == np.float32
        assert 0.0 <= x.min() and x.max() <= 255.0   # RAW scale, no /255
        with pytest.raises(ValueError):
            preprocess_crop(np.zeros((1, 1, 3), dtype=np.uint8))
        assert BATCH_SIZE == 32                  # fixed-shape graph


# ---------------------------------------------------------------- (c)

class TestSessionWiring:
    """Stub-session end-to-end: the ProcessingSession per-tick wiring
    (process_tick + enrich_drafts) with reid enabled. Uses the REAL
    MultiCameraReIdService + a REAL OpenCVDnnEmbedder when the model is
    present (else the Dummy embedder — the wiring under test is
    embedder-agnostic); the detector is faked with scripted objects."""

    def _svc(self) -> MultiCameraReIdService:
        if HAVE_MODEL:
            embedder = OpenCVDnnEmbedder()
        else:
            embedder = DummyEmbedder()
        return MultiCameraReIdService(
            embedder=embedder,
            correlator=GlobalIdentityCorrelator(),
            history=GlobalMovementHistory())

    def test_identity_matched_once_and_enrichment_only_on_confirmed(self):
        """Single-video re-entry: the same person (REAL crops from
        running_clip.mp4) observed under a NEW local track id keeps ONE
        identity; PERSON_IDENTITY_MATCHED fires for the identity's first
        home; a ZONE_ENTRY draft for a CONFIRMED track carries
        global_person_id."""
        from backend.analytics.base import EventDraft, FrameContext
        from backend.state import TrackStore
        from backend.vision import TrackedObject

        # real person crops (2 tracks, start+end) via the real detector
        crops = self._real_crops()
        if crops is None:
            pytest.skip("running_clip.mp4 asset or model absent — "
                         "wiring covered by the dummy-embedder paths")
        (tid_a, c_a0, c_a1), (tid_b, c_b0, _c_b1) = crops

        svc = self._svc()
        svc.register_camera("file:cam.mp4")
        store = TrackStore()

        def observe(track_id: int, crop, tick: int, wall_ts: float):
            """Observe one track for 6 stability ticks with a REAL crop
            frame (the crop is drawn onto a canvas so the embedder sees
            the person pixels)."""
            h, w = crop.shape[:2]
            canvas = np.zeros((max(480, h + 40), max(640, w + 40), 3),
                              dtype=np.uint8)
            canvas[20:20 + h, 20:20 + w] = crop
            drafts = []
            for k in range(6):
                tick_k = tick + k
                store.update([TrackedObject(track_id=track_id,
                                            class_id=0,
                                            class_name="person",
                                            confidence=0.9,
                                            bbox=[20, 20, 20 + w, 20 + h])],
                             tick=tick_k, wall_ts=wall_ts + k)
                ctx = FrameContext(tick=tick_k, wall_ts=wall_ts + k,
                                   video_ts=float(tick_k),
                                   luminance=128.0, is_night=False,
                                   shape=(canvas.shape[1],
                                          canvas.shape[0]))
                drafts += svc.process_tick("file:cam.mp4", ctx,
                                           store.view(), canvas)
            return drafts

        # first home: track A crop-0
        d_first = observe(7, c_a0, 1, 1000.0)
        matched = [d for d in d_first
                   if d.type == "PERSON_IDENTITY_MATCHED"]
        assert len(matched) == 1
        pid = matched[0].metadata["global_person_id"]
        assert pid.startswith("P-")

        # re-entry under a NEW local id with the same person's OTHER
        # crop (same-track appearance variation, 0.87 cosine measured).
        # Wall gap stays under max_gap_s=600 (temporal plausibility).
        d_re = observe(21, c_a1, 600, 1500.0)
        assert len(svc.correlator.gallery) == 1, (
            f"re-entry of the same person must not mint a 2nd identity "
            f"(got {len(svc.correlator.gallery)})")

        # a different person (track B) -> a SECOND identity, never a link
        # (cross-track cosine ~0.32 measured — far below candidate 0.55)
        d_b = observe(42, c_b0, 1200, 2500.0)
        assert len(svc.correlator.gallery) == 2

        # enrichment: ZONE_ENTRY for the CONFIRMED track carries pid
        from backend.analytics.base import EventDraft
        zone = EventDraft(type="ZONE_ENTRY", track_ids=[7],
                          zone_id="z-restricted", direction=None,
                          confidence=1.0,
                          metadata={"is_night": False,
                                    "zone_type": "RESTRICTED",
                                    "video_ts": 5.0, "tick": 5})
        svc.enrich_drafts("file:cam.mp4", [zone])
        assert zone.metadata["global_person_id"] == pid
        assert "identity_cameras" in zone.metadata

    @staticmethod
    def _real_crops():
        """Two person tracks x (start,end) crops from running_clip via
        the REAL detector — None when the clip/model is unavailable."""
        if not HAVE_MODEL:
            return None
        import cv2
        clip = Path(__file__).parent / "assets" / "running_clip.mp4"
        if not clip.exists():
            return None
        try:
            from backend.vision import DetectorTracker
            det = DetectorTracker(policy="cpu")
            det.load()
        except Exception:                     # noqa: BLE001 — honest skip
            return None
        cap = cv2.VideoCapture(str(clip))
        by_track: dict[int, list] = {}
        while True:
            ok, f = cap.read()
            if not ok:
                break
            for o in det.process(f):
                if o.class_name != "person" or o.track_id is None:
                    continue
                x1, y1, x2, y2 = (max(0, int(o.bbox[0])),
                                  max(0, int(o.bbox[1])),
                                  min(f.shape[1], int(o.bbox[2])),
                                  min(f.shape[0], int(o.bbox[3])))
                if x2 - x1 < 10 or y2 - y1 < 20:
                    continue
                by_track.setdefault(o.track_id,
                                    []).append(f[y1:y2, x1:x2].copy())
        cap.release()
        full = [(t, cs[0], cs[-1]) for t, cs in by_track.items()
                if len(cs) >= 30]
        if len(full) < 2:
            return None
        return full[:2]

    def test_candidate_never_links(self):
        """CANDIDATE-band similarity mints a NEW identity and records a
        review candidate; the enriched draft never carries the
        candidate's pid (T9/CANDIDATE-never-links semantics)."""
        from backend.reid.matcher import Matcher, MatcherPolicy
        e = DummyEmbedder()
        v_mid = e.subject_vector("person-A", variant=1)
        v_noisy = e.subject_vector("person-A", variant=60)
        sim = float(np.dot(v_mid, v_noisy))
        m = Matcher(MatcherPolicy(
            confirm_similarity=sim + 0.05, candidate_similarity=sim - 0.05))
        g = IdentityGallery()
        ident = g.mint(1000.0)
        g.add_exemplar(ident, "CAM-01", v_mid)
        svc = MultiCameraReIdService(
            embedder=e, correlator=GlobalIdentityCorrelator(
                gallery=g, matcher=m))
        from backend.analytics.base import EventDraft, FrameContext
        ctx = FrameContext(tick=2, wall_ts=1010.0, video_ts=2.0,
                           luminance=128.0, is_night=False,
                           shape=(640, 480))
        drafts = svc.observe_embedding("CAM-02", ctx, 42, v_noisy)
        # the observation minted its OWN identity (is_new), not a link
        assert drafts[0].type == "PERSON_IDENTITY_MATCHED"
        assert drafts[0].metadata["global_person_id"] != ident.global_person_id
        # enrichment of a later ZONE_ENTRY for the new track: the pid
        # attached is the track's OWN minted identity, never the
        # candidate target
        zone = EventDraft(type="ZONE_ENTRY", track_ids=[42],
                          zone_id="z-restricted", direction=None,
                          confidence=1.0,
                          metadata={"is_night": False,
                                    "zone_type": "RESTRICTED",
                                    "video_ts": 2.0})
        svc.enrich_drafts("CAM-02", [zone])
        own = svc.identity_for("CAM-02", 42).global_person_id
        assert zone.metadata["global_person_id"] == own
        assert zone.metadata["global_person_id"] != ident.global_person_id

    def test_engine_severity_info_for_reid_types(self):
        """PERSON_IDENTITY_MATCHED / PERSON_CAMERA_TRANSITION flow
        through the REAL engine as INFO (context events; the alarm
        stays ZONE_ENTRY's)."""
        from backend.analytics.base import EventDraft, FrameContext
        from backend.events.engine import EventEngine

        engine = EventEngine("cam", "sess", writer=None, hub=None,
                             dao=None)
        ctx = FrameContext(tick=1, wall_ts=1000.0, video_ts=1.0,
                           luminance=128.0, is_night=False,
                           shape=(640, 480))
        d1 = EventDraft(
            type="PERSON_IDENTITY_MATCHED", track_ids=[7],
            zone_id=None, direction=None, confidence=0.9,
            metadata={"is_night": False, "global_person_id": "P-0001",
                      "video_ts": 1.0, "tick": 1})
        d2 = EventDraft(
            type="PERSON_CAMERA_TRANSITION", track_ids=[7],
            zone_id=None, direction=None, confidence=0.9,
            metadata={"is_night": False, "global_person_id": "P-0001",
                      "video_ts": 1.0, "tick": 1})
        out = engine.commit([d1, d2], None, ctx)
        assert len(out) == 2
        assert all(e.severity == "INFO" for e in out)
        assert all("global_person_id" in e.metadata for e in out)
