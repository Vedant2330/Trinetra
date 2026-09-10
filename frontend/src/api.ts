// API client — thin fetch wrappers over the REAL backend surface.
// Every function maps 1:1 to a real endpoint; nothing invented.

import type {
  EventRow, EventSummaryData, GeoCamera, GeoSector, Health, MapConfig, ReidPerson,
  SessionHistory, SessionStatus, SessionSummary, SourceRow, TrackAgg, UploadInfo,
  WebcamScan, ZoneRow,
} from './types';

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail ?? ''; } catch { /* no body */ }
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () =>
    fetch('/api/health').then(r => j<Health>(r)),

  sessionStatus: () =>
    fetch('/api/session/status').then(r => j<SessionStatus>(r)),

  sessionStart: (body: { type: 'file' | 'webcam' | 'rtsp'; path?: string; index?: number; uri?: string }) =>
    fetch('/api/session/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(r => j<{ status: string; session: Record<string, unknown> }>(r)),

  sessionStop: () =>
    fetch('/api/session/stop', { method: 'POST' })
      .then(r => j<{ status: string; stopped: Record<string, unknown> | null }>(r)),

  sessionLayersGet: () =>
    fetch('/api/session/layers')
      .then(r => j<{ layers: Record<string, boolean> }>(r)),

  sessionLayersPost: (updates: Partial<Record<'boxes' | 'labels' | 'fps' | 'trajectories' | 'zones' | 'faces', boolean>>) =>
    fetch('/api/session/layers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    }).then(r => j<{ layers: Record<string, boolean> }>(r)),

  events: (params: { session_id?: string; severity?: string; type?: string; limit?: number; before?: string; before_id?: string } = {}) => {
    const q = new URLSearchParams();
    if (params.session_id) q.set('session_id', params.session_id);
    if (params.severity) q.set('severity', params.severity);
    if (params.type) q.set('type', params.type);
    if (params.limit) q.set('limit', String(params.limit));
    if (params.before && params.before_id) {
      q.set('before', params.before);
      q.set('before_id', params.before_id);
    }
    return fetch(`/api/events?${q}`).then(r =>
      j<{ events: EventRow[]; count: number; next_before: string | null; next_before_id: string | null }>(r));
  },

  ackEvent: (id: string) =>
    fetch(`/api/events/${id}/ack`, { method: 'POST' })
      .then(r => j<{ status: string; event_id: string; acked: boolean }>(r)),

  eventSummary: (id: string) =>
    fetch(`/api/events/${id}/summary`).then(r => j<EventSummaryData>(r)),

  zones: () =>
    fetch('/api/zones').then(r => j<{ zones: ZoneRow[] }>(r)),

  createZone: (body: { source_id: string; name: string; kind: 'polygon' | 'line'; type: 'WATCH' | 'RESTRICTED'; geometry: Record<string, unknown>; active?: boolean }) =>
    fetch('/api/zones', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(r => j<ZoneRow>(r)),

  updateZone: (id: string, body: { name?: string; type?: string; active?: boolean; geometry?: Record<string, unknown> }) =>
    fetch(`/api/zones/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(r => j<ZoneRow>(r)),

  deleteZone: (id: string) =>
    fetch(`/api/zones/${id}`, { method: 'DELETE' })
      .then(r => j<{ status: string; deleted: string }>(r)),

  // ---- V2 source integration ----
  webcamScan: () =>
    fetch('/api/sources/webcam/scan', { method: 'POST' })
      .then(r => j<WebcamScan>(r)),

  uploadVideo: (file: File, onProgress?: (pct: number) => void) =>
    new Promise<UploadInfo>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/api/sources/upload');
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(Math.round((e.loaded / e.total) * 100));
      };
      xhr.onload = () => {
        try {
          const body = JSON.parse(xhr.responseText || '{}');
          if (xhr.status >= 200 && xhr.status < 300) resolve(body as UploadInfo);
          else reject(new Error(body.detail ?? `upload failed (${xhr.status})`));
        } catch { reject(new Error(`upload failed (${xhr.status})`)); }
      };
      xhr.onerror = () => reject(new Error('network error during upload'));
      const fd = new FormData();
      fd.append('file', file);
      xhr.send(fd);
    }),

  sources: () =>
    fetch('/api/sources').then(r => j<{ sources: SourceRow[] }>(r)),

  sessions: (limit = 50) =>
    fetch(`/api/sessions?limit=${limit}`).then(r =>
      j<{ sessions: SessionHistory[]; count: number }>(r)),

  sessionTracks: (id: string) =>
    fetch(`/api/sessions/${id}/tracks`).then(r =>
      j<{ session_id: string; tracks: TrackAgg[]; count: number }>(r)),

  sessionSummary: (id: string) =>
    fetch(`/api/sessions/${id}/summary`).then(r =>
      j<SessionSummary>(r)),

  // ---- M7 geographic layer ----
  mapConfig: () =>
    fetch('/api/map/config').then(r => j<MapConfig>(r)),

  mapCameras: () =>
    fetch('/api/map/cameras').then(r => j<{ cameras: GeoCamera[] }>(r)),

  setCameraGeo: (id: string, latitude: number, longitude: number, label: string) =>
    fetch(`/api/map/cameras/${encodeURIComponent(id)}/geo`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ latitude, longitude, label }),
    }).then(r => j<{ status: string; camera: { camera_id: string; latitude: number; longitude: number; label: string } }>(r)),

  mapSectors: () =>
    fetch('/api/map/sectors').then(r => j<{ sectors: GeoSector[] }>(r)),

  createSector: (body: { name: string; kind?: string; description?: string; polygon: number[][]; active?: boolean }) =>
    fetch('/api/map/sectors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(r => j<GeoSector>(r)),

  deleteSector: (id: string) =>
    fetch(`/api/map/sectors/${id}`, { method: 'DELETE' })
      .then(r => j<{ status: string; deleted: string }>(r)),

  // ---- Phase 2 cross-camera Re-ID ----
  reidPersons: () =>
    fetch('/api/reid/persons')
      .then(r => j<{ persons: ReidPerson[]; count: number; note?: string }>(r)),

  reidPerson: (pid: string) =>
    fetch(`/api/reid/persons/${encodeURIComponent(pid)}`)
      .then(r => j<ReidPerson>(r)),
};

// Evidence URL helper — the registered snapshot for an event, when any.
export const evidenceUrl = (ev: EventRow): string | null => {
  if (!ev.snapshot_path) return null;
  const file = ev.snapshot_path.split('/').pop();
  if (!file || !file.includes('.')) return null;
  return `/api/evidence/${ev.id}/${file}`;
};
