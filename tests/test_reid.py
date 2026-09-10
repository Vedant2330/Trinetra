"""TRINETRA Re-ID unit tests (Phase 2 port of the M8 suite, verbatim
semantics) — deterministic synthetic embeddings ONLY (mandate §13: no
GPU/model download for unit tests).

The DummyEmbedder.subject_vector() surface constructs controlled
similarity: same subject (+variant noise) -> ~0.9 cosine; different
subjects -> ~0. All 15 mandated cases are covered, numbered in
docstrings as [T1]..[T15].

Port notes (Phase 2): TorchScriptEmbedder stays the honest-unavailable
gate in T14/T14b (an explicit missing path — availability is
per-embedder-instance, honestly). The real-model tests for the new
OpenCVDnnEmbedder (cv2.dnn + the committed fast-reid ONNX) live in
tests/test_reid_port.py.
"""

from __future__ import annotations

import threading

import numpy as np
import pytest

from backend.analytics.base import EventDraft, FrameContext
from backend.reid import (
    DummyEmbedder,
    GlobalIdentityCorrelator,
    GlobalMovementHistory,
    IdentityGallery,
    MatchState,
    Matcher,
    MatcherPolicy,
    MultiCameraReIdService,
    ReIDSamplingPolicy,
    SamplePolicy,
    TorchScriptEmbedder,
    build_clip_summary,
    make_embedder,
)
from backend.reid.embedder import preprocess_crop
from backend.reid.identity import IdentityObservation
from backend.state import TrackStore
from backend.vision import TrackedObject

# ---------------------------------------------------------------- fixtures

W, H = 1920, 1080


def ctx(tick, wall_ts=None, shape=(W, H), is_night=False):
    return FrameContext(tick=tick, wall_ts=wall_ts if wall_ts is not None
                       else float(tick), video_ts=float(tick),
                       luminance=128.0, is_night=is_night, shape=shape)


@pytest.fixture
def embedder():
    return DummyEmbedder()


@pytest.fixture
def subject():
    """(v_a, v_a2, v_b): same-subject variants + a different subject."""
    e = DummyEmbedder()
    return (e.subject_vector("person-A", variant=1),
            e.subject_vector("person-A", variant=2),
            e.subject_vector("person-B", variant=1))


@pytest.fixture
def correlator():
    return GlobalIdentityCorrelator()


def obs(camera, track, vec, ts):
    return IdentityObservation(camera_id=camera, track_id=track,
                               embedding=vec, wall_ts=ts)


def mk_track(tid, foot_x, foot_y, bbox_h=100):
    cx, y2 = foot_x, foot_y
    y1 = max(0.0, y2 - bbox_h)
    return TrackedObject(track_id=tid, class_id=0, class_name="person",
                         confidence=0.9, bbox=[cx - 20, y1, cx + 20, y2])


# ---------------------------------------------------------------- [T1]/[T2]

def test_t1_same_embedding_same_identity(correlator, subject):
    """[T1] identical embedding on two cameras -> same global id."""
    v_a, _, _ = subject
    r1 = correlator.observe(obs("CAM-01", 17, v_a, 1000.0))
    r2 = correlator.observe(obs("CAM-02", 42, v_a, 1010.0))
    assert r1.is_new
    assert r2.matched
    assert r2.identity.global_person_id == r1.identity.global_person_id


def test_t2_different_embeddings_different_identity(correlator, subject):
    """[T2] clearly different embeddings -> different identities."""
    v_a, _, v_b = subject
    r1 = correlator.observe(obs("CAM-01", 17, v_a, 1000.0))
    r2 = correlator.observe(obs("CAM-02", 42, v_b, 1010.0))
    assert r1.identity.global_person_id != r2.identity.global_person_id
    assert r2.is_new


# ---------------------------------------------------------------- [T3]

def test_t3_ambiguous_similarity_is_candidate_not_confirmed(subject):
    """[T3] similarity in the candidate band -> CANDIDATE, and the
    track still gets its OWN identity (never linked on candidate)."""
    v_a, _, _ = subject
    # craft an ambiguous vector: midway between A and B anchors
    e = DummyEmbedder()
    v_mid = e.subject_vector("person-A", variant=1)
    v_b2 = e.subject_vector("person-A", variant=60)  # heavy noise variant
    sim = float(np.dot(v_mid, v_b2))
    # build a matcher with the candidate band pinned around this sim
    m = Matcher(MatcherPolicy(
        confirm_similarity=sim + 0.05, candidate_similarity=sim - 0.05,
        max_gap_s=600.0))
    g = IdentityGallery()
    ident = g.mint(1000.0)
    g.add_exemplar(ident, "CAM-01", v_mid)
    c = GlobalIdentityCorrelator(gallery=g, matcher=m)
    r = c.observe(obs("CAM-02", 42, v_b2, 1010.0))
    assert r.result.state is MatchState.CANDIDATE
    assert not r.matched
    assert r.is_new                      # own identity, not a link
    assert ident.candidates              # candidate recorded for review


