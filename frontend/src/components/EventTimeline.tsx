// EventTimeline — live event stream: SSE pushes (/api/stream/events)
// merged with REST backfill (/api/events). Severity chips, source,
// zone/track info, ack state. Click → investigation detail.

import type { Store } from '../store';
import type { EventRow } from '../types';
import { EmptyState, Panel, SevChip, eventTone, eventTypeLabel } from './ui';

export function EventRowView({ ev, store, dense = false }: {
  ev: EventRow; store: Store; dense?: boolean;
}) {
  const selected = store.selectedEventId === ev.id;
  const tone = eventTone(ev.type);
  const time = ev.ts.slice(11, 23);
  return (
    <button
      onClick={() => store.selectEvent(selected ? null : ev.id)}
      className={`w-full text-left px-2.5 py-1.5 border-l-2 transition-colors ${
        selected
          ? 'border-cc-blue bg-cc-panel2'
          : `border-l-transparent hover:bg-cc-panel2/60 ${ev.status === 'new' && ev.severity === 'HIGH' ? 'bg-cc-red/5' : ''}`
      }`}
    >
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-[10px] font-mono text-cc-dim shrink-0">{time}</span>
        <SevChip severity={ev.severity} />
        <span className={`text-[11px] truncate ${
          tone === 'red' ? 'text-cc-red font-semibold' : 'text-cc-text'}`}>
          {eventTypeLabel(ev.type)}
        </span>
        {ev.status === 'new' ? (
          <span className="ml-auto shrink-0 w-1.5 h-1.5 rounded-full bg-cc-amber" title="unacked" />
        ) : (
          <span className="ml-auto shrink-0 text-[9px] text-cc-dim font-mono">ACK</span>
        )}
      </div>
      {!dense && (
        <div className="flex items-center gap-3 text-[10px] text-cc-dim font-mono mt-0.5 min-w-0">
          <span className="truncate">{ev.source_id}</span>
          {ev.zone_id && <span className="text-cc-amber/80">zone {ev.zone_id.slice(0, 11)}</span>}
          {ev.track_ids.length > 0 && (
            <span>track {ev.track_ids.map(t => `#${t}`).join(',')}</span>
          )}
          {ev.direction && <span className="text-cc-blue">{ev.direction}</span>}
          {ev.video_ts != null && <span className="shrink-0">v+{ev.video_ts.toFixed(1)}s</span>}
        </div>
      )}
    </button>
  );
}

export default function EventTimeline({ store, limit }: { store: Store; limit?: number }) {
  const events = limit ? store.events.slice(0, limit) : store.events;
  return (
    <Panel
      title="Event Stream"
      right={
        <span className="text-[10px] font-mono text-cc-dim">
          {store.sseState === 'open' ? '● LIVE' : '○ RECONNECTING'}
        </span>
      }
      className="min-h-0"
      scroll
    >
      {events.length === 0
        ? <EmptyState>no events — sessions on this server will report here</EmptyState>
        : events.map(ev => (
          <EventRowView key={ev.id} ev={ev} store={store} />
        ))}
    </Panel>
  );
}
