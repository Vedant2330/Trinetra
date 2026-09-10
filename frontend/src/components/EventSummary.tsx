// EventSummary — V3.5 / Phase 6: DETERMINISTIC, field-faithful event summary.
// Answers WHAT / WHO / WHERE / WHEN / MOVEMENT / WHY / EVIDENCE from real database rows.
// Every absent field is explicitly labeled 'Not available'.
// Deterministic — same event, same summary.

import { useState } from 'react';
import { SevChip } from './ui';
import type { Store } from '../store';
import type { EventRow } from '../types';
import { buildEventSummary } from '../utils/eventSummary';

export function EventStructuredBlock({ event, store }: { event: EventRow; store: Store }) {
  const summary = buildEventSummary(event, store.zones, store.cameras, store.sectors);
  const [showJson, setShowJson] = useState(false);

  return (
    <div className="bg-cc-panel2 border border-cc-line rounded-md p-2.5 space-y-2 text-[11px] font-mono">
      <div className="flex items-center justify-between border-b border-cc-line pb-1">
        <div className="flex items-center gap-2">
          <SevChip severity={event.severity} />
          <span className="font-semibold text-cc-text">{summary.structured.what.label}</span>
          <span className="text-[10px] text-cc-dim">{event.ts}</span>
        </div>
        <button
          onClick={() => setShowJson(!showJson)}
          className="text-[9px] text-cc-dim hover:text-cc-text border border-cc-line px-1.5 py-0.5 rounded"
        >
          {showJson ? 'SHOW AUDIT' : 'SHOW JSON'}
        </button>
      </div>

      {showJson ? (
        <pre className="text-[10px] text-cc-dim bg-cc-bg p-2 rounded overflow-x-auto max-h-48">
          {JSON.stringify(summary.structured, null, 2)}
        </pre>
      ) : (
        <div className="space-y-1 text-cc-text">
          <div className="text-[11px] leading-relaxed text-cc-text/90 italic bg-cc-bg/40 p-1.5 rounded border border-cc-line/50">
            "{summary.narrative}"
          </div>
          <div className="grid grid-cols-[80px_1fr] gap-x-2 gap-y-1 pt-1 text-[10px]">
            <span className="text-cc-dim uppercase tracking-wider">WHAT</span>
            <span>{summary.what}</span>

            <span className="text-cc-dim uppercase tracking-wider">WHO</span>
            <span>{summary.who}</span>

            <span className="text-cc-dim uppercase tracking-wider">WHERE</span>
            <span className="truncate">{summary.where}</span>

            <span className="text-cc-dim uppercase tracking-wider">WHEN</span>
            <span>{summary.when}</span>

            <span className="text-cc-dim uppercase tracking-wider">MOVEMENT</span>
            <span>{summary.movement}</span>

            <span className="text-cc-dim uppercase tracking-wider">WHY</span>
            <span className="text-cc-amber">{summary.why}</span>

            <span className="text-cc-dim uppercase tracking-wider">EVIDENCE</span>
            <span className="text-cc-blue">{summary.evidence}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function EventSummary({
  store,
  count = 4,
  selectedOnly = false,
}: {
  store: Store;
  count?: number;
  selectedOnly?: boolean;
}) {
  const { events, zones, cameras, sectors, selectedEventId } = store;

  if (selectedOnly) {
    const selEvent = events.find(e => e.id === selectedEventId);
    if (!selEvent) {
      return (
        <div className="h-full flex items-center justify-center text-cc-dim text-[11px] font-mono p-4 text-center">
          select an alert from timeline or log to inspect structured audit summary
        </div>
      );
    }
    return <EventStructuredBlock event={selEvent} store={store} />;
  }

  const rows = events.filter(e => !e.keepalive).slice(0, count);

  return (
    <div className="h-full min-h-0 flex flex-col">
      {rows.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-cc-dim text-[11px] font-mono px-4 text-center">
          no events yet — run a session to generate real alerts
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto divide-y divide-cc-line">
          {rows.map(e => {
            const summary = buildEventSummary(e, zones, cameras, sectors);
            const isSelected = e.id === selectedEventId;
            return (
              <div
                key={e.id}
                className={`flex flex-col gap-1 px-2.5 py-2 hover:bg-cc-panel2/50 transition-colors ${
                  isSelected ? 'bg-cc-panel2 border-l-2 border-cc-blue' : ''
                }`}
              >
                <div className="flex items-start gap-2">
                  <SevChip severity={e.severity} />
                  <span className="text-[11px] font-mono text-cc-text leading-tight flex-1">
                    {summary.narrative}
                  </span>
                  <button
                    onClick={() => store.selectEvent(e.id)}
                    className="text-[9px] font-mono text-cc-blue hover:underline shrink-0"
                  >
                    {isSelected ? 'selected' : 'inspect →'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
