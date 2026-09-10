"""TRINETRA schema migrations (M5, §14).

Numbered SQL scripts, applied strictly in order; `user_version` records
the applied version. Migration 001 = the full frozen Phase-1 schema
(6 tables + indexes, ARCHITECTURE §14 verbatim).

Incident tables are Phase 2 BY DESIGN — reserved via migration then,
no empty tables now (§13).
"""

from __future__ import annotations

MIGRATIONS: dict[int, str] = {
    1: """
    CREATE TABLE sources(
      id TEXT PRIMARY KEY,
      name TEXT,
      type TEXT CHECK(type IN('webcam','file','rtsp')),
      uri TEXT,
      created_at TEXT,
      status TEXT DEFAULT 'idle'
    );
    CREATE TABLE zones(
      id TEXT PRIMARY KEY,
      source_id TEXT REFERENCES sources(id) ON DELETE CASCADE,
      name TEXT,
      kind TEXT CHECK(kind IN('polygon','line')),
      zone_type TEXT DEFAULT 'RESTRICTED',
      geometry TEXT,
      active INT DEFAULT 1,
      created_at TEXT,
      updated_at TEXT
    );
    CREATE TABLE sessions(
      id TEXT PRIMARY KEY,
      source_id TEXT REFERENCES sources(id),
      started_at TEXT,
      ended_at TEXT,
      status TEXT DEFAULT 'running',
      stats TEXT
    );
    CREATE TABLE tracks(
      session_id TEXT REFERENCES sessions(id),
      track_id INT,
      class_name TEXT,
      first_seen TEXT,
      last_seen TEXT,
      frames INT,
      max_conf REAL,
      PRIMARY KEY(session_id, track_id)
    );
    CREATE TABLE events(
      id TEXT PRIMARY KEY,
      session_id TEXT REFERENCES sessions(id),
      source_id TEXT,
      ts TEXT,
      video_ts REAL,
      type TEXT,
      severity TEXT,
      confidence REAL,
      track_ids TEXT,
      zone_id TEXT,
      direction TEXT,
      is_night INT DEFAULT 0,
      snapshot_path TEXT,
      metadata TEXT,
      status TEXT DEFAULT 'new'
    );
    CREATE TABLE evidence(
      id TEXT PRIMARY KEY,
      event_id TEXT REFERENCES events(id),
      kind TEXT,
      path TEXT,
      created_at TEXT
    );
    CREATE INDEX idx_events_session_ts ON events(session_id, ts);
    CREATE INDEX idx_events_type_ts ON events(type, ts);
    CREATE INDEX idx_events_severity_ts ON events(severity, ts);
    CREATE INDEX idx_tracks_session ON tracks(session_id);
    CREATE INDEX idx_zones_source ON zones(source_id);
    """,
    # M7 (ADR-002 §14 future-migrations pattern): geographic layer.
    # GEOGRAPHIC/OPERATIONAL zones — polygons in lat/lng on the map.
    # DISTINCT concept from the `zones` table (video-space, normalized
    # frame coordinates); never merged, never conflated (ADR-002 MANDATE).
    2: """
    CREATE TABLE geo_sectors(
      id TEXT PRIMARY KEY,
      name TEXT,
      kind TEXT DEFAULT 'sector',
      description TEXT,
      polygon TEXT,
      active INT DEFAULT 1,
      created_at TEXT,
      updated_at TEXT
    );
    ALTER TABLE sources ADD COLUMN latitude REAL;
    ALTER TABLE sources ADD COLUMN longitude REAL;
    ALTER TABLE sources ADD COLUMN label TEXT;
    CREATE INDEX idx_geo_sectors_active ON geo_sectors(active);
    """,
    # Migration 3 (V3.5 / V5): Persisted track trajectories for investigation.
    3: """
    ALTER TABLE tracks ADD COLUMN trajectory TEXT DEFAULT NULL;
    """,
}
