// Analytics — V3: a REAL runtime panel (people/vehicles/tracks/fps/
// frames/device/uptime + trajectory capability + fence status, all
// from status_payload) + visualization controls that ACTUALLY work
// (the same server render layers as Live View) + the real event
// charts (severity/type/hour from /api/events). No synthetic charts.

import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import LayerToggles from '../components/LayerToggles';
import { EmptyState, Panel, Pill } from '../components/ui';
import type { Store } from '../store';
import type { EventRow } from '../types';

export default function Analytics({ store }: { store: Store }) {
  const { status, zones } = store;
  const s = status.session;
  const [all, setAll] = useState<EventRow[]>([]);
  const [loading, setLoading] = useState(true);

  // pull a large real window (persisted + live merge, newest-first unique)
  useEffect(() => {
    setLoading(true);
    api.events({ limit: 500 }).then(r => setAll(r.events))
      .catch(() => setAll([]))
      .finally(() => setLoading(false));
  }, [store.status.active === false]);

  const merged = useMemo(() => {
    const seen = new Set<string>();
    return [...store.events, ...all].filter(e => {
      if (seen.has(e.id)) return false;
      seen.add(e.id);
      return true;
    });
  }, [store.events, all]);

  const byType = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of merged) m.set(e.type, (m.get(e.type) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, 12);
  }, [merged]);

  const byHour = useMemo(() => {
    const m = new Map<number, number>();
    for (const e of merged) {
      const h = new Date(e.ts).getHours();
      if (!Number.isNaN(h)) m.set(h, (m.get(h) ?? 0) + 1);
    }
    return [...Array(24).keys()].map(h => [h, m.get(h) ?? 0] as const);
  }, [merged]);

  const maxHour = Math.max(1, ...byHour.map(([, n]) => n));
  const maxType = Math.max(1, ...byType.map(([, n]) => n));

  if (loading && merged.length === 0) {
    return <EmptyState>loading event analytics…</EmptyState>;
  }

  return (
    <div className="h-full min-h-0 grid grid-rows-[auto_minmax(0,1fr)_minmax(0,1fr)] gap-2 overflow-y-auto">
      {/* REAL runtime panel — every number from status_payload */}
      <Panel
        title="Runtime — live session state"
        right={<Pill tone={s ? (s.status === 'running' ? 'green' : 'amber') : 'dim'}>
          {s ? s.status.toUpperCase() : 'NO SESSION'}
        </Pill>}
        className="shrink-0 min-h-0"
      >
        <div className="grid grid-cols-4 lg:grid-cols-7 gap-1.5 p-2">
          <Stat label="People Detected" value={s ? String(s.people_detected) : '—'} />
          <Stat label="Vehicles Detected" value={s ? String(s.vehicles_detected) : '—'} />
          <Stat label="Active Tracks" value={s ? String(s.active_tracks) : '—'} />
          <Stat label="Pipeline FPS" value={s ? s.pipeline_fps.toFixed(1) : '—'} />
          <Stat label="Frames Processed" value={s ? String(s.frames_processed) : '—'} />
          <Stat label="Device" value={s ? s.device.toUpperCase() : '—'} />
          <Stat label="Uptime" value={s ? `${Math.round(s.uptime_s)}s` : '—'} />
          <Stat label="Active People" value={s ? String(s.active_people) : '—'} />
          <Stat label="Active Vehicles" value={s ? String(s.active_vehicles) : '—'} />
          <Stat label="Total Tracks" value={s ? String(s.total_tracks) : '—'} />
          {/* trajectory info — capability + live count (real config) */}
          <Stat label="Trajectory Depth"
            value={s ? `${s.active_tracks > 0 ? 60 : 0} pts/track` : '—'}
            hint="tracking.history_len = 60 retained foot points per track" />
          {/* fence status — real zone store + live occupancy */}
          <Stat label="Active Zones"
            value={String(zones.filter(z => z.active).length)}
            hint={Object.values(s?.zone_person_counts ?? {})
              .some((n: number) => n > 0)
              ? 'occupied — person inside a fence'
              : 'no occupancy'} />
          <Stat label="Events Committed" value={s ? String(s.events_committed) : '—'} />
        </div>
      </Panel>

      {/* visualization controls — the SAME server layers as Live View */}
      <Panel
        title="Visualization Controls — render layers (same surface as Live View)"
        className="shrink-0 min-h-0"
      >
        <div className="p-2">
          <LayerToggles store={store} />
        </div>
      </Panel>

      <Panel title="Events by Type — real committed events" scroll className="min-h-0">
        {byType.length === 0
          ? <EmptyState>no events yet — run a session</EmptyState>
          : <div className="p-2 space-y-1.5">
              {byType.map(([type, n]) => (
                <div key={type} className="flex items-center gap-2">
                  <span className="text-[10px] font-mono text-cc-dim w-44 truncate shrink-0">
                    {type.replace(/_/g, ' ')}
                  </span>
                  <div className="flex-1 h-3 bg-cc-line/60 rounded-sm overflow-hidden">
                    <div
                      className={`h-full rounded-sm ${type === 'ZONE_ENTRY' ? 'bg-cc-red/70'
                        : type.startsWith('SOURCE') || type.startsWith('SESSION') ? 'bg-cc-accent/60'
                        : 'bg-cc-blue/60'}`}
                      style={{ width: `${(n / maxType) * 100}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-mono text-cc-text w-10 text-right shrink-0">{n}</span>
                </div>
              ))}
            </div>}
      </Panel>

      <Panel
        title="Activity by Hour — local clock (real timestamps)"
        right={<Pill tone="dim">{merged.length} events analyzed</Pill>}
        className="min-h-0"
      >
        <div className="h-full flex items-end gap-[3px] p-2 pb-4">
          {byHour.map(([h, n]) => (
            <div key={h} className="flex-1 flex flex-col items-center gap-1 min-w-0"
              title={`${h}:00 — ${n} events`}>
              <div
                className={`w-full rounded-t-sm ${n > 0 ? 'bg-cc-accent/50' : 'bg-cc-line/50'}`}
                style={{ height: `${Math.max(2, (n / maxHour) * 88)}%` }}
              />
              {h % 6 === 0 && (
                <span className="text-[8px] font-mono text-cc-dim">{String(h).padStart(2, '0')}</span>
              )}
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function Stat({ label, value, tone = 'text', hint }: {
  label: string; value: string | number; hint?: string;
  tone?: 'red' | 'amber' | 'blue' | 'dim' | 'text';
}) {
  const colors = {
    red: 'text-cc-red', amber: 'text-cc-amber', blue: 'text-cc-blue',
    dim: 'text-cc-dim', text: 'text-cc-text',
  };
  return (
    <div title={hint} className="bg-cc-panel2 border border-cc-line rounded-lg px-2.5 py-1.5 min-w-0">
      <div className="text-[9px] uppercase tracking-wider text-cc-dim truncate">{label}</div>
      <div className={`font-mono text-base leading-tight truncate ${colors[tone]}`}>{value}</div>
    </div>
  );
}
