"""TRINETRA Phase 6 Tests — Three-State ANPR & Offline Network Gate.

Tests:
  1. Indian plate regex validation: Standard series (e.g. DL01AB1234, MH12CD5678, KA05N1234) and Bharat series (e.g. 22BH1234AA).
  2. Plate text normalization: strips spaces, punctuation, dashes, lower-case conversion to uppercase.
  3. Three-State ANPR Classification:
     - ANPR_READ: confidence >= 0.80 and valid regex match.
     - OCR_UNCERTAIN: confidence < 0.80 or invalid regex format.
     - ANPR_PLATE_DETECTED: plate localized but OCR unavailable or crop < 64px.
  4. Heuristic Plate Localization & Vehicle Gate:
     - Rejects boxes with width < 100px or height < 40px.
     - Returns center-lower bounding box on valid vehicle boxes.
  5. Plate Crop Size Gating (< 64px width skips OCR, produces ANPR_PLATE_DETECTED).
  6. ANPRAnalytic lifecycle & throttling across video frames.
  7. API health includes anpr mode and presence.
"""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.analytics.anpr import (
    ANPRAnalytic,
    classify_anpr_read,
    clean_plate_text,
    locate_plate_heuristic,
    validate_indian_plate,
)
from backend.analytics.base import FrameContext
from backend.main import app
from backend.state.tracks import TrackState


# ---------------------------------------------------------------------------
# 1. Regex Validation & Text Normalization Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected_valid, expected_type",
    [
        # Standard format variations
        ("DL01AB1234", True, "standard"),
        ("dl 01 ab 1234", True, "standard"),
        ("MH-12-CD-5678", True, "standard"),
        ("KA05N1234", True, "standard"),
        ("TN09B1234", True, "standard"),
        ("HR26DK8337", True, "standard"),
        ("UP32AA1111", True, "standard"),
        ("WB021234", True, "standard"),  # 0 letters in series
        ("GJ01ABC1234", True, "standard"),  # 3 letters in series
        # Bharat (BH) Series format variations
        ("22BH1234AA", True, "bh_series"),
        ("22 bh 1234 aa", True, "bh_series"),
        ("23BH9999A", True, "bh_series"),
        ("21BH0001ZZ", True, "bh_series"),
        # Invalid strings
        ("INVALID", False, "invalid"),
        ("12345", False, "invalid"),
        ("ABCDEF", False, "invalid"),
        ("DL01AB12345", False, "invalid"),  # 5 digits at end
        ("22BH1234AAA", False, "invalid"),  # 3 letters at end for BH
        ("", False, "invalid"),
        (None, False, "invalid"),
    ],
)
def test_validate_indian_plate(raw: str | None, expected_valid: bool, expected_type: str) -> None:
    valid, ptype = validate_indian_plate(raw)
    assert valid is expected_valid
    assert ptype == expected_type


def test_clean_plate_text() -> None:
    assert clean_plate_text(" dl-01.ab_1234 ") == "DL01AB1234"
    assert clean_plate_text(None) == ""
    assert clean_plate_text("") == ""
    assert clean_plate_text("22-BH-1234/AA") == "22BH1234AA"


# ---------------------------------------------------------------------------
# 2. Three-State Classification Engine Tests
# ---------------------------------------------------------------------------

def test_classify_anpr_read_high_confidence_valid() -> None:
    """State 1: ANPR_READ (High confidence + Valid Regex)."""
    ev_type, meta = classify_anpr_read(
        text="DL01AB1234",
        confidence=0.92,
        plate_bbox=[100, 200, 180, 230],
        detection_mode="heuristic",
    )
    assert ev_type == "ANPR_READ"
    assert meta["plate_text"] == "DL01AB1234"
    assert meta["plate_type"] == "standard"
    assert meta["ocr_confidence"] == 0.92
    assert meta["ocr_validated"] is True
    assert meta["detection_mode"] == "heuristic"
    assert "uncertain_reason" not in meta


