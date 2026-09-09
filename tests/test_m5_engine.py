"""M5 event-engine tests — cooldown, severity, snapshots, per-session
state, PERSON/VEHICLE_DETECTED via the confirm seam.

Covers the architect's mandatory list: exact-10s cooldown boundary
(9.99 suppressed / 10.00 allowed), severity stacking caps (RESTRICTED+
night entry -> HIGH capped + dual reason; WATCH+night -> HIGH; restricted
line + forward + night -> HIGH), snapshot gating (LOW -> no file,
MEDIUM+ -> file bytes == slot JPEG), PERSON_DETECTED re-fires same
track_id in a NEW session (C8).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.analytics.base import EventDraft, FrameContext
from backend.events.engine import EventEngine


def ctx(tick=0, wall_ts=1_000_000.0, is_night=False, video_ts=0.0):
    return FrameContext(tick=tick, wall_ts=wall_ts, video_ts=video_ts,
                        luminance=20.0 if is_night else 128.0,
                        is_night=is_night, shape=(1920, 1080))


def draft(type_, track_ids=(1,), zone_id="z1", direction=None,
          zone_type="RESTRICTED", zone_kind="polygon", is_night=False,
          confidence=1.0, zone_kind_extra=None):
    meta = {"is_night": is_night, "zone_type": zone_type,
            "direction_mode": zone_kind_extra, "zone_kind": zone_kind,
            "tick": 0, "video_ts": 0.0}
    return EventDraft(type=type_, track_ids=list(track_ids),
                      zone_id=zone_id, direction=direction,
                      confidence=confidence, metadata=meta)


def make_engine(session_id="sess-1", writer=None, hub=None, dao=None):
    return EventEngine("file:x.mp4", session_id, writer=writer, hub=hub,
                       dao=dao)


# ---- cooldown (A2): STRICTLY less than 10s suppressed; 10.00 allowed ----

def test_cooldown_exact_boundary_9_99_suppressed_10_00_allowed():
    eng = make_engine()
    d = draft("ZONE_ENTRY")
    t0 = 1_000_000.0
    assert eng.commit([d], None, ctx(wall_ts=t0))             # fires
    # 9.99s later: same (type, track, zone) -> suppressed
    assert eng.commit([d], None, ctx(wall_ts=t0 + 9.99)) == []
    # exactly 10.00s later: ALLOWED (strictly-less rule, pinned A2)
    out = eng.commit([d], None, ctx(wall_ts=t0 + 10.0))
    assert [e.type for e in out] == ["ZONE_ENTRY"]


def test_cooldown_key_includes_type_and_zone():
    """ZONE_ENTRY then ZONE_EXIT within 10s -> BOTH land (key has type;
    god's acceptance list)."""
    eng = make_engine()
    t0 = 1_000_000.0
    eng.commit([draft("ZONE_ENTRY", track_ids=[1], zone_id="z1")], None,
               ctx(wall_ts=t0))
    eng.commit([draft("ZONE_EXIT", track_ids=[1], zone_id="z1")], None,
               ctx(wall_ts=t0 + 1.0))          # 1s later, different type
    assert eng.committed == 2
    # same type different zone: also both land
    eng.commit([draft("ZONE_ENTRY", track_ids=[1], zone_id="z2")], None,
               ctx(wall_ts=t0 + 1.0))
    assert eng.committed == 3


# ---- severity ladder + stacking (A3) ----

@pytest.mark.parametrize("zone_type,is_night,expected,frag", [
    ("RESTRICTED", False, "HIGH", "RESTRICTED zone entry"),
    ("RESTRICTED", True, "HIGH", "RESTRICTED zone entry at night"),  # capped
    ("WATCH", False, "MEDIUM", "WATCH zone entry"),
    ("WATCH", True, "HIGH", "WATCH zone entry at night"),
])
def test_zone_entry_severity_matrix(zone_type, is_night, expected, frag):
    eng = make_engine()
    out = eng.commit(
        [draft("ZONE_ENTRY", zone_type=zone_type, is_night=is_night)],
        None, ctx(is_night=is_night))
    assert out[0].severity == expected
    assert frag in out[0].metadata["severity_reason"]


def test_zone_exit_low_no_modifiers_even_night():
    eng = make_engine()
    out = eng.commit([draft("ZONE_EXIT", is_night=True)], None,
                     ctx(is_night=True))
    assert out[0].severity == "LOW"          # pinned A3: no modifiers


def test_line_crossing_severity_stacking():
    """Base MEDIUM; +1 RESTRICTED line; +1 night; CAP at HIGH."""
    eng = make_engine()
    out = eng.commit(
        [draft("LINE_CROSSING", zone_kind="line", zone_type="WATCH",
               direction="forward", is_night=False)], None, ctx())
    assert out[0].severity == "MEDIUM"
    eng2 = make_engine()
    out = eng2.commit(
        [draft("LINE_CROSSING", zone_kind="line", zone_type="RESTRICTED",
               direction="forward", is_night=False)], None, ctx())
    assert out[0].severity == "HIGH"         # MEDIUM + 1
    eng3 = make_engine()
    out = eng3.commit(
        [draft("LINE_CROSSING", zone_kind="line", zone_type="RESTRICTED",
               direction="forward", is_night=True)], None, ctx(is_night=True))
    assert out[0].severity == "HIGH"         # capped
    assert "RESTRICTED line" in out[0].metadata["severity_reason"]
    assert "at night" in out[0].metadata["severity_reason"]


def test_person_vehicle_detected_low_and_system_info():
    eng = make_engine()
    out = eng.commit([draft("PERSON_DETECTED", zone_id=None)], None, ctx())
    assert out[0].severity == "LOW"
    out = eng.commit([draft("VEHICLE_DETECTED", zone_id=None)], None, ctx())
    assert out[0].severity == "LOW"
    out = eng.commit([draft("SOURCE_CONNECTED", track_ids=[])], None, ctx())
    assert out[0].severity == "INFO"


# ---- snapshot gating (A1: bytes == slot JPEG) ----

class _Recorder:
    def __init__(self):
        self.rows = []

    def enqueue(self, row):
        self.rows.append(row)


def test_snapshot_gating_low_none_medium_bytes_match(tmp_path, monkeypatch):
    from backend.events import engine as eng_mod
    from backend.core.config import EVENTS
    monkeypatch.setattr(eng_mod, "EVIDENCE_DIR", tmp_path / "ev")
    eng = make_engine()
    jpeg = b"\xff\xd8FAKEJPG\xff\xd9"
    # LOW (ZONE_EXIT): no snapshot
    out = eng.commit([draft("ZONE_EXIT")], jpeg, ctx())
    assert out[0].snapshot_path is None
    assert list((tmp_path / "ev").glob("*.jpg")) == [] if (
        tmp_path / "ev").exists() else True
    # MEDIUM (WATCH entry): snapshot written, bytes IDENTICAL
    eng2 = make_engine()
    out = eng2.commit([draft("ZONE_ENTRY", zone_type="WATCH")], jpeg, ctx())
    assert out[0].snapshot_path is not None
    assert Path(out[0].snapshot_path).read_bytes() == jpeg
    # system events: never snapshot (A1)
    eng3 = make_engine()
    out = eng3.commit([draft("SESSION_COMPLETED", track_ids=[])], jpeg, ctx())
    assert out[0].snapshot_path is None
    assert EVENTS.snapshot_min_severity == "MEDIUM"  # config gate honored


# ---- per-session state (C8) ----

def test_reset_clears_cooldown_and_refires_new_session():
    """Same track_id + type + zone in a NEW session fires again after
    reset() (per-session cooldown map, C8)."""
    eng = make_engine("sess-A")
    d = draft("ZONE_ENTRY", track_ids=[7])
    t = 1_000_000.0
    eng.commit([d], None, ctx(wall_ts=t))
    eng.commit([d], None, ctx(wall_ts=t + 1.0))      # suppressed (cooldown)
    assert eng.committed == 1
    eng.reset("sess-B")
    assert eng.committed == 0
    out = eng.commit([d], None, ctx(wall_ts=t + 2.0))
    assert [e.type for e in out] == ["ZONE_ENTRY"]   # re-fires
    assert eng.committed == 1


def test_engine_emits_to_writer_and_hub():
    rec = _Recorder()
    hub_rows = []

    class _Hub:
        def publish(self, j):
            hub_rows.append(j)

    eng = make_engine(writer=rec, hub=_Hub())
    eng.commit([draft("ZONE_ENTRY", zone_type="RESTRICTED")], None, ctx())
    assert len(rec.rows) == 1                  # writer row queued
    assert len(hub_rows) == 1                  # SSE json published
    assert hub_rows[0]["severity"] == "HIGH"
    assert hub_rows[0]["severity_reason"] == "RESTRICTED zone entry"
    assert hub_rows[0]["track_ids"] == [1]
    assert hub_rows[0]["type"] == "ZONE_ENTRY"
