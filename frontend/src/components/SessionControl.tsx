// SessionControl — real session lifecycle: start (file/webcam), stop,
// and every metric from status_payload(). PAUSE/RESTART are NOT backend
// capabilities → honestly shown as unavailable (V2 dispatch §11).

import { useState } from 'react';
import { api } from '../api';
import type { Store } from '../store';
import { Metric, Panel, Pill, StatusDot } from './ui';

export default function SessionControl({ store }: { store: Store }) {
  const { status } = store;
  const s = status.session;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const stop = async () => {
    setBusy(true); setErr(null);
    try { await api.sessionStop(); } catch (e) { setErr(String(e)); }
    finally { setBusy(false); void store.refreshAll(); }
  };

  return (
    <Panel
      title="Session Control"
      right={
        <div className="flex items-center gap-2">
          {s && <Pill tone={s.status === 'running' ? 'green'
            : s.status === 'error' ? 'red' : 'amber'}>{s.status.toUpperCase()}</Pill>}
          {status.active && (
            <button
              disabled={busy}
              onClick={() => void stop()}
              className="text-[10px] font-mono px-2 py-0.5 border border-cc-red/60 text-cc-red rounded-sm hover:bg-cc-red/10 disabled:opacity-50"
            >
              STOP
            </button>
          )}
        </div>
      }
      className="min-h-0 shrink-0"
    >
      <div className="p-2 space-y-2">
        {status.active && s ? (
          <>
            <div className="flex items-center gap-2 text-[11px] font-mono">
              <StatusDot ok={s.status === 'running'} warn={s.status !== 'running'} title={s.status} />
              <span className="text-cc-text truncate">{s.source_id}</span>
              <span className="text-cc-dim ml-auto">{s.uptime_s}s</span>
            </div>
            <div className="grid grid-cols-4 gap-1.5">
              <Metric label="Frames" value={s.frames_processed} />
              <Metric label="FPS" value={s.pipeline_fps.toFixed(1)} />
              <Metric label="Tracks" value={`${s.active_tracks}/${s.total_tracks}`} />
              <Metric label="Events" value={s.events_committed} />
            </div>
            <div className="flex gap-1.5 items-center">
              <button disabled className="text-[10px] font-mono px-2 py-0.5 border border-cc-line text-cc-dim/50 rounded-sm cursor-not-allowed">
                PAUSE — NOT SUPPORTED
              </button>
              <button disabled className="text-[10px] font-mono px-2 py-0.5 border border-cc-line text-cc-dim/50 rounded-sm cursor-not-allowed">
                RESTART — NOT SUPPORTED
              </button>
            </div>
            {s.error && (
              <div className="text-[10px] font-mono text-cc-red bg-cc-red/5 border border-cc-red/30 rounded px-2 py-1">
                {s.error}
              </div>
            )}
          </>
        ) : (
          <div className="text-[11px] font-mono text-cc-dim px-1 py-3 text-center">
            no active session — pick a source on the Sources page
          </div>
        )}
        {err && <div className="text-[10px] font-mono text-cc-red">{err}</div>}
      </div>
    </Panel>
  );
}
