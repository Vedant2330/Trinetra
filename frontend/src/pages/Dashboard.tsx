// Command Center — PRIMARY: live camera feed; RAIL: live alerts (SSE);
// SECONDARY: alerts summary from real events; slot for the P1
// AI/EVENT SUMMARY. Every value is REAL backend state; zero-when-zero.
//
// Layout (DESIGN_SPEC §1): metrics row → live feed + alerts rail →
// alerts summary + AI/event summary. Density-first, no decorative cards.

import EventDetail from '../components/EventDetail';
import EventSummary from '../components/EventSummary';
import EventTimeline from '../components/EventTimeline';
import LiveFeed from '../components/LiveFeed';
import { Metric, Panel, Pill, SevChip, StatusDot } from '../components/ui';
import type { Store } from '../store';

export default function Dashboard({ store }: { store: Store }) {
  const { status, events, health } = store;
  const s = status.session;

  // summary cards — real session-level counts (V3 T1.2: status_payload
  // per-class fields, C5), zero when no session
  const people = s?.people_detected ?? 0;
  const vehicles = s?.vehicles_detected ?? 0;
  const activeAlerts = events.filter(e => e.status === 'new').length;
  const systemOnline = !!health?.ok;

  // alerts summary — severity counts over the loaded real event window
  const sev = { INFO: 0, LOW: 0, MEDIUM: 0, HIGH: 0 } as Record<string, number>;
  for (const e of events) sev[e.severity] = (sev[e.severity] ?? 0) + 1;

  return (
    <div className="h-full min-h-0 flex flex-col gap-2 animate-fade-in">
      {/* ── 4 summary cards ── */}
      <div className="grid grid-cols-4 gap-2 shrink-0">
        <Metric label="People Detected" value={people} unit="tracks" dim={people === 0} />
        <Metric label="Vehicles Detected" value={vehicles} unit="tracks" dim={vehicles === 0} />
        <Metric label="Active Alerts" value={activeAlerts} warn={activeAlerts > 0} />
        <div className="bg-cc-panel border border-cc-line rounded-lg px-2.5 py-1.5 min-w-0">
          <div className="text-[9px] uppercase tracking-wider text-cc-dim truncate">System Status</div>
          <div className={`font-mono text-lg leading-tight truncate flex items-center gap-2 ${systemOnline ? 'text-cc-accent' : 'text-cc-red'}`}>
            <StatusDot ok={systemOnline} title={systemOnline ? 'backend healthy' : health ? 'backend degraded' : 'backend unreachable'} />
            {systemOnline ? 'ONLINE' : health ? 'OFFLINE' : 'CONNECTING'}
            <span className="text-[10px] text-cc-dim ml-auto font-normal">
              {health ? `up ${health.uptime_s}s` : ''}
            </span>
          </div>
        </div>
      </div>

      {/* ── main: live camera + alerts rail + detail ── */}
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
        <Panel
          title="AI / Event Summary"
          right={<Pill tone="dim">deterministic · field-faithful · no LLM</Pill>}
          scroll
          className="min-h-0"
        >
          <EventSummary store={store} />
        </Panel>
      </div>
    </div>
  );
}