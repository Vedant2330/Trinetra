"""M4 FenceAnalytic tests — synthetic inputs over the real TrackStore +
TrackView + FenceAnalytic (architect's mandatory edge list).

Zone fixtures are normalized (§12); foot points are frame pixels scaled
by the synthetic frame size, so tests prove resolution independence
(640x360 vs 1920x1080 same zone => identical drafts).
"""

from __future__ import annotations

from backend.analytics import FenceAnalytic, FrameContext, ZoneStore
from backend.state import TrackStore
from backend.vision import TrackedObject

W, H = 1920, 1080          # synthetic frame size for normalization
SMALL_W, SMALL_H = 640, 360


def make_store():
    return TrackStore()


def mk_track(tid, foot_x, foot_y, bbox_h=100):
    """TrackedObject whose FOOT point (cx, y2) = (foot_x, foot_y)."""
    cx, y2 = foot_x, foot_y
    y1 = max(0.0, y2 - bbox_h)
    return TrackedObject(track_id=tid, class_id=0, class_name="person",
                         confidence=0.9, bbox=[cx - 20, y1, cx + 20, y2])


def ctx(tick, shape=(W, H), is_night=False, luminance=128.0):
    return FrameContext(tick=tick, wall_ts=float(tick), video_ts=float(tick),
                        luminance=luminance, is_night=is_night,
                        shape=shape)


def make_zone_polygon(store, points=None, ztype="RESTRICTED", name="z-poly"):
    pts = points or [[0.1, 0.3], [0.88, 0.3], [0.88, 0.95], [0.12, 0.95]]
    return store.add("s", name, "polygon", ztype, {"points": pts})


def make_zone_line(store, p1=None, p2=None, mode="both", ztype="WATCH",
                   name="z-line"):
    p1 = p1 or [0.1, 0.5]
    p2 = p2 or [0.9, 0.5]
    return store.add("s", name, "line", ztype,
                     {"p1": p1, "p2": p2, "direction_mode": mode})


def run(fence, store, tick, tracks, shape=(W, H), is_night=False):
    store.update(tracks, tick=tick, wall_ts=float(tick))
    return fence.process(ctx(tick, shape=shape, is_night=is_night),
                          store.view())


def foot(point, shape=(W, H)):
    """normalized point -> frame pixel foot coordinates."""
    return (point[0] * shape[0], point[1] * shape[1])


def in_zone_norm():
    return (0.5, 0.6)       # inside the default polygon
def out_zone_norm():
    return (0.5, 0.05)      # clearly outside (above the top edge 0.3)


# ---- zone confirm/exit state machine ----

def test_three_frame_confirm_exactly_one_entry():
    zs, store, fence = ZoneStore(), make_store(), None
    zone = make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    p = foot(in_zone_norm())
    drafts = []
    for t in range(6):
        d = run(fence, store, t, [mk_track(1, *p)])
        drafts += d
    entries = [d for d in drafts if d.type == "ZONE_ENTRY"]
    assert len(entries) == 1
    assert entries[0].zone_id == zone.id
    assert entries[0].confidence == 1.0
    assert entries[0].metadata["zone_type"] == "RESTRICTED"


def test_confirm_interrupted_resets_counter():
    zs, store = ZoneStore(), make_store()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin, pout = foot(in_zone_norm()), foot(out_zone_norm())
    drafts = []
    for t in range(10):                       # in, in, out, in, in, in...
        p = pout if t == 2 else pin
        drafts += run(fence, store, t, [mk_track(1, *p)])
    # counter reset at t=2; confirm completes at t=5 (t=3,4,5 consecutive)
    entries = [d for d in drafts if d.type == "ZONE_ENTRY"]
    assert len(entries) == 1


def test_flapping_below_confirm_no_events():
    zs, store = ZoneStore(), make_store()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin, pout = foot(in_zone_norm()), foot(out_zone_norm())
    drafts = []
    for t in range(12):                       # alternating in/out
        p = pin if t % 2 == 0 else pout
        drafts += run(fence, store, t, [mk_track(1, *p)])
    assert drafts == []                       # never 3 consecutive inside


