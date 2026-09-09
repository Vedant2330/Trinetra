// Cameras — the full live view for the active camera plus the real
// registry grid. ONE active session at a time (frozen §17): the grid
// shows every registered camera with honest live/idle/error state;
// the big feed shows the LIVE session's annotated stream.

import CameraStatus from '../components/CameraStatus';
import LiveFeed from '../components/LiveFeed';
import SourcePicker from '../components/SourcePicker';
import { EmptyState, Panel, Pill, StatusDot } from '../components/ui';
import type { Store } from '../store';

export default function Cameras({ store }: { store: Store }) {
  const { cameras, status, selectedCamera } = store;
  const s = status.session;

  return (
    <div className="h-full min-h-0 grid grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-1.5">
      <div className="grid grid-rows-[minmax(0,1.35fr)_minmax(0,1fr)] gap-1.5 min-h-0">
        <LiveFeed store={store} />
        {/* camera grid — one tile per REAL source row */}
        <Panel
          title="Camera Grid — registered sources"
          right={<Pill tone="dim">{cameras.length} total</Pill>}
          scroll
          className="min-h-0"
        >
          {cameras.length === 0
            ? <EmptyState>no cameras registered — a source row is created when a session starts</EmptyState>
            : <div className="grid grid-cols-2 lg:grid-cols-3 gap-1.5 p-1.5">
                {cameras.map(c => {
                  const live = c.status === 'live';
                  const sel = selectedCamera === c.camera_id;
                  return (
                    <button
                      key={c.camera_id}
                      onClick={() => store.selectCamera(sel ? null : c.camera_id)}
                      className={`border rounded p-2 text-left transition-colors ${
                        sel ? 'border-cc-blue bg-cc-panel2' : 'border-cc-line hover:bg-cc-panel2/60'
                      }`}
                    >
                      <div className="flex items-center gap-1.5 mb-1">
                        <StatusDot ok={live} warn={c.status === 'idle'} title={c.status} />
                        <span className="text-[11px] font-mono truncate">{c.camera_id}</span>
                        <span className={`ml-auto text-[9px] font-mono uppercase ${live ? 'text-cc-accent'
                          : c.status === 'error' ? 'text-cc-red' : 'text-cc-dim'}`}>
                          {c.status}
                        </span>
                      </div>
                      {/* live tile shows the real feed when this is the session source */}
                      <div className="bg-black rounded border border-cc-line/60 aspect-video flex items-center justify-center overflow-hidden">
                        {live && s && s.source_id === c.camera_id ? (
                          <img
                            src={`/api/frame.jpg?_=${store.clock.getTime()}`}
                            alt="latest annotated frame"
                            className="max-w-full max-h-full object-contain"
                          />
                        ) : (
                          <span className="text-[9px] font-mono text-cc-dim">
                            {c.status === 'error' ? 'ERROR' : 'IDLE'}
                          </span>
                        )}
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-[9px] font-mono text-cc-dim">
                        <span className="truncate">{c.label}</span>
                        <span className="ml-auto shrink-0">{c.type ?? '—'}</span>
                        <span className="shrink-0">
                          {c.has_coordinates ? 'placed' : 'unplaced'}
                        </span>
                      </div>
                      {live && s && s.source_id === c.camera_id && (
                        <div className="mt-0.5 text-[9px] font-mono text-cc-accent">
                          {s.active_tracks} tracks · {s.pipeline_fps.toFixed(1)}fps
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>}
        </Panel>
      </div>
      <div className="grid grid-rows-[auto_minmax(0,1fr)] gap-1.5 min-h-0">
        <SourcePicker store={store} />
        <CameraStatus store={store} />
      </div>
    </div>
  );
}
