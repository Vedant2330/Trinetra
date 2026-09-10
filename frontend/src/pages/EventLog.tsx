// EventLog — V3 T2.2: the SQLite-backed TABLE view of every committed
// event (nav 'Event Log'). Columns map 1:1 to /api/events fields:
// Event ID, Time, Source, Type, Severity, Track ID, Metadata. Search
// is a client-side substring over loaded pages; 'Load older 50' walks
// the keyset cursor. Row click selects for the EventDetail panel.

import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import EventDetail from '../components/EventDetail';
import { EmptyState, Panel, Pill, SevChip } from '../components/ui';
import type { Store } from '../store';
import type { EventRow } from '../types';

export default function EventLog({ store }: { store: Store }) {
  const [rows, setRows] = useState<EventRow[]>([]);
  const [cursor, setCursor] = useState<{ before: string; before_id: string } | null>(null);
  const [q, setQ] = useState('');
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);

  const loadPage = useCallback(async (
    cur: { before: string; before_id: string } | null, append: boolean,
  ) => {
    setLoading(true);
    try {
      const r = await api.events({ limit: 50, ...(cur ?? {}) });
      setRows(prev => append ? [...prev, ...r.events] : r.events);
      setCount(r.count);
      setCursor(r.next_before && r.next_before_id
        ? { before: r.next_before, before_id: r.next_before_id }
        : null);
    } catch { /* transient */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { void loadPage(null, false); }, [loadPage]);

  // client-side substring search across id/type/source/zone/metadata
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return rows;
    return rows.filter(e => {
      const zoneName = e.zone_id
        ? (store.zones.find(z => z.id === e.zone_id)?.name ?? e.zone_id) : '';
      return [e.id, e.type, e.source_id, zoneName,
        JSON.stringify(e.metadata ?? {})]
        .some(s => s.toLowerCase().includes(needle));
    });
  }, [rows, q, store.zones]);

  const zoneName = (id: string | null) => {
    if (!id) return '—';
    const z = store.zones.find(z => z.id === id);
    return z ? (z.name || z.id.slice(0, 11)) : id.slice(0, 11);
  };

  return (
    <div className="h-full min-h-0 grid grid-cols-[minmax(0,1.7fr)_minmax(0,1fr)] gap-2">
      <Panel
        title="Event Log — SQLite"
        right={
          <div className="flex items-center gap-1.5">
            <input
              value={q}
              onChange={e => setQ(e.target.value)}
              placeholder="search id / type / source / zone / metadata…"
              className="text-[10px] font-mono px-1.5 py-0.5 w-56 border border-cc-line rounded-sm bg-cc-panel text-cc-text placeholder:text-cc-dim/70"
            />
            <Pill tone="dim">{filtered.length} rows</Pill>
          </div>
        }
        scroll
        className="min-h-0"
      >
        {filtered.length === 0 && !loading
          ? <EmptyState>
              {q ? 'no rows match the search' : 'event table empty — run a session to commit events'}
            </EmptyState>
          : <div className="w-full">
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 bg-cc-panel z-10">
                  <tr className="text-[9px] uppercase tracking-wider text-cc-dim border-b border-cc-line">
                    <th className="px-2 py-1.5 font-semibold">Event ID</th>
                    <th className="px-2 py-1.5 font-semibold">Time</th>
                    <th className="px-2 py-1.5 font-semibold">Source</th>
                    <th className="px-2 py-1.5 font-semibold">Type</th>
                    <th className="px-2 py-1.5 font-semibold">Severity</th>
                    <th className="px-2 py-1.5 font-semibold">Track ID</th>
                    <th className="px-2 py-1.5 font-semibold">Metadata</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(e => {
                    const sel = store.selectedEventId === e.id;
                    const meta = e.metadata ?? {};
                    const chips = Object.entries(meta).slice(0, 4)
                      .filter(([, v]) => v !== null && v !== undefined);
                    return (
                      <tr
                        key={e.id}
                        onClick={() => store.selectEvent(e.id)}
                        className={`text-[10px] font-mono cursor-pointer border-b border-cc-line/50 transition-colors ${
                          sel ? 'bg-cc-blue/10' : 'hover:bg-cc-panel2/70'
                        }`}
                      >
                        <td className="px-2 py-1 text-cc-dim" title={`${e.id} — click to copy`}
                          onClick={ev => { ev.stopPropagation(); void navigator.clipboard?.writeText(e.id); }}>
                          {e.id.slice(0, 8)}…
                        </td>
                        <td className="px-2 py-1 whitespace-nowrap">
                          {new Date(e.ts).toLocaleTimeString()}
                        </td>
                        <td className="px-2 py-1 max-w-36 truncate text-cc-dim" title={e.source_id}>
                          {e.source_id}
                        </td>
                        <td className="px-2 py-1 whitespace-nowrap">
                          {e.type.replace(/_/g, ' ')}
                        </td>
                        <td className="px-2 py-1"><SevChip severity={e.severity} /></td>
                        <td className="px-2 py-1">
                          {e.track_ids?.length ? `#${e.track_ids.join(', #')}` : '—'}
                        </td>
                        <td className="px-2 py-1 max-w-56">
                          <span className="flex gap-1 flex-wrap">
                            {e.zone_id && (
                              <span className="text-[9px] px-1 border border-cc-line rounded-sm text-cc-dim"
                                title={`zone ${zoneName(e.zone_id)}`}>
                                {zoneName(e.zone_id)}
                              </span>
                            )}
                            {chips.map(([k, v]) => (
                              <span key={k} className="text-[9px] px-1 border border-cc-line rounded-sm text-cc-dim"
                                title={`${k}: ${String(v)}`}>
                                {k === 'track_class' ? String(v) : `${k}:${String(v)}`}
                              </span>
                            ))}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {cursor && (
                <button
                  disabled={loading}
                  onClick={() => void loadPage(cursor, true)}
                  className="w-full py-2 text-[10px] font-mono text-cc-dim hover:text-cc-text border-t border-cc-line/60 disabled:opacity-50"
                >
                  {loading ? 'LOADING…' : 'LOAD OLDER 50'}
                </button>
              )}
              {count === 50 && !cursor && null}
            </div>}
      </Panel>
      <EventDetail store={store} />
    </div>
  );
}
