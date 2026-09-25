// TRINETRA Command Center V2 — persistent app shell.
// Top bar (identity/status/clock) · left nav (8 working pages) ·
// primary workspace · bottom status bar (pipeline health chain).
// Every rendered value is REAL backend state; no decorative data.

import { useEffect, useState } from 'react';
import Analytics from './pages/Analytics';
import Cameras from './pages/Cameras';
import Dashboard from './pages/Dashboard';
import EventLog from './pages/EventLog';
import Events from './pages/Events';
import Geography from './pages/Geography';
import Investigation from './pages/Investigation';
import Settings from './pages/Settings';
import Sources from './pages/Sources';
import { StatusDot, Pill } from './components/ui';
import { useStore, type Page } from './store';

const NAV: { id: Page; label: string; glyph: string }[] = [
  { id: 'dashboard', label: 'Command Center', glyph: '▦' },
  { id: 'cameras', label: 'Live View', glyph: '◎' },
  { id: 'events', label: 'Alerts', glyph: '⚡' },
  { id: 'eventlog', label: 'Event Log', glyph: '≡' },
  { id: 'investigation', label: 'Investigation', glyph: '⌕' },
  { id: 'geography', label: 'Map', glyph: '⌖' },
  { id: 'analytics', label: 'Analytics', glyph: '∿' },
  { id: 'sources', label: 'Cameras', glyph: '⬒' },
  { id: 'settings', label: 'Settings', glyph: '⚙' },
];

