// Command Center — PRIMARY: live camera feed; RAIL: live alerts (SSE);
// SECONDARY: alerts summary from real events; slot for the P1
// AI/EVENT SUMMARY. Every value is REAL backend state; zero-when-zero.

import EventDetail from '../components/EventDetail';
import EventTimeline from '../components/EventTimeline';
import LiveFeed from '../components/LiveFeed';
import { Metric, Panel, Pill, SevChip } from '../components/ui';
import type { Store } from '../store';

export default function Dashboard({ store }: { store: Store }) {
  const { events, health } = store;

  // summary cards — all real state, zero-when-zero
  // people/vehicles: interim event-derived counts (per plan T0.5; the
  // P1 T1.2 change replaces these with session-level truth)
  let people = 0, vehicles = 0;
  for (const e of events) {
    if (e.type === 'PERSON_DETECTED') people += 1;
    else if (e.type === 'VEHICLE_DETECTED') vehicles += 1;
  }
  const activeAlerts = events.filter(e => e.status === 'new').length;
  const systemOnline = !!health?.ok;

  // alerts summary — severity counts over the loaded real event window
  const sev = { INFO: 0, LOW: 0, MEDIUM: 0, HIGH: 0 } as Record<string, number>;
  for (const e of events) sev[e.severity] = (sev[e.severity] ?? 0) + 1;

  return (
    <div className="h-full min-h-0 flex flex-col gap-2">
      {/* ── 4 summary cards ── */}
      <div className="grid grid-cols-4 gap-2 shrink-0">
        <Metric label="People Detected" value={people} dim={people === 0} />
        <Metric label="Vehicles Detected" value={vehicles} dim={vehicles === 0} />
        <Metric label="Active Alerts" value={activeAlerts} warn={activeAlerts > 0} />
        <div className="bg-cc-panel2 border border-cc-line rounded-lg px-2.5 py-1.5 min-w-0">
          <div className="text-[9px] uppercase tracking-wider text-cc-dim truncate">System Status</div>
          <div className={`font-mono text-lg leading-tight truncate flex items-center gap-2 ${systemOnline ? 'text-cc-accent' : 'text-cc-red'}`}>
            <span className={`inline-block w-2 h-2 rounded-full ${systemOnline ? 'bg-cc-accent' : 'bg-cc-red animate-pulse'}`} />
            {systemOnline ? 'ONLINE' : health ? 'OFFLINE' : 'CONNECTING'}
            <span className="text-[10px] text-cc-dim ml-auto font-normal">
              {health ? `up ${health.uptime_s}s` : ''}
            </span>
          </div>
        </div>
      </div>

      {/* ── main: live camera + alerts rail ── */}
      <div className="flex-1 min-h-0 grid grid-cols-[minmax(0,2.2fr)_minmax(0,1fr)_320px] gap-2">
        <LiveFeed store={store} compact />
        <EventTimeline store={store} />
        <div className="min-h-0 flex flex-col gap-2">
          <EventDetail store={store} />
        </div>
      </div>

      {/* ── below: alerts summary + AI/event summary slot ── */}
      <div className="shrink-0 grid grid-cols-2 gap-2" style={{ minHeight: 84 }}>
        <Panel
          title="Alerts Summary"
          right={<Pill tone="dim">{events.length} events loaded</Pill>}
        >
          <div className="p-2 grid grid-cols-4 gap-1.5">
            {(['HIGH', 'MEDIUM', 'LOW', 'INFO'] as const).map(k => (
              <div key={k} className="flex items-center gap-2">
                <SevChip severity={k} />
                <span className={`font-mono text-base ${k === 'HIGH' && sev[k] > 0 ? 'text-cc-red font-semibold' : 'text-cc-text'}`}>
                  {sev[k] ?? 0}
                </span>
              </div>
            ))}
            {events.length === 0 && (
              <div className="col-span-4 text-[10px] font-mono text-cc-dim">
                no alerts yet — start a session to generate real events
              </div>
            )}
          </div>
        </Panel>
        <Panel title="AI / Event Summary" right={<Pill tone="amber">P1 — DETERMINISTIC, NO LLM</Pill>}>
          <div className="p-2 text-[10px] font-mono text-cc-dim leading-relaxed">
            Field-faithful event narrative lands in Phase 1 (deterministic
            template over real EventRow fields — no invented facts, no LLM).
          </div>
        </Panel>
      </div>
    </div>
  );
}
