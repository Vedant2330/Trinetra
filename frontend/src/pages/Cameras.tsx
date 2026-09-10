// Live View — to V3 spec: source UX (webcam scan / file upload with
// real progress / start / stop), the big LIVE feed, a REAL stats
// strip (status_payload session fields — people/vehicles/frames/fps/
// device), and the working Analytics-Layers toggle bar (server-side
// render layers, C2). Plus the honest registry grid.

import CameraStatus from '../components/CameraStatus';
import LayerToggles from '../components/LayerToggles';
import LiveFeed from '../components/LiveFeed';
import SourcePicker from '../components/SourcePicker';
import { ComingSoon } from '../components/ui';
import { EmptyState, Panel, Pill, StatusDot } from '../components/ui';
import type { Store } from '../store';

export default function Cameras({ store }: { store: Store }) {
  const { cameras, status, selectedCamera } = store;
  const s = status.session;

  return (
    <div className="h-full min-h-0 grid grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-2">
      <div className="grid grid-rows-[auto_minmax(0,1.6fr)_minmax(0,1fr)] gap-2 min-h-0">
        {/* REAL stats strip — every number from status_payload */}
        <Panel title="Session Stats" className="min-h-0">
          <div className="grid grid-cols-7 gap-1.5 p-2">
            <Stat label="People" value={s ? String(s.people_detected) : '—'} live={!!s && s.people_detected > 0} />
            <Stat label="Vehicles" value={s ? String(s.vehicles_detected) : '—'} live={!!s && s.vehicles_detected > 0} />
            <Stat label="Active Tracks" value={s ? String(s.active_tracks) : '—'} />
            <Stat label="Frames" value={s ? String(s.frames_processed) : '—'} />
            <Stat label="Pipeline FPS" value={s ? s.pipeline_fps.toFixed(1) : '—'} />
            <Stat label="Device" value={s ? s.device.toUpperCase() : '—'} />
            <Stat label="Uptime" value={s ? `${Math.round(s.uptime_s)}s` : '—'} />
          </div>
        </Panel>

        <LiveFeed store={store} />

        {/* analytics layers — VERIFIABLY change the rendered stream */}
        <Panel
          title="Analytics Layers"
          right={<Pill tone="dim">server-side render layers</Pill>}
          className="min-h-0"
        >
          <div className="p-2 flex flex-wrap gap-2 items-center">
            <LayerToggles store={store} />
            {/* honest roadmap — every item disabled + labeled */}
            <span className="text-[9px] font-mono text-cc-dim/70 ml-1">roadmap — not in this build:</span>
            <ComingSoon label="Pose Estimation" />
            <ComingSoon label="Thermal Fusion" />
            <ComingSoon label="Advanced Behavior" />
          </div>
        </Panel>
      </div>

      <div className="grid grid-rows-[auto_auto_minmax(0,1fr)] gap-2 min-h-0">
        <SourcePicker store={store} />
        <CameraStatus store={store} />

        {/* camera grid — one tile per REAL source row */}
        <Panel
          title="Camera Grid — registered sources"
          right={<Pill tone="dim">{cameras.length} total</Pill>}
          scroll
          className="min-h-0"
        >
          {cameras.length === 0
            ? <EmptyState>no cameras registered — a source row is created when a session starts</EmptyState>
            : <div className="grid grid-cols-2 gap-1.5 p-1.5">
                {cameras.map(c => {
                  const live = c.status === 'live';
                  const sel = selectedCamera === c.camera_id;
                  return (
                    <button
                      key={c.camera_id}
                      onClick={() => store.selectCamera(sel ? null : c.camera_id)}
                      className={`border rounded-lg p-2 text-left transition-colors ${
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
    </div>
  );
}

function Stat({ label, value, live }: { label: string; value: string; live?: boolean }) {
  return (
    <div className="bg-cc-panel2 border border-cc-line rounded-lg px-2 py-1.5 min-w-0">
      <div className="text-[9px] uppercase tracking-wider text-cc-dim truncate">{label}</div>
      <div className={`font-mono text-base leading-tight truncate ${live ? 'text-cc-blue font-semibold' : 'text-cc-text'}`}>
        {value}
      </div>
    </div>
  );
}