def test_one_in_out_cycle_exactly_two_drafts():
    zs, store = ZoneStore(), make_store()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin, pout = foot(in_zone_norm()), foot(out_zone_norm())
    drafts = []
    for t in range(4):                        # confirm: 0,1,2 inside
        drafts += run(fence, store, t, [mk_track(1, *pin)])
    for t in range(10):                       # grace: 3..12 outside (10)
        drafts += run(fence, store, t, [mk_track(1, *pout)])
    assert [d.type for d in drafts] == ["ZONE_ENTRY", "ZONE_EXIT"]
    assert drafts[0].zone_id == drafts[1].zone_id


def test_exit_grace_boundary_exact():
    """exit_grace_frames=10: 9 outside ticks = NO exit, 10th = exit."""
    zs, store = ZoneStore(), make_store()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin, pout = foot(in_zone_norm()), foot(out_zone_norm())
    for t in range(3):
        run(fence, store, t, [mk_track(1, *pin)])       # entry confirmed
    no_draft = []
    for t in range(3, 12):                              # 9 outside ticks
        no_draft += run(fence, store, t, [mk_track(1, *pout)])
    assert all(d.type != "ZONE_EXIT" for d in no_draft)
    final = run(fence, store, 12, [mk_track(1, *pout)])  # 10th outside
    assert [d.type for d in final] == ["ZONE_EXIT"]


def test_reappear_in_grace_no_second_entry():
    zs, store = ZoneStore(), make_store()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin, pout = foot(in_zone_norm()), foot(out_zone_norm())
    drafts = []
    for t in range(3):                        # confirmed inside
        drafts += run(fence, store, t, [mk_track(1, *pin)])
    drafts += run(fence, store, 3, [mk_track(1, *pout)])   # 1 outside
    for t in range(4, 7):                                  # back inside
        drafts += run(fence, store, t, [mk_track(1, *pin)])
    # inside again: grace resets, NO second entry, NO exit ever
    types = [d.type for d in drafts]
    assert types == ["ZONE_ENTRY"]


# ---- absent tracks (god correction 5) ----

def test_disappear_mid_confirm_no_entry():
    zs, store = ZoneStore(), make_store()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin = foot(in_zone_norm())
    drafts = []
    for t in range(2):                        # 2 inside ticks (need 3)
        drafts += run(fence, store, t, [mk_track(1, *pin)])
    for t in range(2, 20):                    # track vanishes entirely
        drafts += run(fence, store, t, [])
    assert drafts == []                       # no entry without confirm


def test_disappear_after_entry_exactly_one_exit():
    zs, store = ZoneStore(), make_store()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin = foot(in_zone_norm())
    drafts = []
    for t in range(3):                        # confirmed entry
        drafts += run(fence, store, t, [mk_track(1, *pin)])
    for t in range(3, 40):                    # gone: grace advances
        drafts += run(fence, store, t, [])
    types = [d.type for d in drafts]
    assert types == ["ZONE_ENTRY", "ZONE_EXIT"]


def test_no_exit_without_prior_entry():
    """A track that never confirmed entry and then vanishes: zero drafts."""
    zs, store = ZoneStore(), make_store()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin = foot(in_zone_norm())
    drafts = []
    drafts += run(fence, store, 0, [mk_track(1, *pin)])   # 1 inside tick
    for t in range(1, 40):
        drafts += run(fence, store, t, [])
    assert drafts == []


def test_reappear_inside_grace_resumes_counters():
    """Disappear mid-grace (after entry), reappear INSIDE the grace window
    (< exit_grace_frames outside ticks): no second entry, occupancy
    resumes as if never left."""
    zs, store = ZoneStore(), make_store()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin, pout = foot(in_zone_norm()), foot(out_zone_norm())
    drafts = []
    for t in range(3):                        # entry
        drafts += run(fence, store, t, [mk_track(1, *pin)])
    drafts += run(fence, store, 3, [mk_track(1, *pout)])   # outside 1 tick
    for t in range(4, 11):                                 # gone (grace < 10)
        drafts += run(fence, store, t, [])
    for t in range(11, 14):                                # back inside
        drafts += run(fence, store, t, [mk_track(1, *pin)])
    assert [d.type for d in drafts] == ["ZONE_ENTRY"]


