// Sources — the operator's source registry: upload workflow, USB
// selection, real per-source rows (DB), future RTSP shown honestly as
// not available in this build.

import { useEffect, useState } from 'react';
import { api } from '../api';
import CameraStatus from '../components/CameraStatus';
import SourcePicker from '../components/SourcePicker';
import { EmptyState, Panel, Pill, StatusDot } from '../components/ui';
import type { Store } from '../store';
import type { SourceRow } from '../types';

export default function Sources({ store }: { store: Store }) {
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const refresh = () => {
    api.sources().then(r => setSources(r.sources)).catch(e => setErr(String(e)));
  };
  useEffect(refresh, [store.status.active, store.events.length]);

  return (
    <div className="h-full min-h-0 grid grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)] gap-1.5">
      <SourcePicker store={store} />

      {/* registry */}
      <Panel
        title="Source Registry — DB rows"
        right={<Pill tone="dim">{sources.length} registered</Pill>}
        scroll
        className="min-h-0"
      >
        {err && <div className="text-[10px] font-mono text-cc-red px-2 pt-2">{err}</div>}
        {sources.length === 0
          ? <EmptyState>no sources registered — rows are created at session start</EmptyState>
          : <table className="w-full text-[11px] font-mono">
              <thead className="sticky top-0 bg-cc-panel text-cc-dim text-[9px] uppercase tracking-wider">
                <tr className="border-b border-cc-line">
                  <th className="text-left px-2.5 py-1.5">ID</th>
                  <th className="text-left px-2.5 py-1.5">Type</th>
                  <th className="text-left px-2.5 py-1.5">Status</th>
                  <th className="text-left px-2.5 py-1.5">Registered</th>
                </tr>
              </thead>
              <tbody>
                {sources.map(s => (
                  <tr key={s.id} className="border-b border-cc-line/40 hover:bg-cc-panel2/40">
                    <td className="px-2.5 py-1.5">
                      <span className="flex items-center gap-1.5">
                        <StatusDot ok={s.live} warn={!s.live} title={s.live ? 'live session' : 'not active'} />
                        <span className="truncate max-w-52">{s.id}</span>
                      </span>
                    </td>
                    <td className="px-2.5 py-1.5 text-cc-dim">{s.type}</td>
                    <td className="px-2.5 py-1.5">
                      <span className={s.live ? 'text-cc-accent' : 'text-cc-dim'}>
                        {s.live ? 'LIVE' : s.status}
                      </span>
                    </td>
                    <td className="px-2.5 py-1.5 text-cc-dim">{s.created_at?.slice(0, 16).replace('T', ' ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>}
      </Panel>

      {/* future capability — honest */}
      <div className="grid grid-rows-[auto_auto_minmax(0,1fr)] gap-1.5 min-h-0">
        <Panel title="RTSP / Network Cameras" className="shrink-0">
          <div className="px-3 py-3 text-[11px] font-mono text-cc-dim">
            <span className="text-cc-amber">NOT AVAILABLE</span> in this build —
            the sources abstraction (VideoSource) supports the contract, but no
            RTSP source is implemented. No fake streams will be shown.
          </div>
        </Panel>
        <CameraStatus store={store} />
        <Panel title="Uploads" scroll className="min-h-0">
          <div className="px-3 py-2 text-[10px] font-mono text-cc-dim">
            Uploads land in <span className="text-cc-text">uploads/</span> (probe-validated
            by the same FileSource a session opens). Start analysis from the
            Input Source panel after upload.
          </div>
        </Panel>
      </div>
    </div>
  );
}
