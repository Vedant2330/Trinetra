// CameraStatus — the REAL camera registry (DB source rows + live flag).
// One camera per real source row; the map geo join shows placement.

import type { Store } from '../store';
import { EmptyState, Panel, StatusDot } from './ui';

export default function CameraStatus({ store, limit }: { store: Store; limit?: number }) {
  const { cameras, selectedCamera, selectCamera } = store;
  const list = limit ? cameras.slice(0, limit) : cameras;
  return (
    <Panel title="Cameras" scroll className="min-h-0">
      {cameras.length === 0
        ? <EmptyState>no sources registered — start a session to create one</EmptyState>
        : list.map(c => (
          <button
            key={c.camera_id}
            onClick={() => selectCamera(selectedCamera === c.camera_id ? null : c.camera_id)}
            className={`w-full flex items-center gap-2 px-2.5 py-2 border-b border-cc-line/50 text-left hover:bg-cc-panel2/60 ${
              selectedCamera === c.camera_id ? 'bg-cc-panel2' : ''
            }`}
          >
            <StatusDot
              ok={c.status === 'live'}
              warn={c.status === 'idle'}
              title={c.status}
            />
            <div className="min-w-0 flex-1">
              <div className="text-[11px] font-mono truncate">{c.camera_id}</div>
              <div className="text-[10px] text-cc-dim truncate">
                {c.label} · {c.type ?? '—'}
              </div>
            </div>
            <div className="text-right shrink-0">
              <div className={`text-[9px] font-mono uppercase ${c.status === 'live' ? 'text-cc-accent'
                : c.status === 'error' ? 'text-cc-red' : 'text-cc-dim'}`}>
                {c.status}
              </div>
              <div className="text-[9px] font-mono text-cc-dim">
                {c.has_coordinates ? `${c.latitude!.toFixed(3)},${c.longitude!.toFixed(3)}` : 'unplaced'}
              </div>
            </div>
          </button>
        ))}
    </Panel>
  );
}