def test_new_track_id_fresh_state():
    zs, store = ZoneStore(), make_store()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin = foot(in_zone_norm())
    drafts = []
    # track 1 confirms entry, then track 2 (NEW id) appears inside:
    # track 2 must run its OWN confirm cycle -> second entry is legitimate
    for t in range(3):
        drafts += run(fence, store, t, [mk_track(1, *pin)])
    for t in range(3, 6):
        drafts += run(fence, store, t, [mk_track(2, *pin)])
    types = [d.type for d in drafts]
    assert types == ["ZONE_ENTRY", "ZONE_ENTRY"]    # per-(track,zone) isolation
    assert drafts[0].track_ids == [1] and drafts[1].track_ids == [2]


def test_two_tracks_interleaved_isolated():
    zs, store = ZoneStore(), make_store()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin, pout = foot(in_zone_norm()), foot(out_zone_norm())
    drafts = []
    for t in range(6):
        # track 1 inside the whole time; track 2 in for 3, out for 10+
        t1 = [mk_track(1, *pin)]
        t2 = [mk_track(2, *(pin if t < 3 else pout))]
        drafts += run(fence, store, t, t1 + t2)
    for t in range(6, 20):
        drafts += run(fence, store, t, [mk_track(1, *pin),
                                         mk_track(2, *pout)])
    e1 = [d for d in drafts if d.type == "ZONE_ENTRY" and d.track_ids == [1]]
    e2 = [d for d in drafts if d.type == "ZONE_ENTRY" and d.track_ids == [2]]
    x2 = [d for d in drafts if d.type == "ZONE_EXIT" and d.track_ids == [2]]
    x1 = [d for d in drafts if d.type == "ZONE_EXIT" and d.track_ids == [1]]
    assert len(e1) == 1 and len(e2) == 1 and len(x2) == 1 and len(x1) == 0


# ---- tripwires (architect correction 3) ----

def _line_cross_setup(mode="both", p1=None, p2=None):
    zs, store = ZoneStore(), make_store()
    make_zone_line(zs, p1=p1, p2=p2, mode=mode)
    fence = FenceAnalytic(zs); fence.reset("s")
    return zs, store, fence


def test_line_touch_or_collinear_no_event():
    """Zero/touch/collinear transitions never fire: a foot point exactly ON
    the line (sign 0) sets no state; the documented case is a single-tick
    touch — arrival on the line then retreat to the SAME side, and a
    slide fully ALONG the line. A touch BETWEEN opposite sides is a real
    crossing (that's the fast-mover guarantee) and fires."""
    zs, store, fence = _line_cross_setup()
    drafts = []
    on_line = foot((0.5, 0.5))
    left = foot((0.5, 0.3))      # above horizontal line
    # arrive ON the line, retreat to the same (left) side: no event
    drafts += run(fence, store, 0, [mk_track(1, *on_line)])
    drafts += run(fence, store, 1, [mk_track(1, *left)])
    # slide along the line (still sign 0): no event, no state change
    drafts += run(fence, store, 2, [mk_track(1, *on_line)])
    assert drafts == []
    # touch then return to the same side: no event
    drafts += run(fence, store, 3, [mk_track(1, *foot((0.3, 0.5)))])
    assert [d.type for d in drafts if d.type] == []


def test_line_collinear_slide_no_event():
    """Both foot points collinear WITH the line's span but off its ends,
    then sliding along: no crossing event."""
    zs, store, fence = _line_cross_setup(p1=[0.1, 0.5], p2=[0.9, 0.5])
    drafts = []
    a = foot((0.0, 0.5))
    b = foot((0.95, 0.5))
    drafts += run(fence, store, 0, [mk_track(1, *a)])
    drafts += run(fence, store, 1, [mk_track(1, *b)])
    assert drafts == []


def test_vertical_line_crossing_directions():
    """Vertical tripwire + horizontal motion: proves the geometry is NOT a
    Y-threshold (a vertical line has constant y — naive prev_y<y<=y fails)."""
    zs, store, fence = _line_cross_setup(p1=[0.5, 0.1], p2=[0.5, 0.9])
    drafts = []
    left = foot((0.3, 0.5))
    right = foot((0.7, 0.5))
    drafts += run(fence, store, 0, [mk_track(1, *left)])
    drafts += run(fence, store, 1, [mk_track(1, *right)])   # L->R = reverse
    drafts += run(fence, store, 2, [mk_track(1, *left)])    # R->L = forward
    crossings = [d for d in drafts if d.type == "LINE_CROSSING"]
    assert [c.direction for c in crossings] == ["reverse", "forward"]