def test_t3b_below_candidate_never_matches(subject):
    """0.55-style similarity must NOT merge (mandate §4 example)."""
    v_a, _, v_b = subject
    sim = float(np.dot(v_a, v_b))         # ~0 (different subjects)
    m = Matcher(MatcherPolicy(
        confirm_similarity=0.80, candidate_similarity=0.55))
    g = IdentityGallery()
    ident = g.mint(1000.0)
    g.add_exemplar(ident, "CAM-01", v_a)
    r = m.best_match(obs("CAM-02", 42, v_b, 1010.0), [ident])
    assert r.state is MatchState.UNMATCHED


# ---------------------------------------------------------------- [T4]/[T5]

def test_t4_two_camera_chain(correlator, subject):
    """[T4] CAM-01 Track 17 -> CAM-02 Track 42 same identity."""
    v_a, v_a2, _ = subject
    correlator.observe(obs("CAM-01", 17, v_a, 1000.0))
    r2 = correlator.observe(obs("CAM-02", 42, v_a2, 1010.0))
    assert r2.matched
    assert r2.transitioned
    assert len(correlator.gallery) == 1


def test_t5_three_camera_chain(correlator, subject):
    """[T5] 17 -> 42 -> 81 across three cameras, one global id."""
    v_a, v_a2, _ = subject
    r1 = correlator.observe(obs("CAM-01", 17, v_a, 1000.0))
    r2 = correlator.observe(obs("CAM-02", 42, v_a2, 1010.0))
    v_a3 = DummyEmbedder().subject_vector("person-A", variant=3)
    r3 = correlator.observe(obs("CAM-03", 81, v_a3, 1020.0))
    ids = {r1.identity.global_person_id, r2.identity.global_person_id,
           r3.identity.global_person_id}
    assert len(ids) == 1
    ident = r3.identity
    assert ident.cameras_visited == ["CAM-01", "CAM-02", "CAM-03"]
    assert sorted(t for (_c, t) in ident.local_track_ids) == [17, 42, 81]


# ---------------------------------------------------------------- [T6]/[T7]

def test_t6_same_local_track_retains_identity(correlator, subject):
    """[T6] re-observing the same (camera, track) keeps its identity."""
    v_a, _, _ = subject
    r1 = correlator.observe(obs("CAM-01", 17, v_a, 1000.0))
    r2 = correlator.observe(obs("CAM-01", 17, v_a, 1001.0))
    assert not r2.is_new
    assert r2.identity.global_person_id == r1.identity.global_person_id
    assert len(correlator.gallery) == 1


def test_t7_different_people_stay_separate(correlator):
    """[T7] three different people across three cameras -> three ids."""
    e = DummyEmbedder()
    people = [e.subject_vector(f"person-{i}", variant=1) for i in range(3)]
    outs = []
    for i, vec in enumerate(people):
        outs.append(correlator.observe(
            obs(f"CAM-0{i+1}", 10 + i, vec, 1000.0 + i)).identity)
    assert len({o.global_person_id for o in outs}) == 3
    assert len(correlator.gallery) == 3


# ---------------------------------------------------------------- [T8]

def test_t8_identity_survives_track_id_change(correlator, subject):
    """[T8] local track ID changes across cameras (ByteTrack locality):
    the global identity carries over via appearance, not the local id."""
    v_a, v_a2, _ = subject
    correlator.observe(obs("CAM-01", 17, v_a, 1000.0))
    # CAM-01 tracker restarts: new local id 55, same person
    r = correlator.observe(obs("CAM-01", 55, v_a2, 1030.0))
    assert r.matched
    assert r.identity.cameras_visited == ["CAM-01"]
    assert len(r.identity.local_track_ids) == 2


# ---------------------------------------------------------------- [T9]

