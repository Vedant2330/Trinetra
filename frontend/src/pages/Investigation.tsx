// Investigation — the clip-intelligence page (V2 dispatch §22): pick a
// REAL session from history, see its summary (stats flushed at end) +
// per-track aggregates (§14: first/last seen, frames, max conf, class, trajectory).
// Only backend-provided measurements; no invented trajectory data.

import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { EmptyState, Panel, Pill } from '../components/ui';
import type { Store } from '../store';
import type { SessionHistory, SessionSummary, TrackAgg } from '../types';

const VEHICLE = new Set(['bicycle', 'car', 'motorcycle', 'bus', 'truck']);

function fmtDuration(from: string | null, to: string | null): string {
  if (!from || !to) return '—';
  const ms = new Date(to).getTime() - new Date(from).getTime();
  if (Number.isNaN(ms)) return '—';
  return `${(ms / 1000).toFixed(1)}s`;
}

function TrajectoryCanvas({ trajectory, isVehicle }: { trajectory?: { x: number; y: number; t: number }[] | null; isVehicle: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const cvs = canvasRef.current;
    if (!cvs) return;
    const ctx = cvs.getContext('2d');
    if (!ctx) return;

    const w = cvs.width;
    const h = cvs.height;
    ctx.clearRect(0, 0, w, h);

    // Subtle dark background
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, w, h);

    if (!trajectory || trajectory.length === 0) return;

    if (trajectory.length === 1) {
      ctx.fillStyle = isVehicle ? '#38bdf8' : '#f59e0b';
      ctx.beginPath();
      ctx.arc(trajectory[0].x * w, trajectory[0].y * h, 2, 0, Math.PI * 2);
      ctx.fill();
      return;
    }

    // Polyline
    ctx.strokeStyle = isVehicle ? '#38bdf8' : '#f59e0b';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    trajectory.forEach((pt, i) => {
      const px = Math.max(1, Math.min(w - 1, pt.x * w));
      const py = Math.max(1, Math.min(h - 1, pt.y * h));
      if (i === 0) ctx.moveTo(px, py);
      else ctx.lineTo(px, py);
    });
    ctx.stroke();

    // Start point (emerald)
    const p0 = trajectory[0];
    ctx.fillStyle = '#10b981';
    ctx.beginPath();
    ctx.arc(p0.x * w, p0.y * h, 2, 0, Math.PI * 2);
    ctx.fill();

    // End point (rose)
    const pN = trajectory[trajectory.length - 1];
    ctx.fillStyle = '#f43f5e';
    ctx.beginPath();
    ctx.arc(pN.x * w, pN.y * h, 2, 0, Math.PI * 2);
    ctx.fill();
  }, [trajectory, isVehicle]);

  if (!trajectory || trajectory.length === 0) {
    return <span className="text-cc-dim text-[10px]">—</span>;
  }

  return (
    <canvas
      ref={canvasRef}
      width={56}
      height={28}
      className="rounded border border-cc-line/60 inline-block align-middle"
      title={`${trajectory.length} waypoints recorded`}
    />
  );
}

export default function Investigation({ store }: { store: Store }) {
  const [sessions, setSessions] = useState<SessionHistory[]>([]);
  const [picked, setPicked] = useState<SessionHistory | null>(null);
  const [tracks, setTracks] = useState<TrackAgg[]>([]);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void api.sessions(50).then(r => setSessions(r.sessions)).catch(() => {});
  }, [store.status.active === false]); // refresh when a session completes

  useEffect(() => {
    if (!picked) {
      setTracks([]);
      setSummary(null);
      return;
    }
    setLoading(true);
    Promise.all([
      api.sessionTracks(picked.id).catch(() => ({ tracks: [] })),
      api.sessionSummary(picked.id).catch(() => null),
    ])
      .then(([trRes, sumRes]) => {
        setTracks(trRes.tracks || []);
        setSummary(sumRes);
      })
      .finally(() => setLoading(false));
  }, [picked]);

  const stats = picked?.stats;
  const people = summary?.people_detected ?? tracks.filter(t => t.class_name === 'person').length;
  const vehicles = summary?.vehicles_detected ?? tracks.filter(t => VEHICLE.has(t.class_name)).length;
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
        <Panel title="Clip Summary & Audit Trail" className="min-h-0 shrink-0">
          {!picked ? (
            <EmptyState>select a session from the left</EmptyState>
          ) : (
            <div className="p-2 space-y-2">
              <div className="grid grid-cols-3 lg:grid-cols-6 gap-1.5">
                <Stat label="Source" value={picked.source_id} mono />
                <Stat label="Status" value={picked.status} mono />
                <Stat label="Duration" value={summary ? `${summary.duration_s}s` : fmtDuration(picked.started_at, picked.ended_at)} mono />
                <Stat label="Frames" value={summary?.frames ?? stats?.frames_processed ?? '—'} />
                <Stat label="Avg FPS" value={stats?.pipeline_fps?.toFixed(1) ?? '—'} />
                <Stat label="Events" value={stats?.events_committed ?? '—'} />
                <Stat label="Unique Tracks" value={summary?.unique_tracks ?? stats?.tracks_total ?? tracks.length} />
                <Stat label="People Tracks" value={people} />
                <Stat label="Vehicle Tracks" value={vehicles} />
                <Stat label="Peak People" value={summary?.max_concurrent_people ?? '—'} />
                <Stat
                  label="Zones Active"
                  value={summary?.zones_breached?.length ? summary.zones_breached.join(', ') : 'None'}
                />
              </div>

              {summary?.notes && summary.notes.length > 0 && (
                <div className="bg-cc-panel2 border border-cc-line rounded p-2 text-[11px] font-mono space-y-1">
                  <div className="text-[9px] uppercase tracking-wider text-cc-dim font-sans font-medium">
                    Deterministic Audit Trail
                  </div>
                  {summary.notes.map((note, i) => (
                    <div key={i} className="text-cc-text flex items-start gap-1.5">
                      <span className="text-cc-blue shrink-0">›</span>
                      <span>{note}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </Panel>

        <Panel
          title="Tracks — flushed aggregates & trajectory"
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
                    <th className="text-left px-2.5 py-1.5">Trajectory</th>
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
                      <td className="px-2.5 py-1.5">
                        <TrajectoryCanvas
                          trajectory={t.trajectory}
                          isVehicle={VEHICLE.has(t.class_name)}
                        />
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