def test_direction_mode_forward_suppresses_reverse():
    """mode=forward: reverse crossing suppressed; only forward crossings
    emit drafts. Horizontal arrow points +x: above(-1)->below(+1) is
    FORWARD; below->above is reverse."""
    zs, store, fence = _line_cross_setup(mode="forward")
    above = foot((0.5, 0.3))
    below = foot((0.5, 0.7))
    drafts = []
    drafts += run(fence, store, 0, [mk_track(1, *below)])
    drafts += run(fence, store, 1, [mk_track(1, *above)])   # reverse: dropped
    assert drafts == []
    # fresh track crossing forward: kept (proves the filter, not state)
    drafts += run(fence, store, 2, [mk_track(2, *above)])
    drafts += run(fence, store, 3, [mk_track(2, *below)])   # forward: kept
    assert [d.direction for d in drafts] == ["forward"]


def test_direction_mode_reverse_matrix():
    zs, store, fence = _line_cross_setup(mode="reverse")
    above, below = foot((0.5, 0.3)), foot((0.5, 0.7))
    drafts = []
    drafts += run(fence, store, 0, [mk_track(1, *above)])
    drafts += run(fence, store, 1, [mk_track(1, *below)])   # forward: dropped
    assert drafts == []
    drafts += run(fence, store, 2, [mk_track(2, *below)])
    drafts += run(fence, store, 3, [mk_track(2, *above)])   # reverse: kept
    assert [d.direction for d in drafts] == ["reverse"]


def test_fast_mover_between_ticks_line_detected_zone_skipped():
    """Fast mover: trajectory segment catches the line crossing; a SMALL
    polygon fully skipped between ticks produces NO zone events (frozen
    documented limitation — trajectory-segment zone tests are P3)."""
    zs, store, fence = _line_cross_setup(p1=[0.5, 0.1], p2=[0.5, 0.9])
    # also add a small polygon zone the mover jumps clean over
    make_zone_polygon(zs, points=[[0.45, 0.2], [0.55, 0.2],
                                 [0.55, 0.3], [0.45, 0.3]], name="tiny")
    drafts = []
    left_far = foot((0.2, 0.5))
    right_far = foot((0.8, 0.5))    # jump: crosses line at x=0.5, skips tiny zone
    drafts += run(fence, store, 0, [mk_track(1, *left_far)])
    drafts += run(fence, store, 1, [mk_track(1, *right_far)])
    types = [(d.type, d.zone_id) for d in drafts]
    assert types == [("LINE_CROSSING", "z1")]   # only the line fired
    assert all(d.type != "ZONE_ENTRY" for d in drafts)


def test_line_no_state_update_on_zero_sign():
    """A zero sign (on-line) must not poison the previous-sign memory:
    after touching the line, a genuine crossing still fires exactly once."""
    zs, store, fence = _line_cross_setup()
    drafts = []
    left, right, on = foot((0.5, 0.3)), foot((0.5, 0.7)), foot((0.5, 0.5))
    drafts += run(fence, store, 0, [mk_track(1, *left)])
    drafts += run(fence, store, 1, [mk_track(1, *on)])      # touch: nothing
    drafts += run(fence, store, 2, [mk_track(1, *right)])  # cross: fires once
    assert [d.type for d in drafts] == ["LINE_CROSSING"]


# ---- structural dedup ----

def test_no_drafts_while_state_unchanged():
    zs, store = ZoneStore(), make_store()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin = foot(in_zone_norm())
    drafts = []
    for t in range(50):                       # 50 consecutive inside ticks
        drafts += run(fence, store, t, [mk_track(1, *pin)])
    assert [d.type for d in drafts] == ["ZONE_ENTRY"]    # exactly one


# ---- resolution independence (§12 normalized space) ----