def test_t9_zone_intrusion_attaches_global_person_id(subject):
    """[T9] a ZONE_ENTRY draft gets global_person_id attached (the
    fence stays the only zone system; identity rides metadata)."""
    v_a, _, _ = subject
    svc = MultiCameraReIdService(embedder=None)  # replaced below
    svc = MultiCameraReIdService(
        embedder=DummyEmbedder(),
        correlator=GlobalIdentityCorrelator(),
        history=GlobalMovementHistory())
    svc.register_camera("CAM-03")
    svc.observe_embedding("CAM-03", ctx(100, wall_ts=100.0),
                          track_id=81, embedding=v_a)
    draft = EventDraft(
        type="ZONE_ENTRY", track_ids=[81], zone_id="restricted-zone",
        direction=None, confidence=1.0,
        metadata={"is_night": False, "zone_type": "RESTRICTED",
                  "video_ts": 100.0, "tick": 100})
    svc.enrich_drafts("CAM-03", [draft])
    assert draft.metadata["global_person_id"] == \
        svc.identity_for("CAM-03", 81).global_person_id
    tl = svc.history.timeline(draft.metadata["global_person_id"])
    assert any(p["kind"] == "zone_entry" and
               p["zone_id"] == "restricted-zone" for p in tl)


# ---------------------------------------------------------------- [T10]

def test_t10_global_history_ordered(correlator, subject):
    """[T10] movement history is (wall_ts, seq) ordered."""
    v_a, v_a2, _ = subject
    svc = MultiCameraReIdService(
        embedder=DummyEmbedder(),
        correlator=correlator, history=GlobalMovementHistory())
    svc.register_camera("CAM-01")
    svc.register_camera("CAM-02")
    svc.observe_embedding("CAM-01", ctx(10, wall_ts=1000.0), 17, v_a)
    svc.observe_embedding("CAM-02", ctx(20, wall_ts=1010.0), 42, v_a2)
    pid = correlator.all_identities()[0].global_person_id
    tl = svc.history.timeline(pid)
    assert [p["wall_ts"] for p in tl] == sorted(p["wall_ts"] for p in tl)
    kinds = [p["kind"] for p in tl]
    assert kinds[0] == "first_seen"
    assert "camera_transition" in kinds


# ---------------------------------------------------------------- [T11]

def test_t11_duplicate_observations_no_duplicate_transitions(subject):
    """[T11] re-sampling the same track must not duplicate transitions."""
    v_a, v_a2, _ = subject
    svc = MultiCameraReIdService(
        embedder=DummyEmbedder(),
        correlator=GlobalIdentityCorrelator(),
        history=GlobalMovementHistory())
    svc.register_camera("CAM-01")
    svc.register_camera("CAM-02")
    drafts = []
    drafts += svc.observe_embedding("CAM-01", ctx(1, wall_ts=1000.0), 17, v_a)
    drafts += svc.observe_embedding("CAM-02", ctx(2, wall_ts=1010.0), 42, v_a2)
    # duplicate: same track re-sampled repeatedly
    for i in range(5):
        drafts += svc.observe_embedding(
            "CAM-02", ctx(3 + i, wall_ts=1011.0 + i), 42, v_a2)
    transitions = [d for d in drafts
                   if d.type == "PERSON_CAMERA_TRANSITION"]
    assert len(transitions) == 1           # exactly one CAM-02 transition
    pid = svc.correlator.all_identities()[0].global_person_id
    tl = [p for p in svc.history.timeline(pid)
          if p["kind"] == "camera_transition"]
    assert len(tl) == 1


# ---------------------------------------------------------------- [T12]

def test_t12_concurrent_observations_gallery_integrity():
    """[T12] the SAME person observed CONCURRENTLY on 4 cameras:
    the correlator lock must serialize everything into exactly ONE
    identity, all observations accounted for, no corruption."""
    e = DummyEmbedder()
    c = GlobalIdentityCorrelator()
    n_threads, n_obs = 4, 50
    errors: list[Exception] = []

    def worker(cam_i: int) -> None:
        try:
            for i in range(n_obs):
                # SAME subject on every thread, camera-specific track ids
                vec = e.subject_vector("person-shared", variant=i % 3)
                c.observe(obs(f"CAM-{cam_i:02d}", i, vec,
                              1000.0 + i * 0.1))
        except Exception as exc:            # noqa: BLE001 — record, don't hide
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(k,))
               for k in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    # one shared person -> exactly ONE global identity
    assert len(c.gallery) == 1
    ident = c.all_identities()[0]
    assert len(ident.cameras_visited) == n_threads
    # all observations accounted: 4 threads x 50
    assert ident.observations == n_threads * n_obs
    # every (camera, track) binding landed
    assert len(ident.track_bindings) == n_threads * n_obs


