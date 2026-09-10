// LayerToggles — the V3 render-layer control bar. Every toggle hits
// POST /api/session/layers and changes the REAL rendered MJPEG/evidence
// (server-side renderer, C2). Disabled with a reason when no session —
// no dead controls. Shared by Live View + Analytics.

import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Store } from '../store';

export interface LayerState {
  boxes: boolean;
  labels: boolean;
  fps: boolean;
  trajectories: boolean;
  zones: boolean;
  faces: boolean;
}

const DEFAULTS: LayerState = {
  boxes: true, labels: true, fps: true, trajectories: false, zones: true, faces: false,
};

const LAYERS: { key: keyof LayerState; label: string; hint: string }[] = [
  { key: 'boxes', label: 'Detections',
    hint: 'bounding boxes + class/conf chips' },
  { key: 'labels', label: 'Track IDs', hint: 'the "| ID n" suffix' },
  { key: 'trajectories', label: 'Trajectories',
    hint: 'foot-point history polylines (60 pts/track)' },
  { key: 'zones', label: 'Virtual Fence', hint: 'zones burned into stream + evidence' },
  { key: 'faces', label: 'Faces', hint: 'YuNet face detection + landmark overlay' },
  { key: 'fps', label: 'FPS', hint: 'pipeline HUD text' },
];

export default function LayerToggles({ store }: { store: Store }) {
  const active = store.status.active;
  const [layers, setLayers] = useState<LayerState>(DEFAULTS);
  const [err, setErr] = useState<string | null>(null);

  // refresh current state on session start/stop (defaults on new session)
  useEffect(() => {
    if (!active) { setLayers(DEFAULTS); setErr(null); return; }
    api.sessionLayersGet()
      .then(r => setLayers({ ...DEFAULTS, ...r.layers }))
      .catch(() => setLayers(DEFAULTS));
  }, [active, store.status.session?.source_id]);

  if (!active) {
    return (
      <div className="flex flex-wrap gap-1.5 items-center opacity-60">
        {LAYERS.map(l => (
          <span key={l.key}
            title={`${l.label} (${l.hint}) — no active session`}
            className="text-[10px] font-mono px-1.5 py-0.5 border border-dashed border-cc-line rounded text-cc-dim bg-cc-panel2/50 select-none cursor-not-allowed">
            {l.label}
          </span>
        ))}
        <span className="text-[9px] font-mono text-cc-dim ml-1">
          — no active session
        </span>
      </div>
    );
  }

  const flip = async (key: keyof LayerState) => {
    setErr(null);
    try {
      const r = await api.sessionLayersPost({ [key]: !layers[key] });
      setLayers({ ...DEFAULTS, ...r.layers });
    } catch (e) {
      setErr(String(e));   // honest failure surface (e.g. session just ended)
    }
  };

  return (
    <div className="flex flex-wrap gap-1.5 items-center">
      {LAYERS.map(l => (
        <button key={l.key}
          onClick={() => void flip(l.key)}
          title={`${l.label} — ${l.hint}`}
          className={`text-[10px] font-mono px-1.5 py-0.5 border rounded transition-colors ${
            layers[l.key]
              ? 'border-cc-blue/50 bg-cc-blue/10 text-cc-blue font-semibold'
              : 'border-cc-line bg-cc-panel2 text-cc-dim hover:text-cc-text'
          }`}>
          {l.label}
        </button>
      ))}
      {err && <span className="text-[9px] font-mono text-cc-red truncate" title={err}>toggle failed</span>}
    </div>
  );
}
