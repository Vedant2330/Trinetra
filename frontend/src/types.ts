// Real backend payload types — mirrored from the Python source of truth:
//   health:      backend/main.py::health()
//   status:      backend/services/session.py::status_payload()
//   events:      backend/api/events.py::_row_to_json()
//   zones:       backend/api/zones.py::_row_to_json()
//   sources V2:  backend/api/sources.py (upload/scan/list/sessions)
//   map config:  backend/api/map.py (M7)
// No field is invented; anything absent in the backend is absent here.

export interface Health {
  ok: boolean;
  app: string;
  phase: string;
  uptime_s: number;
  device_policy: string;
  models: {
    detector: { file: string; present: boolean; size_mb: number | null };
    reid?: { file: string; present: boolean; size_mb: number | null };
    face?: { file: string; present: boolean; size_mb: number | null };
  };
  db: { ok?: boolean };
  writer: { writer?: string } & Record<string, unknown>;
  active_session: string | null;
  reid_enabled?: boolean;          // Phase 2: capability flag (config × model)
  face_enabled?: boolean;          // Phase 3: capability flag (model present)
}

export interface SessionStatus {
  active: boolean;
  session: SessionPayload | null;
}

export interface SessionPayload {
  source_id: string;
  status: 'starting' | 'running' | 'completed' | 'error' | 'stopped';
  device: string;
  frames_processed: number;
  pipeline_fps: number;
  active_tracks: number;
  total_tracks: number;
  people_detected: number;      // V3: cumulative unique person tracks (C5)
  vehicles_detected: number;    // V3: cumulative unique vehicle tracks
  active_people: number;
  active_vehicles: number;
  events_committed: number;
  zone_person_counts: Record<string, number>;
  error: string | null;
  uptime_s: number;
}

export interface EventRow {
  id: string;
  keepalive?: boolean;         // SSE heartbeat frames (backend sse.py)
  session_id: string;
  source_id: string;
  ts: string;
  video_ts: number | null;
  type: string;
  severity: 'INFO' | 'LOW' | 'MEDIUM' | 'HIGH' | string;
  confidence: number;
  track_ids: number[];
  zone_id: string | null;
  direction: string | null;
  is_night: boolean;
  snapshot_path: string | null;
  severity_reason?: string;   // engine rows carry it (engine.py:88)
  metadata: Record<string, unknown> & { snapshot_skipped_low_disk?: boolean; severity_reason?: string };
  status: 'new' | 'acked' | string;
}

export interface ZoneRow {
  id: string;
  source_id: string;
  name: string;
  kind: 'polygon' | 'line';
  zone_type: 'WATCH' | 'RESTRICTED' | string;
  geometry: {
    // polygon §12: points [[x,y],...] normalized 0..1
    points?: number[][];
    // line §12: p1/p2 foot points + direction
    p1?: number[];
    p2?: number[];
    direction_mode?: 'both' | 'forward' | 'reverse';
  };
  active: boolean;             // backend JSON boolean (sqlite row cast)
}

// ---- V2 source integration (backend/api/sources.py) ----

export interface WebcamScan {
  cameras: { index: number; id: string; status: string }[];
  count: number;
}

export interface UploadInfo {
  status: string;
  filename: string;
  path: string;
  size_bytes: number;
  fps: number;
  frame_count: number;
  width: number;
  height: number;
}

export interface SourceRow {
  id: string;
  name: string;
  type: string;
  status: string;
  live: boolean;
  created_at: string;
}

export interface SessionHistory {
  id: string;
  source_id: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  stats: {
    frames_processed?: number;
    pipeline_fps?: number;
    events_committed?: number;
    tracks_total?: number;
    zone_person_counts?: Record<string, number>;
  } | null;
}

export interface TrackAgg {
  track_id: number;
  class_name: string;
  first_seen: string;
  last_seen: string;
  frames: number;
  max_conf: number;
  trajectory?: { x: number; y: number; t: number }[] | null;
}

export interface SessionSummary {
  session_id: string;
  source_id: string;
  status: string;
  duration_s: number;
  frames: number;
  people_detected: number;
  vehicles_detected: number;
  unique_tracks: number;
  events_by_severity: Record<string, number>;
  events_by_type: Record<string, number>;
  zones_breached: string[];
  max_concurrent_people: number;
  first_event_ts: string | null;
  last_event_ts: string | null;
  notes: string[];
}

export interface EventSummaryStructured {
  what: {
    type: string;
    label: string;
    severity: string;
    confidence: number;
  };
  who: {
    track_ids: number[];
    class_names: string[];
    identity: string | null;
    identity_cameras: string[];
  };
  where: {
    source_id: string;
    source_label: string;
    coordinates: { latitude: number; longitude: number } | null;
    zone_id: string | null;
    zone_name: string | null;
    zone_kind: string | null;
    zone_type: string | null;
    geo_sectors: string[];
  };
  when: {
    ts: string;
    video_ts: number | null;
    is_night: boolean;
  };
  movement: {
    direction: string | null;
    kinematics: Record<string, unknown> | null;
  };
  why: {
    severity_reason: string | null;
    summary: string;
  };
  evidence: {
    snapshot_path: string | null;
    snapshot_available: boolean;
    skip_reason: string | null;
  };
}

export interface EventSummaryData {
  event_id: string;
  session_id: string;
  source_id: string;
  what: string;
  who: string;
  where: string;
  when: string;
  movement: string;
  why: string;
  evidence: string;
  narrative: string;
  structured: EventSummaryStructured;
}

// ---- Phase 2 cross-camera Re-ID (backend/reid/integration.py) ----

export interface ReidPerson {
  global_person_id: string;
  created_ts: number;
  first_seen_ts: number;
  last_seen_ts: number;
  observations: number;
  confidence: number;
  cameras_visited: string[];
  track_bindings: { camera_id: string; track_id: number; linked_ts: number; state: string }[];
  candidate_count: number;
  timeline?: { wall_ts: number; camera_id: string; track_id: number; kind: string; note?: string | null; zone_id?: string | null }[];
}

// ---- M7 geographic layer (ADR-002/003) ----

export interface MapConfig {
  google_maps_key: string;      // from /api/map/config — env, never in source
  has_tiles: boolean;
  fallback: 'satellite' | 'roadmap' | 'schematic';
  simulated: boolean;           // true → "Demo Operational Area" labeling
  label: string;
}

export interface GeoCamera {
  camera_id: string;
  source_id: string;
  label: string;
  latitude: number | null;
  longitude: number | null;
  sector_id: string | null;
  status: 'live' | 'idle' | 'error' | string;
  type?: string;               // source kind (webcam/file), from map API
  has_coordinates: boolean;
}

export interface GeoSector {
  id: string;
  name: string;
  kind: string;
  description: string | null;
  // [[lat,lng], ...] — geographic polygon, DISTINCT from video zones
  polygon: number[][];
  active: boolean;
}