def test_t12b_concurrent_distinct_people_no_cross_links():
    """Concurrent DISTINCT people stay distinct (no cross-thread
    identity bleed under the lock)."""
    e = DummyEmbedder()
    c = GlobalIdentityCorrelator()
    errors: list[Exception] = []

    def worker(k: int) -> None:
        try:
            vec = e.subject_vector(f"person-{k}")
            for i in range(20):
                c.observe(obs(f"CAM-{k:02d}", i, vec, 1000.0 + i))
        except Exception as exc:            # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(k,))
               for k in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert len(c.gallery) == 4              # 4 people, 4 identities
    for ident in c.all_identities():
        assert len(ident.cameras_visited) == 1   # each person on own camera


# ---------------------------------------------------------------- [T13]

def test_t13_selective_sampling_reduces_inference():
    """[T13] sampling policy cuts embed calls vs every-frame."""
    every = ReIDSamplingPolicy(SamplePolicy.every_frame())
    real = ReIDSamplingPolicy()            # config defaults
    ticks, wall = 100, 0.0
    for tick in range(ticks):
        every.should_sample(1, tick, wall + tick, frames_seen=tick + 1)
        real.should_sample(1, tick, wall + tick, frames_seen=tick + 1)
    # every-frame samples every tick; selective skips
    assert every._last_tick[1] == ticks - 1
    sampled_ticks = [t for t in range(ticks)
                     if real.should_sample(1, t, wall + t,
                                           frames_seen=t + 1)]
    assert len(sampled_ticks) < ticks
    # stability gate: nothing before min_frames_seen (except forced)
    strict = ReIDSamplingPolicy(SamplePolicy(
        interval_ticks=25, min_frames_seen=5, min_gap_s=0.0))
    assert not strict.should_sample(9, 1, 100.0, frames_seen=1)
    assert not strict.should_sample(9, 2, 101.0, frames_seen=2)
    # forced/stable triggers bypass the interval
    assert strict.should_sample(9, 2, 101.0, frames_seen=2, force=True)
    p = ReIDSamplingPolicy()
    assert p.should_sample(1, 50, 500.0, frames_seen=50,
                           camera_changed=True)


# ---------------------------------------------------------------- [T14]

def test_t14_no_identity_fabricated_without_embedding(tmp_path):
    """[T14] unavailable embedder -> process_tick is a NO-OP: no
    drafts, no gallery entries, no exceptions. (Uses an explicit
    missing path so the test holds even when a real models/reid.ts
    exists — availability is per-embedder-instance, honestly.)"""
    ts = TorchScriptEmbedder(
        model_path=str(tmp_path / "definitely-missing.ts"))
    assert not ts.available               # no model file at this path
    svc = MultiCameraReIdService(embedder=ts)
    svc.register_camera("CAM-01")
    store = TrackStore()
    store.update([mk_track(7, 960, 900)], tick=1, wall_ts=100.0)
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    drafts = svc.process_tick("CAM-01", ctx(1, wall_ts=100.0),
                              store.view(), frame)
    assert drafts == []
    assert len(svc.correlator.gallery) == 0


def test_t14b_unavailable_embedder_reports_honestly(tmp_path):
    # config default (torchscript) with a missing model path: honest gate
    missing = TorchScriptEmbedder(
        model_path=str(tmp_path / "nope.ts"))
    assert missing.available is False
    svc = MultiCameraReIdService(embedder=missing)
    assert svc.embedder_available is False
    assert make_embedder("dummy").available
    with pytest.raises(ValueError):
        make_embedder("bogus")


# ---------------------------------------------------------------- [T15]

def test_t15_event_payload_compatible_with_event_engine(subject):
    """[T15] PERSON_IDENTITY_MATCHED / PERSON_CAMERA_TRANSITION drafts
    pass the REAL EventEngine unchanged (INFO system-style events,
    no snapshot, sse_json shape intact)."""
    from backend.events.engine import EventEngine

    v_a, v_a2, _ = subject
    svc = MultiCameraReIdService(
        embedder=DummyEmbedder(),
        correlator=GlobalIdentityCorrelator(),
        history=GlobalMovementHistory())
    svc.register_camera("CAM-01")
    svc.register_camera("CAM-02")
    committed: list = []
    engine = EventEngine("CAM-01", "sess-test",
                         writer=None, hub=None, dao=None)

    d1 = svc.observe_embedding("CAM-01", ctx(1, wall_ts=1000.0), 17, v_a)
    d2 = svc.observe_embedding("CAM-02", ctx(2, wall_ts=1010.0), 42, v_a2)
    drafts = d1 + d2
    out = engine.commit(drafts, annotated_jpeg=None,
                        ctx=ctx(2, wall_ts=1010.0))
    assert len(out) == 2
    assert all(e.type in ("PERSON_IDENTITY_MATCHED",
                          "PERSON_CAMERA_TRANSITION") for e in out)
    for e in out:
        j = e.sse_json()
        assert j["severity"] == "INFO"     # ladder treats new types as INFO
        assert j["track_ids"]
        assert "global_person_id" in e.metadata
    # transition event carries both cameras
    tr = next(e for e in out if e.type == "PERSON_CAMERA_TRANSITION")
    assert tr.metadata["camera_id"] == "CAM-02"
    assert tr.metadata["global_person_id"].startswith("P-")
    committed.extend(out)
    assert len(committed) == 2


