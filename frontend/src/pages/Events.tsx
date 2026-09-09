// Events — full event log: live SSE + REST backfill with severity
// filter + pagination (keyset cursor), investigation detail on select.

import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import EventDetail from '../components/EventDetail';
import { EventRowView } from '../components/EventTimeline';
import { EmptyState, Panel, Pill } from '../components/ui';
import type { Store } from '../store';
import type { EventRow } from '../types';

const SEV_FILTERS = ['', 'HIGH', 'MEDIUM', 'LOW', 'INFO'] as const;

export default function Events({ store }: { store: Store }) {
  const [severity, setSeverity] = useState<string>('');
  const [page, setPage] = useState<EventRow[]>([]);
  const [cursor, setCursor] = useState<{ before: string; before_id: string } | null>(null);
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(false);

  // live events matching filter, from the SSE-fed store
  const live = store.events.filter(
    e => !severity || e.severity === severity);

  const loadPage = useCallback(async (cur: { before: string; before_id: string } | null, append: boolean) => {
    setLoading(true);
    try {
      const r = await api.events({
        severity: severity || undefined,
        limit: 50,
        ...(cur ?? {}),
      });
      setPage(prev => append ? [...prev, ...r.events] : r.events);
      setCount(r.count);
      setCursor(r.next_before && r.next_before_id
        ? { before: r.next_before, before_id: r.next_before_id }
        : null);
    } catch { /* transient */ } finally { setLoading(false); }
  }, [severity]);

  useEffect(() => {
    setPage([]);
    setCursor(null);
    void loadPage(null, false);
  }, [loadPage]);

  return (
    <div className="h-full min-h-0 grid grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)] gap-1.5">
      <Panel
        title="Event Log"
        right={
          <div className="flex items-center gap-1.5">
            {SEV_FILTERS.map(f => (
              <button
                key={f}
                onClick={() => setSeverity(f)}
                className={`text-[9px] font-mono px-1.5 py-0.5 border rounded-sm ${
                  severity === f ? 'border-cc-blue text-cc-blue bg-cc-blue/10'
                    : 'border-cc-line text-cc-dim hover:text-cc-text'
                }`}
              >
                {f || 'ALL'}
              </button>
            ))}
            <Pill tone={store.sseState === 'open' ? 'green' : 'amber'}>
              {store.sseState === 'open' ? '● LIVE' : '○ REST ONLY'}
            </Pill>
          </div>
        }
        scroll
        className="min-h-0"
      >
        {live.length === 0 && page.length === 0 && !loading
          ? <EmptyState>no events match — run a session to generate detections</EmptyState>
          : <div>
              {/* live section */}
              {live.length > 0 && (
                <>
                  <div className="px-2.5 py-1 text-[9px] uppercase tracking-wider text-cc-dim sticky top-0 bg-cc-panel border-b border-cc-line/60 z-10">
                    Live — SSE ({live.length})
                  </div>
                  {live.map(ev => <EventRowView key={ev.id} ev={ev} store={store} />)}
                </>
              )}
              {/* persisted section */}
              <div className="px-2.5 py-1 text-[9px] uppercase tracking-wider text-cc-dim sticky top-0 bg-cc-panel border-b border-cc-line/60 z-10">
                Persisted — REST ({page.length} shown{count === 50 ? '+' : ''})
              </div>
              {page.filter(ev => !live.some(l => l.id === ev.id)).map(ev => (
                <EventRowView key={`p-${ev.id}`} ev={ev} store={store} />
              ))}
              {cursor && (
                <button
                  disabled={loading}
                  onClick={() => void loadPage(cursor, true)}
                  className="w-full py-2 text-[10px] font-mono text-cc-dim hover:text-cc-text border-t border-cc-line/60 disabled:opacity-50"
                >
                  {loading ? 'LOADING…' : 'LOAD OLDER 50'}
                </button>
              )}
            </div>}
      </Panel>
      <EventDetail store={store} />
    </div>
  );
}
