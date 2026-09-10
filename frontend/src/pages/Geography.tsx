// Geography — the full map experience + geo sector CRUD + camera
// placement (PUT /api/map/cameras/{id}/geo). Camera markers with
// status, event markers, sector polygons; click a camera to select.

import { useState } from 'react';
import { api } from '../api';
import GeoMap from '../components/GeoMap';
import GeoSectors from '../components/GeoSectors';
import CameraStatus from '../components/CameraStatus';
import EventTimeline from '../components/EventTimeline';
import { EmptyState, Panel, Pill } from '../components/ui';
import type { Store } from '../store';

export default function Geography({ store }: { store: Store }) {
  const { cameras, selectedCamera } = store;
  const sel = cameras.find(c => c.camera_id === selectedCamera) ?? null;
  const [lat, setLat] = useState('');
  const [lng, setLng] = useState('');
  const [label, setLabel] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const place = async () => {
    if (!sel) return;
    setBusy(true); setErr(null);
    try {
      await api.setCameraGeo(sel.camera_id, Number(lat), Number(lng), label);
      await store.refreshGeo();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally { setBusy(false); }
  };

  return (
    <div className="h-full min-h-0 grid grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] gap-1.5">
      {/* map */}
      <div className="grid grid-rows-[minmax(0,1.5fr)_minmax(0,1fr)] gap-1.5 min-h-0">
        <GeoMap store={store} />
        <Panel title="Geo Sector Management" scroll className="min-h-0">
          <GeoSectors store={store} />
        </Panel>
      </div>
      {/* right: selected-camera info card + placement + registry + events */}
      <div className="grid grid-rows-[auto_auto_minmax(0,1fr)_minmax(0,1fr)] gap-1.5 min-h-0">
        {/* T2.4: marker-click info card — the selected camera's real
            metadata, pinned next to the map */}
        <Panel
          title="Selected Camera"
          right={sel
            ? (sel.status === 'live'
                ? <Pill tone="green">LIVE</Pill>
                : <Pill tone="dim">{sel.status.toUpperCase()}</Pill>)
            : <Pill tone="dim">none</Pill>}
          className="min-h-0 shrink-0"
        >
          {!sel ? (
            <div className="px-3 py-2.5 text-[10px] font-mono text-cc-dim">
              click a map marker (or a registry row) to inspect a camera
            </div>
          ) : (
            <div className="p-2 grid grid-cols-2 gap-x-3 gap-y-1 text-[10px] font-mono">
              <Info k="Name" v={sel.label || '—'} />
              <Info k="Camera ID" v={sel.camera_id} />
              <Info k="Status" v={sel.status.toUpperCase()} tone={sel.status === 'live' ? 'green' : undefined} />
              <Info k="Type" v={sel.type ?? '—'} />
              <Info k="Latitude" v={sel.has_coordinates ? sel.latitude!.toFixed(5) : '—'} />
              <Info k="Longitude" v={sel.has_coordinates ? sel.longitude!.toFixed(5) : '—'} />
            </div>
          )}
        </Panel>
        <Panel
          title="Camera Placement"
          right={sel
            ? <Pill tone="blue">{sel.camera_id}</Pill>
            : <Pill tone="dim">no camera selected</Pill>}
          className="min-h-0 shrink-0"
        >
          <div className="p-2 space-y-1.5">
            {!sel ? (
              <EmptyState>select a camera in the registry below</EmptyState>
            ) : (
              <>
                <div className="text-[10px] font-mono text-cc-dim">
                  {sel.has_coordinates
                    ? `placed at ${sel.latitude!.toFixed(5)}, ${sel.longitude!.toFixed(5)}`
                    : 'unplaced — coordinates never set (NULL in DB)'}
                </div>
                <div className="flex gap-1.5">
                  <input
                    value={lat} onChange={e => setLat(e.target.value)}
                    placeholder="latitude"
                    className="w-1/3 bg-cc-bg border border-cc-line rounded px-2 py-1 text-[10px] font-mono"
                  />
                  <input
                    value={lng} onChange={e => setLng(e.target.value)}
                    placeholder="longitude"
                    className="w-1/3 bg-cc-bg border border-cc-line rounded px-2 py-1 text-[10px] font-mono"
                  />
                  <input
                    value={label} onChange={e => setLabel(e.target.value)}
                    placeholder="label"
                    className="w-1/3 bg-cc-bg border border-cc-line rounded px-2 py-1 text-[10px] font-mono"
                  />
                </div>
                <button
                  disabled={busy || !lat || !lng}
                  onClick={() => void place()}
                  className="w-full text-[10px] font-mono px-2 py-1 border border-cc-blue/60 text-cc-blue rounded-sm hover:bg-cc-blue/10 disabled:opacity-40"
                >
                  {busy ? 'SAVING…' : 'SET COORDINATES (PUT /api/map/cameras/{id}/geo)'}
                </button>
                {err && (
                  <div className="text-[10px] font-mono text-cc-red">{err}</div>
                )}
              </>
            )}
          </div>
        </Panel>
        <CameraStatus store={store} />
        <EventTimeline store={store} limit={30} />
      </div>
    </div>
  );
}

function Info({ k, v, tone }: { k: string; v: string; tone?: 'green' }) {
  return (
    <div className="min-w-0">
      <div className="text-[8px] uppercase tracking-wider text-cc-dim">{k}</div>
      <div className={`truncate ${tone === 'green' ? 'text-cc-accent' : 'text-cc-text'}`}
        title={v}>{v}</div>
    </div>
  );
}
