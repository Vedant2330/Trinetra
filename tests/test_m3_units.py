"""M3 unit tests — annotation purity + frame slot semantics."""

from __future__ import annotations

import threading

import cv2
import numpy as np

from backend.services.frame_slot import LatestFrameSlot
from backend.vision import TrackedObject
from backend.vision.annotation import annotate


def _frame() -> np.ndarray:
    return np.full((480, 640, 3), 40, dtype=np.uint8)


def _obj(tid=7, cls="person", cid=0, conf=0.91, bbox=(100, 120, 200, 320)):
    return TrackedObject(track_id=tid, class_id=cid, class_name=cls,
                         confidence=conf, bbox=list(bbox))


# ---- annotation ----

def test_annotate_returns_new_frame_and_preserves_original():
    f = _frame()
    before = f.copy()
    out = annotate(f, [_obj()])
    assert out is not f
    assert np.array_equal(f, before), "input frame was mutated"
    assert out.shape == f.shape and out.dtype == f.dtype
    assert not np.array_equal(out, before), "nothing was drawn"


def test_annotate_draws_bbox_and_real_label():
    f = _frame()
    out = annotate(f, [_obj(tid=7, conf=0.91234)])
    # bbox area must be altered vs original
    region = out[120:320, 100:200]
    assert (region != 40).any()
    # label text present (non-empty pixels above/inside bbox)
    assert (out[100:130, 90:230] != 40).any()


def test_annotate_hides_missing_track_id():
    out = annotate(_frame(), [_obj(tid=None)])
    assert out is not None  # no crash; ID simply not drawn


def test_annotate_empty_objects_still_hud():
    out = annotate(_frame(), [], pipeline_fps=25.4, device="mps")
    assert (out[:40, :400] != 40).any(), "FPS HUD not drawn"


def test_annotate_handles_zero_fps():
    out = annotate(_frame(), [], pipeline_fps=0.0)
    assert out is not None


def test_annotate_clamps_out_of_bounds_boxes():
    out = annotate(_frame(), [_obj(bbox=(-50, -50, 700, 900))])
    assert out is not None  # no crash on degenerate boxes


def test_jpeg_roundtrip_valid():
    out = annotate(_frame(), [_obj()])
    ok, buf = cv2.imencode(".jpg", out)
    assert ok
    decoded = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    assert decoded.shape == out.shape
    # browser-compatible JPEG magic: FF D8
    assert bytes(buf[:2]) == b"\xff\xd8"


# ---- LatestFrameSlot ----

def test_slot_publish_then_consume():
    s = LatestFrameSlot()
    s.publish(b"frame-1")
    assert s.wait_new(timeout=0.1) == b"frame-1"
    assert s.wait_new(timeout=0.05) is None      # consumed


def test_slot_latest_replaces_not_queues():
    s = LatestFrameSlot()
    s.publish(b"old")
    s.publish(b"new")
    assert s.wait_new(timeout=0.1) == b"new"      # no backlog


def test_slot_peek_non_consuming():
    s = LatestFrameSlot()
    s.publish(b"x")
    assert s.peek() == b"x"
    assert s.peek() == b"x"                       # still there
    assert s.wait_new(timeout=0.1) == b"x"         # consumable once


def test_slot_wait_blocks_until_publish():
    s = LatestFrameSlot()

    def later():
        import time
        time.sleep(0.05)
        s.publish(b"late")

    threading.Thread(target=later, daemon=True).start()
    assert s.wait_new(timeout=2.0) == b"late"      # woke on notify