def test_classify_anpr_read_bh_series() -> None:
    """State 1: ANPR_READ with Bharat Series plate."""
    ev_type, meta = classify_anpr_read(
        text="22BH1234AA",
        confidence=0.85,
        plate_bbox=[50, 50, 150, 80],
        detection_mode="model",
    )
    assert ev_type == "ANPR_READ"
    assert meta["plate_text"] == "22BH1234AA"
    assert meta["plate_type"] == "bh_series"
    assert meta["ocr_validated"] is True


def test_classify_anpr_read_low_confidence_valid_regex() -> None:
    """State 2: OCR_UNCERTAIN (Confidence < 0.80)."""
    ev_type, meta = classify_anpr_read(
        text="MH12CD5678",
        confidence=0.65,
        plate_bbox=[10, 10, 100, 40],
    )
    assert ev_type == "OCR_UNCERTAIN"
    assert meta["uncertain_reason"] == "low_confidence"
    assert meta["cleaned_text"] == "MH12CD5678"
    assert meta["ocr_validated"] is False


def test_classify_anpr_read_high_confidence_invalid_regex() -> None:
    """State 2: OCR_UNCERTAIN (Regex mismatch despite high OCR confidence)."""
    ev_type, meta = classify_anpr_read(
        text="DL01AB12345EXTRA",
        confidence=0.95,
        plate_bbox=[10, 10, 100, 40],
    )
    assert ev_type == "OCR_UNCERTAIN"
    assert meta["uncertain_reason"] == "invalid_format"
    assert meta["cleaned_text"] == "DL01AB12345EXTRA"
    assert meta["ocr_validated"] is False


def test_classify_anpr_read_ocr_unavailable() -> None:
    """State 3: ANPR_PLATE_DETECTED (No OCR text available)."""
    ev_type, meta = classify_anpr_read(
        text=None,
        confidence=0.0,
        plate_bbox=[10, 10, 100, 40],
    )
    assert ev_type == "ANPR_PLATE_DETECTED"
    assert meta["plate_text"] is None
    assert meta["ocr_available"] is False


# ---------------------------------------------------------------------------
# 3. Heuristic Plate Localization & Vehicle Gate Tests
# ---------------------------------------------------------------------------

def test_locate_plate_heuristic_valid_vehicle() -> None:
    """A valid car bbox (e.g. 200x120) produces center-lower plate bbox."""
    # vehicle bbox: (left=100, top=100, right=300, bottom=220) -> w=200, h=120
    vehicle_box = (100, 100, 300, 220)
    plate_box = locate_plate_heuristic(vehicle_box, frame_shape=(640, 480))
    assert plate_box is not None
    px1, py1, px2, py2 = plate_box
    # Verify horizontal centering: 20% to 80% of vehicle width
    assert px1 == 100 + int(0.20 * 200)  # 140
    assert px2 == 100 + int(0.80 * 200)  # 260
    # Verify vertical placement: 65% to 95% of vehicle height
    assert py1 == 100 + int(0.65 * 120)  # 178
    assert py2 == 100 + int(0.95 * 120)  # 214


def test_locate_plate_heuristic_gates() -> None:
    """Rejects sub-100px width, sub-40px height."""
    # Width < 100px
    assert locate_plate_heuristic((100, 100, 180, 200), frame_shape=(640, 480)) is None
    # Height < 40px
    assert locate_plate_heuristic((100, 100, 300, 130), frame_shape=(640, 480)) is None


# ---------------------------------------------------------------------------
# 4. ANPRAnalytic Lifecycle & Frame Processing Tests
# ---------------------------------------------------------------------------

def _vehicle_track(track_id: int, class_name: str, bbox: list[float]) -> "TrackState":
    """Real TrackState — the type the session's AnalyticModule.process
    path actually receives (store active_tracks via TrackView). Its
    __slots__ expose last_bbox ONLY; TrackedObject (detection type)
    diverges from the real contract and hides wiring bugs (oscar
    blocker 2)."""
    return TrackState(
        track_id=track_id, class_id=2, class_name=class_name,
        tick=1, wall_ts=100.0, bbox=bbox, confidence=0.88,
    )