export default function App() {
  const store = useStore();
  const { health, sseState, status, clock } = store;
  const unacked = store.events.filter(e => e.status === 'new').length;
  const high = store.events.filter(
    e => e.status === 'new' && e.severity === 'HIGH').length;
  const [flash, setFlash] = useState<string | null>(null);

  // transient high-alert flash in the top bar (real events only)
  useEffect(() => {
    if (high > 0) setFlash(`${high} HIGH SEVERITY UNACKED — ATTENTION REQUIRED`);
    else setFlash(null);
  }, [high]);

  const Page = {
    dashboard: Dashboard, cameras: Cameras, events: Events,
    eventlog: EventLog, investigation: Investigation, geography: Geography,
    analytics: Analytics, sources: Sources, settings: Settings,
  }[store.page];

  const sessionSrc = status.session?.source_id ?? null;
  const sessionSt = status.session?.status ?? null;

  return (
    <div className="h-screen w-screen flex flex-col bg-cc-bg text-cc-text overflow-hidden">
      {/* ── top bar ── */}
      <header className="flex items-center gap-3 px-4 h-11 border-b border-cc-line bg-cc-panel shrink-0">
        <span className="font-mono font-bold tracking-[0.2em] text-[13px] text-cc-text">
          TRINETRA
        </span>
        <span className="text-[10px] font-mono text-cc-dim tracking-wide hidden md:inline">
          Intelligent Border Video Analytics Platform
        </span>
        <span
          className={`text-[10px] font-mono font-bold px-1.5 py-0.5 border rounded-sm uppercase tracking-wide ${
            health
              ? health.ok
                ? 'text-cc-accent border-cc-accent/40 bg-cc-accent/5'
                : 'text-cc-red border-cc-red/40 bg-cc-red/5'
              : 'text-cc-dim border-cc-line'
          }`}
          title={health?.ok ? 'backend healthy' : health ? 'backend degraded' : 'backend unreachable'}
        >
          {health ? (health.ok ? 'SYSTEM ONLINE' : 'SYSTEM OFFLINE') : 'CONNECTING'}
        </span>
        <Pill tone={sseState === 'open' ? 'green' : 'amber'}>SSE {sseState.toUpperCase()}</Pill>
        {status.active && sessionSt && (
          <Pill tone={sessionSt === 'running' ? 'green' : sessionSt === 'error' ? 'red' : 'amber'}>
            SESSION {sessionSt.toUpperCase()} · {sessionSrc}
          </Pill>
        )}
        {flash && (
          <span className="text-cc-red text-[10px] font-mono font-bold animate-pulse">
            ⚠ {flash}
          </span>
        )}
        <span className="ml-auto flex items-center gap-3 text-[10px] font-mono text-cc-dim">
          {unacked > 0 && <span className="text-cc-amber">{unacked} UNACKED</span>}
          <span>{clock.toLocaleTimeString()}</span>
          <span className="text-cc-dim/60">{clock.toLocaleDateString()}</span>
        </span>
      </header>

      {/* ── shell: nav + workspace ── */}
      <div className="flex flex-1 min-h-0">
        <nav className="w-44 lg:w-44 max-lg:w-12 border-r border-cc-line bg-cc-panel flex flex-col shrink-0">
          <div className="flex-1 py-2">
            {NAV.map(n => (
              <button
                key={n.id}
                onClick={() => store.setPage(n.id)}
                title={n.label}
                className={`w-full text-left px-4 max-lg:px-0 max-lg:text-center max-lg:justify-center py-2.5 text-[12px] flex items-center gap-3 border-l-2 transition-colors ${
                  store.page === n.id
                    ? 'border-cc-accent text-cc-text bg-cc-panel2 font-semibold'
                    : 'border-transparent text-cc-dim hover:text-cc-text hover:bg-cc-panel2/60'
                }`}
              >
                <span className="text-cc-accent/80 font-mono">{n.glyph}</span>
                <span className="max-lg:hidden">{n.label}</span>
                {n.id === 'events' && unacked > 0 && (
                  <span className="ml-auto max-lg:hidden text-cc-amber text-[10px] font-mono">{unacked}</span>
                )}
              </button>
            ))}
          </div>
          {/* AI assistant status — honest NOT CONNECTED until Hermes wiring exists */}
          <div className="border-t border-cc-line px-4 max-lg:px-0 max-lg:text-center py-3">
            <div className="text-[9px] uppercase tracking-wider text-cc-dim mb-1 max-lg:hidden">AI Assistant</div>
            <div className="max-lg:hidden">
              <Pill tone="amber" title="Hermes assistant not connected in this build">HERMES — NOT CONNECTED</Pill>
            </div>
            <span className="lg:hidden text-[9px] font-mono text-cc-dim" title="Hermes assistant not connected in this build">✦</span>
          </div>
        </nav>

        <main className="flex-1 min-w-0 min-h-0 p-2 overflow-hidden">
          <Page store={store} />
        </main>
      </div>

      {/* ── bottom status bar: pipeline health chain ── */}
      <footer className="flex items-center gap-5 px-4 h-7 border-t border-cc-line bg-cc-panel text-[10px] font-mono text-cc-dim shrink-0">
        <span className="flex items-center gap-1.5">
          <StatusDot ok={!!health?.models?.detector?.present}
            title={health?.models?.detector?.present
              ? `YOLOv8n ${health.models.detector.size_mb}MB`
              : 'detector weights missing'} />
          DETECTOR {health?.models?.detector?.present ? 'YOLOV8N READY' : 'MISSING'}
        </span>
        <span className="flex items-center gap-1.5">
          <StatusDot ok={true} title="ByteTrack (per-session state)" />
          TRACKER BYTETRACK
        </span>
        <span className="flex items-center gap-1.5">
          <StatusDot ok={true} warn={!status.active} title="processing loop state" />
          PIPELINE {status.active ? (status.session!.status === 'running' ? 'RUNNING' : status.session!.status.toUpperCase()) : 'STOPPED'}
        </span>
        {status.active && (
          <span className="text-cc-dim">
            DEV {status.session!.device} · {status.session!.frames_processed}f · {status.session!.pipeline_fps.toFixed(1)}fps · {status.session!.active_tracks} tracks
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <StatusDot ok={!!health?.db?.ok} title="SQLite WAL" />
          DB {health?.db?.ok ? 'OK' : 'ERROR'}
        </span>
        <span className="flex items-center gap-1.5">
          <StatusDot ok={health?.writer?.writer === 'running'}
            warn={health?.writer?.writer !== 'running' && health?.writer?.writer !== 'stopped'}
            title={JSON.stringify(health?.writer ?? {})} />
          WRITER {String(health?.writer?.writer ?? 'stopped').toUpperCase()}
        </span>
        <span className="ml-auto text-cc-dim/60">
          {health ? `up ${health.uptime_s}s · ${health.app} ${health.phase}` : ''}
        </span>
      </footer>
    </div>
  );
}