# ---------------------------------------------------------------- summary

def test_clip_summary_from_real_state(subject):
    """Deterministic summary derived ONLY from gallery+history."""
    v_a, v_a2, _ = subject
    svc = MultiCameraReIdService(
        embedder=DummyEmbedder(),
        correlator=GlobalIdentityCorrelator(),
        history=GlobalMovementHistory())
    svc.register_camera("CAM-01")
    svc.register_camera("CAM-02")
    svc.register_camera("CAM-03")
    svc.observe_embedding("CAM-01", ctx(1, wall_ts=1000.0), 17, v_a)
    svc.observe_embedding("CAM-02", ctx(2, wall_ts=1010.0), 42, v_a2)
    svc.observe_embedding("CAM-03", ctx(3, wall_ts=1020.0), 81,
                          DummyEmbedder().subject_vector("person-C"))
    svc.enrich_drafts("CAM-03", [EventDraft(
        type="ZONE_ENTRY", track_ids=[81], zone_id="restricted-zone-3",
        direction=None, confidence=1.0,
        metadata={"video_ts": 1020.0})])
    s = build_clip_summary(svc.correlator, svc.history, alerts=1,
                           clip_duration=42.3)
    d = s.as_dict()
    assert d["unique_global_persons"] == 2
    assert d["cameras"] == ["CAM-01", "CAM-02", "CAM-03"]
    assert d["tracks"] == 3
    assert d["zones_entered"] == ["restricted-zone-3"]
    assert d["identity_transitions"] == 1
    assert d["alerts"] == 1
    assert d["clip_duration"] == 42.3
    mandated = s.as_mandated_dict()
    assert set(mandated) == {
        "clip_duration", "unique_global_persons", "cameras", "tracks",
        "zones_entered", "tripwires_crossed", "identity_transitions",
        "alerts"}


# ---------------------------------------------------------------- misc

def test_preprocess_contract():
    """The frozen preprocessing contract shape (audited steps)."""
    crop = (np.random.default_rng(0).random((300, 120, 3)) * 255
            ).astype(np.uint8)
    x = preprocess_crop(crop)
    assert x.shape == (1, 3, 128, 256)          # batch, CHW, 256x128
    assert x.dtype == np.float32
    assert 0.0 <= x.min() and x.max() <= 255.0  # RAW scale, no /255
    with pytest.raises(ValueError):
        preprocess_crop(np.zeros((1, 1, 3), dtype=np.uint8))


def test_history_rejects_invented_kinds():
    h = GlobalMovementHistory()
    from backend.reid.identity import MovementPoint
    with pytest.raises(ValueError):
        h.record("P-0001", MovementPoint(
            wall_ts=1.0, camera_id="CAM-01", track_id=1,
            kind="acting_suspiciously"))          # banned verb


def test_gallery_minting_monotonic():
    g = IdentityGallery()
    a = g.mint(1.0); b = g.mint(2.0)
    assert a.global_person_id == "P-0001"
    assert b.global_person_id == "P-0002"
    assert a.global_person_id != b.global_person_id


def test_matcher_temporal_veto(subject):
    """Temporal implausibility demotes CONFIRMED to CANDIDATE."""
    v_a, v_a2, _ = subject
    m = Matcher(MatcherPolicy(confirm_similarity=0.80,
                              candidate_similarity=0.55, max_gap_s=60.0))
    g = IdentityGallery()
    ident = g.mint(1000.0)
    g.add_exemplar(ident, "CAM-01", v_a)
    r = m.best_match(obs("CAM-02", 42, v_a2, 1200.0), [ident])
    assert r.state is MatchState.CANDIDATE     # gap 200s > 60s ceiling
    r2 = m.best_match(obs("CAM-02", 42, v_a2, 1030.0), [ident])
    assert r2.state is MatchState.CONFIRMED
