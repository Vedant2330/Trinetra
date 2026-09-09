// Analytics — real counts over the event log: severity/type breakdown,
// per-hour activity (from REAL event timestamps), night share. All
// values derive from /api/events rows; no synthetic charts.

import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import { EmptyState, Panel, Pill } from '../components/ui';
import type { Store } from '../store';
import type { EventRow } from '../types';

export default function Analytics({ store }: { store: Store }) {
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

  const bySev = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of merged) m.set(e.severity, (m.get(e.severity) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [merged]);

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

  const nightCount = merged.filter(e => e.is_night).length;
  const maxHour = Math.max(1, ...byHour.map(([, n]) => n));
  const maxType = Math.max(1, ...byType.map(([, n]) => n));

  if (loading && merged.length === 0) {
    return <EmptyState>loading event analytics…</EmptyState>;
  }

  return (
    <div className="h-full min-h-0 grid grid-rows-[auto_minmax(0,1fr)_minmax(0,1fr)] gap-1.5">
      <Panel title="Event Totals" className="shrink-0 min-h-0">
        <div className="grid grid-cols-6 gap-1.5 p-2">
          <Stat label="Total Events" value={merged.length} />
          <Stat label="High" value={bySev.find(([s]) => s === 'HIGH')?.[1] ?? 0} tone="red" />
          <Stat label="Medium" value={bySev.find(([s]) => s === 'MEDIUM')?.[1] ?? 0} tone="amber" />
          <Stat label="Low" value={bySev.find(([s]) => s === 'LOW')?.[1] ?? 0} tone="blue" />
          <Stat label="Info" value={bySev.find(([s]) => s === 'INFO')?.[1] ?? 0} tone="dim" />
          <Stat label="Night Events" value={nightCount} />
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

function Stat({ label, value, tone = 'text' }: {
  label: string; value: number; tone?: 'red' | 'amber' | 'blue' | 'dim' | 'text';
}) {
  const colors = {
    red: 'text-cc-red', amber: 'text-cc-amber', blue: 'text-cc-blue',
    dim: 'text-cc-dim', text: 'text-cc-text',
  };
  return (
    <div className="bg-cc-panel2 border border-cc-line rounded px-2.5 py-1.5">
      <div className="text-[9px] uppercase tracking-wider text-cc-dim truncate">{label}</div>
      <div className={`font-mono text-lg leading-tight ${colors[tone]}`}>{value}</div>
    </div>
  );
}
