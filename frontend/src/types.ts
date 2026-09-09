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
  models: { detector: { file: string; present: boolean; size_mb: number | null } };
  db: { ok?: boolean };
  writer: { writer?: string } & Record<string, unknown>;
  active_session: string | null;
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