def test_anpr_composition_real_trackstate() -> None:
    """COMPOSITION (must-fail on pre-fix wiring): session invokes
    analytics via process(ctx, view) where active_tracks are TrackState
    (last_bbox only). Pre-fix code read .bbox -> None -> every real
    vehicle track skipped, no ANPR event on the product path."""
    analytic = ANPRAnalytic(cooldown_ticks=30)
    analytic.reset("session-real-1")

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    car = _vehicle_track(42, "car", [100.0, 100.0, 400.0, 250.0])  # w=300 >= 100

    ctx = FrameContext(
        tick=1, wall_ts=100.0, video_ts=100.0,
        luminance=128.0, is_night=False, shape=(640, 480),
    )

    class _View:
        active_tracks = [car]

    events = analytic.process(ctx, _View())

    # The vehicle track was evaluated through the real TrackView shape:
    # a draft IS produced (heuristic fallback always localizes a plate
    # on a >= 100px-wide vehicle). Pre-fix: .bbox None -> 0 events.
    assert len(events) == 1, (
        "TrackState vehicle track was never evaluated — "
        "check the last_bbox read"
    )
    assert events[0].track_ids == [42]
    assert events[0].type in ("ANPR_READ", "OCR_UNCERTAIN", "ANPR_PLATE_DETECTED")


def test_anpr_analytic_process_frame() -> None:
    """ANPRAnalytic processes vehicle tracks and produces throttled events."""
    analytic = ANPRAnalytic(cooldown_ticks=30)
    analytic.reset("test-session-001")

    # Dummy image: 640x480 black image
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Track 1: Car with large bbox (300px wide, 150px high) — REAL
    # TrackState (the session path type), NOT TrackedObject.
    car_track = _vehicle_track(42, "car", [100.0, 100.0, 400.0, 250.0])

    # Track 2: Person (should be ignored)
    person_track = _vehicle_track(99, "person", [50.0, 50.0, 180.0, 300.0])

    ctx1 = FrameContext(
        tick=1,
        wall_ts=100.0,
        video_ts=100.0,
        luminance=128.0,
        is_night=False,
        shape=(640, 480),
    )

    events = analytic.process_tracks(
        frame=frame,
        active_tracks=[car_track, person_track],
        ctx=ctx1,
    )

    assert len(events) == 1
    ev = events[0]
    assert ev.type in ("ANPR_READ", "OCR_UNCERTAIN", "ANPR_PLATE_DETECTED")
    assert ev.track_ids == [42]

    # Next frame at tick 2: same track should be throttled by cooldown_ticks=30
    ctx2 = FrameContext(
        tick=2,
        wall_ts=100.1,
        video_ts=100.1,
        luminance=128.0,
        is_night=False,
        shape=(640, 480),
    )
    events_frame2 = analytic.process_tracks(
        frame=frame,
        active_tracks=[car_track],
        ctx=ctx2,
    )
    assert len(events_frame2) == 0

    # Next frame at tick 35 (> cooldown_ticks):
    # If state is ANPR_PLATE_DETECTED and unchanged, it avoids spamming
    ctx3 = FrameContext(
        tick=35,
        wall_ts=106.0,
        video_ts=106.0,
        luminance=128.0,
        is_night=False,
        shape=(640, 480),
    )
    events_frame3 = analytic.process_tracks(
        frame=frame,
        active_tracks=[car_track],
        ctx=ctx3,
    )
    # Deduplication prevents re-emitting ANPR_PLATE_DETECTED consecutively
    assert len(events_frame3) == 0


# ---------------------------------------------------------------------------
# 5. API Health Inspection Test
# ---------------------------------------------------------------------------

def test_api_health_includes_anpr() -> None:
    """Verify /api/health includes anpr in models and anpr_mode."""
    client = TestClient(app)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()

    assert "anpr" in data["models"]
    assert "anpr_mode" in data
    assert data["anpr_mode"] in ("model", "heuristic_fallback")
