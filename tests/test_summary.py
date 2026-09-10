"""TRINETRA Phase 5 Tests — Trajectory DB Persistence, Migration 3 & Summary Service.

Tests:
  1. Migration 3 applies cleanly and adds nullable `trajectory` column to `tracks`.
  2. DAO._has_trajectory_column detects presence accurately.
  3. Safe degrade: unmigrated/degraded DB handles flush_tracks and upsert_track_trajectories without crashing.
  4. Full trajectory persistence roundtrip (downsampled point serialization -> DB -> API).
  5. Peak concurrency calculation (_calculate_max_concurrent) with interval overlap edge cases.
  6. Deterministic session summary computation across frames, tracks, events, zones, and notes.
  7. GET /api/sessions/{id}/summary and GET /api/sessions/{id}/tracks endpoints.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from backend.db.connection import Database
from backend.db.dao import DAO
from backend.db.migrations import MIGRATIONS
from backend.services.summary import (
    _calculate_max_concurrent,
    generate_event_summary,
    generate_session_summary,
    point_in_sector,
)


@pytest.fixture
def mem_db() -> Generator[Database, None, None]:
    """In-memory database with all migrations applied."""
    db = Database(":memory:")
    db.migrate(MIGRATIONS)
    yield db
    db.close()


@pytest.fixture
def mem_dao(mem_db: Database) -> DAO:
    return DAO(mem_db)


def test_migration_3_trajectory_column(mem_db: Database) -> None:
    """Verify Migration 3 adds the trajectory column to tracks table."""
    assert mem_db.user_version() >= 3
    cols = {r[1] for r in mem_db.conn().execute("PRAGMA table_info(tracks)").fetchall()}
    assert "trajectory" in cols


def test_has_trajectory_column_detects_legacy() -> None:
    """Verify DAO._has_trajectory_column returns False when trajectory column is missing."""
    db = Database(":memory:")
    # Apply only Migration 1 (which lacks trajectory)
    db.conn().executescript(MIGRATIONS[1])
    dao = DAO(db)
    assert not dao._has_trajectory_column()
    db.close()


def test_safe_degrade_unmigrated_db() -> None:
    """Verify flush_tracks and upsert_track_trajectories work safely on legacy DB."""
    db = Database(":memory:")
    db.conn().executescript(MIGRATIONS[1])
    dao = DAO(db)

    # Insert a source and session
    dao.upsert_source("source_cam_1", "file", "test.mp4")
    dao.insert_session("source_cam_1", "sess_legacy", "2026-09-10T10:00:00Z")

    # Flush tracks with 7 elements (including trajectory) on legacy schema
    traj_data = json.dumps([{"x": 0.1, "y": 0.2, "t": 1}])
    rows = [(1, "person", "2026-09-10T10:00:01Z", "2026-09-10T10:00:05Z", 10, 0.95, traj_data)]
    dao.flush_tracks("sess_legacy", rows)

    # Calling upsert_track_trajectories should safely no-op
    dao.upsert_track_trajectories("sess_legacy", [(1, traj_data)])

    # Query tracks
    tracks = dao.get_tracks("sess_legacy")
    assert len(tracks) == 1
    assert tracks[0]["track_id"] == 1
    assert tracks[0]["class_name"] == "person"
    db.close()


def test_trajectory_persistence_roundtrip(mem_dao: DAO) -> None:
    """Verify trajectory JSON roundtrip through flush_tracks and get_tracks."""
    mem_dao.upsert_source("source_cam_1", "file", "test.mp4")
    mem_dao.insert_session("source_cam_1", "sess_traj_1", "2026-09-10T10:00:00Z")

    waypoints = [
        {"x": 0.1, "y": 0.2, "t": 1},
        {"x": 0.15, "y": 0.25, "t": 2},
        {"x": 0.2, "y": 0.3, "t": 3},
    ]
    traj_json = json.dumps(waypoints)

    rows = [
        (1, "person", "2026-09-10T10:00:01Z", "2026-09-10T10:00:05Z", 10, 0.92, traj_json),
        (2, "car", "2026-09-10T10:00:02Z", "2026-09-10T10:00:08Z", 15, 0.88, None),
    ]
    mem_dao.flush_tracks("sess_traj_1", rows)

    tracks = mem_dao.get_tracks("sess_traj_1")
    assert len(tracks) == 2
    t1 = next(t for t in tracks if t["track_id"] == 1)
    assert t1["trajectory"] is not None
    loaded_pts = json.loads(t1["trajectory"])
    assert len(loaded_pts) == 3
    assert loaded_pts[0]["x"] == 0.1

    t2 = next(t for t in tracks if t["track_id"] == 2)
    assert t2["trajectory"] is None


def test_calculate_max_concurrent() -> None:
    """Test mathematical interval overlap calculation for max concurrent people."""
    # Test case 1: Non-overlapping tracks
    tracks_non_overlap = [
        {"class_name": "person", "first_seen": "2026-09-10T10:00:00Z", "last_seen": "2026-09-10T10:00:05Z"},
        {"class_name": "person", "first_seen": "2026-09-10T10:00:06Z", "last_seen": "2026-09-10T10:00:10Z"},
    ]
    assert _calculate_max_concurrent(tracks_non_overlap, "person") == 1

    # Test case 2: Overlapping tracks (3 concurrent peak)
    tracks_overlap = [
        {"class_name": "person", "first_seen": "2026-09-10T10:00:00Z", "last_seen": "2026-09-10T10:00:10Z"},
        {"class_name": "person", "first_seen": "2026-09-10T10:00:02Z", "last_seen": "2026-09-10T10:00:08Z"},
        {"class_name": "person", "first_seen": "2026-09-10T10:00:04Z", "last_seen": "2026-09-10T10:00:06Z"},
        {"class_name": "car", "first_seen": "2026-09-10T10:00:00Z", "last_seen": "2026-09-10T10:00:10Z"},  # Ignored
    ]
    assert _calculate_max_concurrent(tracks_overlap, "person") == 3


def test_session_summary_deterministic_values(mem_dao: DAO) -> None:
    """Verify generate_session_summary generates accurate, unhallucinated summaries."""
    session_id = "sess_summary_test"
    mem_dao.upsert_source("cam_main", "file", "test.mp4")
    mem_dao.insert_session("cam_main", session_id, "2026-09-10T12:00:00.000Z")

    # Update session with stats and completion
    stats = {
        "frames_processed": 300,
        "pipeline_fps": 30.0,
        "events_committed": 2,
    }
    mem_dao.update_session(session_id, "completed", stats=stats, ended_at="2026-09-10T12:00:10.000Z")

    # Flush tracks: 2 people, 1 car
    track_rows = [
        (1, "person", "2026-09-10T12:00:01.000Z", "2026-09-10T12:00:05.000Z", 120, 0.95, None),
        (2, "person", "2026-09-10T12:00:03.000Z", "2026-09-10T12:00:07.000Z", 120, 0.91, None),
        (3, "car", "2026-09-10T12:00:02.000Z", "2026-09-10T12:00:08.000Z", 180, 0.88, None),
    ]
    mem_dao.flush_tracks(session_id, track_rows)

    # Insert events: 1 HIGH, 1 MEDIUM
    event_rows = [
        (
            "ev_1", session_id, "cam_main", "2026-09-10T12:00:04.000Z", 4.0,
            "ZONE_INTRUSION", "HIGH", 0.92, "[1]", "restricted_zone_a", "inbound", 0, None, "{}", "new"
        ),
        (
            "ev_2", session_id, "cam_main", "2026-09-10T12:00:06.000Z", 6.0,
            "LOITERING", "MEDIUM", 0.85, "[2]", None, None, 0, None, "{}", "new"
        ),
    ]
    mem_dao.insert_events(event_rows)

    summary = generate_session_summary(mem_dao, session_id)
    assert summary is not None
    assert summary["session_id"] == session_id
    assert summary["source_id"] == "cam_main"
    assert summary["status"] == "completed"
    assert summary["duration_s"] == 10.0
    assert summary["frames"] == 300
    assert summary["unique_tracks"] == 3
    assert summary["people_detected"] == 2
    assert summary["vehicles_detected"] == 1
    assert summary["max_concurrent_people"] == 2  # Overlap between track 1 and track 2 at 12:00:03-05
    assert summary["events_by_severity"] == {"HIGH": 1, "MEDIUM": 1}
    assert summary["events_by_type"] == {"ZONE_INTRUSION": 1, "LOITERING": 1}
    assert summary["zones_breached"] == ["restricted_zone_a"]
    assert len(summary["notes"]) >= 3
    assert any("ZONE_INTRUSION (HIGH) in zone 'restricted_zone_a'" in n for n in summary["notes"])


def test_session_summary_nonexistent(mem_dao: DAO) -> None:
    """Verify generate_session_summary returns None for nonexistent session."""
    assert generate_session_summary(mem_dao, "non_existent_sess") is None


def test_api_summary_and_tracks_endpoints(tmp_path: Path) -> None:
    """Test /api/sessions/{id}/summary and /api/sessions/{id}/tracks endpoints."""
    from backend.core.errors import install, reset_for_tests
    from backend.events.sse import SseHub
    from backend.main import app

    db_path = tmp_path / "test_api.db"
    db = Database(str(db_path))
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    install(dao, SseHub())

    session_id = "api_sess_1"
    dao.upsert_source("cam_api", "webcam")
    dao.insert_session("cam_api", session_id, "2026-09-10T08:00:00.000Z")
    dao.update_session(session_id, "completed", stats={"frames_processed": 50, "pipeline_fps": 25.0}, ended_at="2026-09-10T08:00:02.000Z")

    waypoints = [{"x": 0.5, "y": 0.5, "t": 1}]
    dao.flush_tracks(session_id, [
        (1, "person", "2026-09-10T08:00:00.000Z", "2026-09-10T08:00:02.000Z", 50, 0.99, json.dumps(waypoints))
    ])

    client = TestClient(app)

    try:
        # 1. Test /api/sessions/{id}/tracks
        res_tracks = client.get(f"/api/sessions/{session_id}/tracks")
        assert res_tracks.status_code == 200
        data_tracks = res_tracks.json()
        assert data_tracks["count"] == 1
        assert data_tracks["tracks"][0]["track_id"] == 1
        assert data_tracks["tracks"][0]["trajectory"] == waypoints

        # 2. Test /api/sessions/{id}/summary
        res_sum = client.get(f"/api/sessions/{session_id}/summary")
        assert res_sum.status_code == 200
        data_sum = res_sum.json()
        assert data_sum["session_id"] == session_id
        assert data_sum["frames"] == 50
        assert data_sum["people_detected"] == 1

        # 3. Test 404 for unknown session
        res_404 = client.get("/api/sessions/unknown_xyz/summary")
        assert res_404.status_code == 404
    finally:
        reset_for_tests()
        db.close()


def test_point_in_sector_raycasting() -> None:
    """Verify point_in_sector ray-casting algorithm on standard and edge geometries."""
    # A simple triangle sector: (0,0), (10,0), (5,10)
    polygon = [[0.0, 0.0], [10.0, 0.0], [5.0, 10.0]]

    # Inside point
    assert point_in_sector(3.0, 5.0, polygon) is True

    # Outside point
    assert point_in_sector(12.0, 5.0, polygon) is False
    assert point_in_sector(-1.0, -1.0, polygon) is False

    # Degenerate polygons
    assert point_in_sector(3.0, 5.0, []) is False
    assert point_in_sector(3.0, 5.0, [[0.0, 0.0], [1.0, 1.0]]) is False


def test_event_summary_deterministic_generation(mem_dao: DAO) -> None:
    """Verify deterministic 7-clause summary generation with full rich metadata."""
    session_id = "sess_event_summary"
    source_id = "cam_border_north"

    # Setup source with GPS coordinates
    mem_dao.upsert_source(source_id, "file", "feed.mp4")
    mem_dao.conn.execute(
        "UPDATE sources SET label='North Perimeter Gate', latitude=28.6139, longitude=77.2090 WHERE id=?",
        (source_id,),
    )
    mem_dao.conn.commit()

    # Setup geo sector containing the coordinates
    mem_dao.conn.execute(
        "INSERT INTO geo_sectors (id, name, kind, description, polygon, active) VALUES (?, ?, ?, ?, ?, ?)",
        (
            "sec_north", "Northern Outpost Sector", "SECTOR", "High security border",
            json.dumps([[28.0, 77.0], [29.0, 77.0], [29.0, 78.0], [28.0, 78.0]]), 1
        ),
    )
    mem_dao.conn.commit()

    # Setup video zone
    mem_dao.insert_zone(
        zone_id="zone_restricted_1",
        source_id=source_id,
        name="Restricted Gate Zone",
        kind="polygon",
        zone_type="RESTRICTED",
        geometry_json=json.dumps({"points": [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5]]}),
    )

    mem_dao.insert_session(source_id, session_id, "2026-09-10T14:00:00.000Z")

    # Insert track binding
    mem_dao.flush_tracks(session_id, [
        (101, "person", "2026-09-10T14:00:01.000Z", "2026-09-10T14:00:10.000Z", 150, 0.96, None)
    ])

    # Insert event
    event_id = "ev_audit_1"
    metadata = {
        "global_person_id": "PER-9942",
        "identity_cameras": ["cam_border_north", "cam_outpost_2"],
        "velocity": 45.2,
        "acceleration": -3.1,
        "straightness": 0.88,
        "dwell_time": 12.5,
        "person_count": 1,
        "severity_reason": "Escalated: restricted zone breach during night monitoring window",
    }
    mem_dao.insert_events([
        (
            event_id,
            session_id,
            source_id,
            "2026-09-10T14:00:05.120Z",
            5.12,
            "ZONE_INTRUSION",
            "HIGH",
            0.94,
            json.dumps([101]),
            "zone_restricted_1",
            "inbound",
            1,  # is_night
            "/evidence/snapshots/ev_audit_1.jpg",
            json.dumps(metadata),
            "new",
        )
    ])

    summary = generate_event_summary(mem_dao, event_id)
    assert summary is not None
    assert summary["event_id"] == event_id
    assert summary["session_id"] == session_id
    assert summary["source_id"] == source_id

    # 1. WHAT
    assert "ZONE_INTRUSION (HIGH severity, 94.0% confidence)" in summary["what"]
    assert summary["structured"]["what"]["label"] == "Zone Intrusion"

    # 2. WHO
    assert "Track #101 (person)" in summary["who"]
    assert "Re-ID Identity: PER-9942 (seen on cam_border_north, cam_outpost_2)" in summary["who"]

    # 3. WHERE
    assert "North Perimeter Gate" in summary["where"]
    assert "Coords: 28.6139, 77.2090" in summary["where"]
    assert "Zone: Restricted Gate Zone (polygon, RESTRICTED)" in summary["where"]
    assert "Geo Sector: Northern Outpost Sector" in summary["where"]

    # 4. WHEN
    assert "Time: 2026-09-10T14:00:05.120Z" in summary["when"]
    assert "Video offset: +5.12s" in summary["when"]
    assert "Night mode: Active" in summary["when"]

    # 5. MOVEMENT
    assert "Direction: inbound" in summary["movement"]
    assert "velocity: 45.2px/s" in summary["movement"]
    assert "accel: -3.1px/s²" in summary["movement"]
    assert "straightness: 0.88" in summary["movement"]
    assert "dwell: 12.5s" in summary["movement"]
    assert "count: 1" in summary["movement"]

    # 6. WHY
    assert summary["why"] == "Escalated: restricted zone breach during night monitoring window"

    # 7. EVIDENCE
    assert summary["evidence"] == "Snapshot available (/evidence/snapshots/ev_audit_1.jpg)"
    assert summary["structured"]["evidence"]["snapshot_available"] is True

    # Narrative assertion
    assert "At 2026-09-10T14:00:05.120Z, ZONE_INTRUSION" in summary["narrative"]

    # Determinism: Calling twice yields exact same dict
    summary_2 = generate_event_summary(mem_dao, event_id)
    assert summary == summary_2


def test_event_summary_sparse_and_degraded_fields(mem_dao: DAO) -> None:
    """Verify generate_event_summary explicitly marks all missing/unplaced fields as 'Not available'."""
    session_id = "sess_sparse"
    source_id = "cam_unplaced"

    mem_dao.upsert_source(source_id, "file", "sparse.mp4")
    mem_dao.insert_session(source_id, session_id, "2026-09-10T15:00:00.000Z")

    event_id = "ev_sparse_1"
    # Event with no track bindings, unplaced camera, deleted zone, no kinematics, skipped snapshot
    mem_dao.insert_events([
        (
            event_id,
            session_id,
            source_id,
            "2026-09-10T15:00:02.000Z",
            None,  # No video_ts
            "MOTION",
            "LOW",
            0.70,
            "[]",  # No tracks
            "deleted_zone_uuid",  # Deleted zone
            None,  # No direction
            0,  # Day
            None,  # No snapshot
            json.dumps({"snapshot_skipped_low_disk": True}),
            "new",
        )
    ])

    summary = generate_event_summary(mem_dao, event_id)
    assert summary is not None

    assert summary["who"] == "Not available (no track binding)"
    assert "Coords: Not available" in summary["where"]
    assert "Zone: deleted_zone_uuid (deleted zone)" in summary["where"]
    assert "Geo Sector: Not available (camera unplaced)" in summary["where"]
    assert "Video offset: Not available" in summary["when"]
    assert "Night mode: Inactive" in summary["when"]
    assert "Direction: Not available" in summary["movement"]
    assert "Kinematics: Not available" in summary["movement"]
    assert "Snapshot skipped — low disk threshold" in summary["evidence"]
    assert summary["structured"]["evidence"]["skip_reason"] == "low_disk"


def test_api_event_summary_endpoint(tmp_path: Path) -> None:
    """Test GET /api/events/{event_id}/summary endpoint."""
    from backend.core.errors import install, reset_for_tests
    from backend.events.sse import SseHub
    from backend.main import app

    db_path = tmp_path / "test_event_summary_api.db"
    db = Database(str(db_path))
    db.migrate(MIGRATIONS)
    dao = DAO(db)
    install(dao, SseHub())

    session_id = "api_sess_ev_sum"
    dao.upsert_source("cam_test", "webcam")
    dao.insert_session("cam_test", session_id, "2026-09-10T08:00:00.000Z")

    ev_id = "ev_api_123"
    dao.insert_events([
        (
            ev_id, session_id, "cam_test", "2026-09-10T08:00:05.000Z", 5.0,
            "LINE_CROSS", "MEDIUM", 0.88, "[]", None, "forward", 0, None, "{}", "new"
        )
    ])

    client = TestClient(app)

    try:
        res = client.get(f"/api/events/{ev_id}/summary")
        assert res.status_code == 200
        data = res.json()
        assert data["event_id"] == ev_id
        assert data["what"].startswith("LINE_CROSS")
        assert "narrative" in data
        assert "structured" in data

        res_404 = client.get("/api/events/nonexistent_ev/summary")
        assert res_404.status_code == 404
    finally:
        reset_for_tests()
        db.close()

