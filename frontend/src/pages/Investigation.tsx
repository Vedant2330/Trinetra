// Investigation — the clip-intelligence page (V2 dispatch §22): pick a
// REAL session from history, see its summary (stats flushed at end) +
// per-track aggregates (§14: first/last seen, frames, max conf, class).
// Only backend-provided measurements; no invented trajectory data.

import { useEffect, useState } from 'react';
import { api } from '../api';
import { EmptyState, Panel, Pill } from '../components/ui';
import type { Store } from '../store';
import type { SessionHistory, TrackAgg } from '../types';

const VEHICLE = new Set(['bicycle', 'car', 'motorcycle', 'bus', 'truck']);

function fmtDuration(from: string | null, to: string | null): string {
  if (!from || !to) return '—';
  const ms = new Date(to).getTime() - new Date(from).getTime();
  if (Number.isNaN(ms)) return '—';
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function Investigation({ store }: { store: Store }) {
  const [sessions, setSessions] = useState<SessionHistory[]>([]);
  const [picked, setPicked] = useState<SessionHistory | null>(null);
  const [tracks, setTracks] = useState<TrackAgg[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void api.sessions(50).then(r => setSessions(r.sessions)).catch(() => {});
  }, [store.status.active === false]); // refresh when a session completes

  useEffect(() => {
    if (!picked) { setTracks([]); return; }
    setLoading(true);
    api.sessionTracks(picked.id)
      .then(r => setTracks(r.tracks))
      .catch(() => setTracks([]))
      .finally(() => setLoading(false));
  }, [picked]);

  const stats = picked?.stats;
  const people = tracks.filter(t => t.class_name === 'person').length;
  const vehicles = tracks.filter(t => VEHICLE.has(t.class_name)).length;
  // the session the current investigation event belongs to
  const ev = store.events.find(e => e.id === store.selectedEventId);
  const suggested = ev ? sessions.find(s => s.id === ev.session_id) : undefined;

  return (
    <div className="h-full min-h-0 grid grid-cols-[300px_minmax(0,1fr)] gap-1.5">
      {/* session list */}
      <Panel
        title="Sessions"
        right={<Pill tone="dim">{sessions.length}</Pill>}
        scroll
        className="min-h-0"
      >
        {suggested && (
          <div className="px-2.5 py-1.5 text-[9px] font-mono text-cc-blue bg-cc-blue/5 border-b border-cc-line/60">
            event → session {suggested.id.slice(0, 8)}…
          </div>
        )}
        {sessions.length === 0
          ? <EmptyState>no sessions recorded yet</EmptyState>
          : sessions.map(s => (
              <button
                key={s.id}
                onClick={() => setPicked(s)}
                className={`w-full text-left px-2.5 py-2 border-b border-cc-line/50 hover:bg-cc-panel2/60 ${
                  picked?.id === s.id ? 'bg-cc-panel2 border-l-2 border-l-cc-blue' : ''
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-cc-dim shrink-0">
                    {s.started_at?.slice(5, 16).replace('T', ' ')}
                  </span>
                  <Pill tone={s.status === 'completed' ? 'green'
                    : s.status === 'error' ? 'red' : 'amber'}>
                    {s.status.toUpperCase()}
                  </Pill>
                </div>
                <div className="text-[10px] font-mono text-cc-dim truncate mt-0.5">
                  {s.source_id} · {s.id.slice(0, 8)}
                </div>
              </button>
            ))}
      </Panel>

      {/* clip intelligence */}
      <div className="grid grid-rows-[auto_minmax(0,1fr)] gap-1.5 min-h-0">
        <Panel title="Clip Summary" className="min-h-0 shrink-0">
          {!picked ? (
            <EmptyState>select a session from the left</EmptyState>
          ) : (
            <div className="grid grid-cols-3 lg:grid-cols-6 gap-1.5 p-2">
              <Stat label="Source" value={picked.source_id} mono />
              <Stat label="Status" value={picked.status} mono />
              <Stat label="Duration" value={fmtDuration(picked.started_at, picked.ended_at)} mono />
              <Stat label="Frames" value={stats?.frames_processed ?? '—'} />
              <Stat label="Avg FPS" value={stats?.pipeline_fps?.toFixed(1) ?? '—'} />
              <Stat label="Events" value={stats?.events_committed ?? '—'} />
              <Stat label="Unique Tracks" value={stats?.tracks_total ?? tracks.length} />
              <Stat label="People Tracks" value={people} />
              <Stat label="Vehicle Tracks" value={vehicles} />
            </div>
          )}
        </Panel>

        <Panel
          title="Tracks — flushed aggregates (§14)"
          right={<Pill tone="dim">{tracks.length} tracks</Pill>}
          scroll
          className="min-h-0"
        >
          {!picked ? <EmptyState>no session selected</EmptyState>
            : loading ? <EmptyState>loading track aggregates…</EmptyState>
            : tracks.length === 0 ? (
              <EmptyState>
                no track rows — the session flushed none (too short, or still running)
              </EmptyState>
            ) : (
              <table className="w-full text-[11px] font-mono">
                <thead className="sticky top-0 bg-cc-panel text-cc-dim text-[9px] uppercase tracking-wider">
                  <tr className="border-b border-cc-line">
                    <th className="text-left px-2.5 py-1.5">Track</th>
                    <th className="text-left px-2.5 py-1.5">Class</th>
                    <th className="text-left px-2.5 py-1.5">First Seen</th>
                    <th className="text-left px-2.5 py-1.5">Last Seen</th>
                    <th className="text-right px-2.5 py-1.5">Frames</th>
                    <th className="text-right px-2.5 py-1.5">Max Conf</th>
                    <th className="text-left px-2.5 py-1.5">Dwell (wall)</th>
                  </tr>
                </thead>
                <tbody>
                  {tracks.map(t => (
                    <tr key={t.track_id} className="border-b border-cc-line/40 hover:bg-cc-panel2/40">
                      <td className="px-2.5 py-1.5 text-cc-text">#{t.track_id}</td>
                      <td className="px-2.5 py-1.5">
                        <span className={VEHICLE.has(t.class_name) ? 'text-cc-blue' : 'text-cc-amber'}>
                          {t.class_name}
                        </span>
                      </td>
                      <td className="px-2.5 py-1.5 text-cc-dim">{t.first_seen?.slice(11, 23) || '—'}</td>
                      <td className="px-2.5 py-1.5 text-cc-dim">{t.last_seen?.slice(11, 23) || '—'}</td>
                      <td className="px-2.5 py-1.5 text-right">{t.frames}</td>
                      <td className="px-2.5 py-1.5 text-right">{(t.max_conf * 100).toFixed(0)}%</td>
                      <td className="px-2.5 py-1.5 text-cc-dim">{fmtDuration(t.first_seen, t.last_seen)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
        </Panel>
      </div>
    </div>
  );
}

function Stat({ label, value, mono = false }: { label: string; value: string | number; mono?: boolean }) {
  return (
    <div className="bg-cc-panel2 border border-cc-line rounded px-2.5 py-1.5 min-w-0">
      <div className="text-[9px] uppercase tracking-wider text-cc-dim truncate">{label}</div>
      <div className={`text-sm leading-tight truncate ${mono ? 'font-mono text-cc-text' : 'font-mono text-cc-text'}`}>
        {value}
      </div>
    </div>
  );
}