def _in_out_sequence(fence, store, shape):
    pin = foot(in_zone_norm(), shape)
    pout = foot(out_zone_norm(), shape)
    seq = []
    for t in range(3):
        seq += run(fence, store, t, [mk_track(1, *pin)], shape=shape)
    for t in range(3, 13):
        seq += run(fence, store, t, [mk_track(1, *pout)], shape=shape)
    return [(d.type, d.track_ids, d.zone_id, d.direction,
             d.metadata["is_night"]) for d in seq]


def test_same_zone_640x360_and_1920x1080_identical():
    """Identical normalized zone, two frame sizes: identical draft sequence."""
    results = []
    for shape in [(SMALL_W, SMALL_H), (W, H)]:
        zs, store = ZoneStore(), make_store()
        make_zone_polygon(zs)
        fence = FenceAnalytic(zs); fence.reset("s")
        results.append(_in_out_sequence(fence, store, shape))
    assert results[0] == results[1]


# ---- per-session isolation via reset() ----

def test_reset_second_session_clean_identical_sequence():
    """Same FenceAnalytic object, same input script, two sessions (reset
    between): identical draft sequences — state is fully cleared."""
    def play(fence, store):
        zs_zones = fence._zones                     # same zone store
        pin, pout = foot(in_zone_norm()), foot(out_zone_norm())
        drafts = []
        for t in range(3):
            drafts += run(fence, store, t, [mk_track(1, *pin)])
        for t in range(3, 13):
            drafts += run(fence, store, t, [mk_track(1, *pout)])
        return [(d.type, d.track_ids, d.zone_id) for d in drafts]

    zs = ZoneStore()
    make_zone_polygon(zs)
    fence = FenceAnalytic(zs)
    fence.reset("session-A")
    seq_a = play(fence, make_store())
    fence.reset("session-B")                        # fresh session, same process
    seq_b = play(fence, make_store())
    assert seq_a == seq_b == [("ZONE_ENTRY", [1], "z1"),
                              ("ZONE_EXIT", [1], "z1")]


# ---- metadata seam (architect correction 4) ----

def test_metadata_carries_night_zone_type_direction_mode():
    zs, store = ZoneStore(), make_store()
    zone_p = make_zone_polygon(zs, ztype="WATCH")
    zone_l = make_zone_line(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin, pout = foot(in_zone_norm()), foot(out_zone_norm())
    left, right = foot((0.5, 0.3)), foot((0.5, 0.7))
    drafts = []
    for t in range(3):
        drafts += run(fence, store, t, [mk_track(1, *pin)], is_night=True)
    for t in range(3, 13):
        drafts += run(fence, store, t, [mk_track(1, *pout)], is_night=True)
    entry = next(d for d in drafts if d.type == "ZONE_ENTRY")
    assert entry.metadata["is_night"] is True
    assert entry.metadata["zone_type"] == "WATCH"
    assert entry.metadata["zone_kind"] == "polygon"
    assert entry.metadata["direction_mode"] is None
    # line crossing metadata
    zl_before = len(drafts)
    store2 = TrackStore()
    fence.reset("s2")
    line_drafts = []
    line_drafts += run(fence, store2, 0, [mk_track(9, *left)], is_night=True)
    line_drafts += run(fence, store2, 1, [mk_track(9, *right)], is_night=True)
    cross = next(d for d in line_drafts if d.type == "LINE_CROSSING")
    assert cross.metadata["direction_mode"] == "both"
    assert cross.metadata["zone_kind"] == "line"
    assert cross.metadata["is_night"] is True


# ---- byproduct: per-zone counts ----

def test_zone_person_counts_byproduct():
    zs, store = ZoneStore(), make_store()
    zone = make_zone_polygon(zs)
    fence = FenceAnalytic(zs); fence.reset("s")
    pin, pout = foot(in_zone_norm()), foot(out_zone_norm())
    for t in range(3):                        # both inside, confirmed
        run(fence, store, t, [mk_track(1, *pin), mk_track(2, *pin)])
    assert fence.zone_person_counts() == {zone.id: 2}
    for t in range(3, 13):                     # both leave
        run(fence, store, t, [mk_track(1, *pout), mk_track(2, *pout)])
    assert fence.zone_person_counts() == {}
