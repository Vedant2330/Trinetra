// Cameras — V3 T2.3: the camera-management registry to spec. One row
// per REAL camera record (merged /api/map/cameras + /api/sources):
// camera_id, name, source, source type, status (LIVE only when a
// session is actually running on it — backend-enforced), lat/lng ('—'
// when unplaced), location. The honest RTSP panel stays; the upload
// note stays. No fake cameras, ever.

import { useEffect, useState } from 'react';
import { api } from '../api';
import { EmptyState, Panel, Pill, StatusDot } from '../components/ui';
import type { Store } from '../store';
import type { SourceRow } from '../types';

export default function Sources({ store }: { store: Store }) {
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const { cameras, selectedCamera, selectCamera } = store;

  const refresh = () => {
    api.sources().then(r => setSources(r.sources)).catch(e => setErr(String(e)));
  };
  useEffect(refresh, [store.status.active, store.events.length]);

  return (
    <div className="h-full min-h-0 grid grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)] gap-2">
      {/* camera registry — REAL records only */}
      <Panel
        title="Camera Registry"
        right={<Pill tone="dim">{cameras.length} registered</Pill>}
        scroll
        className="min-h-0"
      >
        {err && <div className="text-[10px] font-mono text-cc-red px-2 pt-2">{err}</div>}
        {cameras.length === 0
          ? <EmptyState>no cameras registered — a camera row is created when a session starts</EmptyState>
          : <table className="w-full text-[11px] font-mono">
              <thead className="sticky top-0 bg-cc-panel text-cc-dim text-[9px] uppercase tracking-wider">
                <tr className="border-b border-cc-line">
                  <th className="text-left px-2.5 py-1.5">Camera</th>
                  <th className="text-left px-2.5 py-1.5">Name</th>
                  <th className="text-left px-2.5 py-1.5">Source Type</th>
                  <th className="text-left px-2.5 py-1.5">Status</th>
                  <th className="text-left px-2.5 py-1.5">Latitude</th>
                  <th className="text-left px-2.5 py-1.5">Longitude</th>
                  <th className="text-left px-2.5 py-1.5">Location</th>
                </tr>
              </thead>
              <tbody>
                {cameras.map(c => {
                  const src = sources.find(s => s.id === c.camera_id);
                  const live = c.status === 'live';
                  const sel = selectedCamera === c.camera_id;
                  return (
                    <tr
                      key={c.camera_id}
                      onClick={() => selectCamera(sel ? null : c.camera_id)}
                      className={`border-b border-cc-line/40 cursor-pointer transition-colors ${
                        sel ? 'bg-cc-blue/10' : 'hover:bg-cc-panel2/70'
                      }`}
                    >
                      <td className="px-2.5 py-1.5">
                        <span className="flex items-center gap-1.5">
                          <StatusDot ok={live} warn={!live}
                            title={live ? 'LIVE — session running on this camera'
                              : c.status === 'error' ? 'error state' : 'CONFIGURED — no active session'} />
                          <span className="truncate max-w-48">{c.camera_id}</span>
                        </span>
                      </td>
                      <td className="px-2.5 py-1.5 text-cc-dim truncate max-w-36" title={c.label}>
                        {c.label || '—'}
                      </td>
                      <td className="px-2.5 py-1.5 text-cc-dim">{c.type ?? src?.type ?? '—'}</td>
                      <td className="px-2.5 py-1.5">
                        <span className={`text-[10px] px-1.5 py-0.5 border rounded-sm uppercase ${
                          live ? 'text-cc-accent border-cc-accent/40'
                            : c.status === 'error'
                              ? 'text-cc-red border-cc-red/40'
                              : 'text-cc-dim border-cc-line'
                        }`}>
                          {live ? 'LIVE' : c.status === 'error' ? 'ERROR' : 'CONFIGURED'}
                        </span>
                      </td>
                      <td className="px-2.5 py-1.5 text-cc-dim">
                        {c.has_coordinates ? c.latitude!.toFixed(5) : '—'}
                      </td>
                      <td className="px-2.5 py-1.5 text-cc-dim">
                        {c.has_coordinates ? c.longitude!.toFixed(5) : '—'}
                      </td>
                      <td className="px-2.5 py-1.5 text-cc-dim truncate max-w-32"
                        title={c.has_coordinates ? 'geo-placed (simulated deployment — labeled on Map page)'
                          : 'not placed on the map yet'}>
                        {c.has_coordinates ? 'geo-placed' : 'unplaced'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>}
      </Panel>

      <div className="grid grid-rows-[auto_auto_minmax(0,1fr)] gap-2 min-h-0">
        {/* RTSP Network Camera capability */}
        <Panel title="RTSP / Network Cameras" className="shrink-0">
          <div className="px-3 py-3 text-[11px] font-mono text-cc-dim">
            <span className="text-cc-accent">AVAILABLE</span> in Phase 7 —
            <code className="text-cc-text">RtspSource</code> with TCP interleaved transport
            (<code className="text-cc-text">rtsp_transport;tcp</code>) and credential sanitization.
            Connect via the Live View / Input Source panel.
          </div>
        </Panel>
        <Panel title="Source Rows — DB" scroll className="min-h-0">
          <div className="p-2 space-y-1">
            {sources.map(s => (
              <div key={s.id} className="flex items-center gap-2 border border-cc-line rounded-lg px-2 py-1 bg-cc-panel2/40">
                <StatusDot ok={s.live} warn={!s.live} title={s.live ? 'live session' : 'not active'} />
                <span className="text-[10px] font-mono truncate flex-1">{s.id}</span>
                <span className="text-[9px] font-mono text-cc-dim">{s.type}</span>
                <span className={`text-[9px] font-mono ${s.live ? 'text-cc-accent' : 'text-cc-dim'}`}>
                  {s.live ? 'LIVE' : s.status}
                </span>
              </div>
            ))}
            {sources.length === 0 && (
              <div className="text-[10px] font-mono text-cc-dim text-center py-3">
                no source rows — created at session start
              </div>
            )}
          </div>
        </Panel>
        <Panel title="Uploads" scroll className="min-h-0">
          <div className="px-3 py-2 text-[10px] font-mono text-cc-dim">
            Uploads land in <span className="text-cc-text">uploads/</span> (probe-validated
            by the same FileSource a session opens). Start analysis from the
            Live View page after upload.
          </div>
        </Panel>
      </div>
    </div>
  );
}
