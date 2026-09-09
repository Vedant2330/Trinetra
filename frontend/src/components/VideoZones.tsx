// VideoZones — real M4 video-space zones (SQLite via /api/zones), with
// CRUD: create polygon/line (normalized coords), toggle active, delete.
// Geometry is validated server-side by the SAME validators the fence
// uses — the UI surfaces the backend's error message on 4xx.

import { useState } from 'react';
import { api } from '../api';
import type { Store } from '../store';
import type { ZoneRow } from '../types';
import { EmptyState, Panel, Pill } from './ui';

interface Draft {
  source_id: string;
  name: string;
  kind: 'polygon' | 'line';
  type: 'WATCH' | 'RESTRICTED';
  points: string;
  p1: string;
  p2: string;
  mode: 'both' | 'forward' | 'reverse';
}

export default function VideoZones({ store }: { store: Store }) {
  const { zones, cameras, status, refreshZones } = store;
  const sessionSource = status.session?.source_id ?? null;
  const [draft, setDraft] = useState<Draft>({
    source_id: sessionSource ?? cameras[0]?.camera_id ?? '',
    name: '', kind: 'polygon', type: 'RESTRICTED',
    points: '0.1,0.3 0.9,0.3 0.9,0.95 0.1,0.95',
    p1: '0.1,0.6', p2: '0.9,0.6', mode: 'both',
  });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async () => {
    setBusy(true); setErr(null);
    try {
      const geometry = draft.kind === 'polygon'
        ? { points: draft.points.trim().split(/\s+/).map(pair => {
            const [x, y] = pair.split(',').map(Number);
            return [x, y];
          }) }
        : { p1: draft.p1.split(',').map(Number),
            p2: draft.p2.split(',').map(Number),
            direction_mode: draft.mode };
      await api.createZone({
        source_id: draft.source_id, name: draft.name || 'zone',
        kind: draft.kind, type: draft.type, geometry,
      });
      await refreshZones();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally { setBusy(false); }
  };

  const toggle = async (z: ZoneRow) => {
    try {
      await api.updateZone(z.id, { active: !z.active });
      await refreshZones();
    } catch (e) { setErr(String((e as Error).message)); }
  };

  const del = async (z: ZoneRow) => {
    try {
      await api.deleteZone(z.id);
      await refreshZones();
    } catch (e) { setErr(String((e as Error).message)); }
  };

  return (
    <Panel title="Video Zones — per-camera" scroll className="min-h-0">
      <div className="p-2 space-y-2">
        {err && (
          <div className="text-[10px] font-mono text-cc-red bg-cc-red/5 border border-cc-red/30 rounded px-2 py-1">
            {err}
          </div>
        )}
        {/* create form */}
        <div className="border border-cc-line rounded p-2 space-y-1.5 bg-cc-panel2/50">
          <div className="text-[9px] uppercase tracking-wider text-cc-dim">New Zone (normalized 0–1 coords)</div>
          <div className="flex gap-1.5">
            <input
              value={draft.name}
              onChange={e => setDraft({ ...draft, name: e.target.value })}
              placeholder="name"
              className="flex-1 bg-cc-bg border border-cc-line rounded px-2 py-1 text-[11px] font-mono"
            />
            <select
              value={draft.source_id}
              onChange={e => setDraft({ ...draft, source_id: e.target.value })}
              className="bg-cc-bg border border-cc-line rounded px-1 py-1 text-[10px] font-mono max-w-40"
            >
              <option value="">camera…</option>
              {cameras.map(c => (
                <option key={c.camera_id} value={c.camera_id}>{c.camera_id}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-1.5">
            <select
              value={draft.kind}
              onChange={e => setDraft({ ...draft, kind: e.target.value as 'polygon' | 'line' })}
              className="bg-cc-bg border border-cc-line rounded px-1 py-1 text-[10px] font-mono"
            >
              <option value="polygon">polygon</option>
              <option value="line">tripwire</option>
            </select>
            <select
              value={draft.type}
              onChange={e => setDraft({ ...draft, type: e.target.value as 'WATCH' | 'RESTRICTED' })}
              className="bg-cc-bg border border-cc-line rounded px-1 py-1 text-[10px] font-mono"
            >
              <option value="RESTRICTED">RESTRICTED</option>
              <option value="WATCH">WATCH</option>
            </select>
            {draft.kind === 'line' && (
              <select
                value={draft.mode}
                onChange={e => setDraft({ ...draft, mode: e.target.value as Draft['mode'] })}
                className="bg-cc-bg border border-cc-line rounded px-1 py-1 text-[10px] font-mono"
              >
                <option value="both">both</option>
                <option value="forward">forward</option>
                <option value="reverse">reverse</option>
              </select>
            )}
            <button
              disabled={busy || !draft.source_id}
              onClick={() => void create()}
              className="ml-auto text-[10px] font-mono px-2 py-1 border border-cc-accent/60 text-cc-accent rounded-sm hover:bg-cc-accent/10 disabled:opacity-40"
            >
              CREATE
            </button>
          </div>
          {draft.kind === 'polygon'
            ? <input
                value={draft.points}
                onChange={e => setDraft({ ...draft, points: e.target.value })}
                className="w-full bg-cc-bg border border-cc-line rounded px-2 py-1 text-[10px] font-mono"
                placeholder="x,y x,y x,y (>= 3 points)"
              />
            : <div className="flex gap-1.5">
              <input
                value={draft.p1}
                onChange={e => setDraft({ ...draft, p1: e.target.value })}
                className="w-1/2 bg-cc-bg border border-cc-line rounded px-2 py-1 text-[10px] font-mono"
                placeholder="p1: x,y"
              />
              <input
                value={draft.p2}
                onChange={e => setDraft({ ...draft, p2: e.target.value })}
                className="w-1/2 bg-cc-bg border border-cc-line rounded px-2 py-1 text-[10px] font-mono"
                placeholder="p2: x,y"
              />
            </div>}
        </div>
        {/* zone list */}
        {zones.length === 0
          ? <EmptyState>no zones defined — create one above</EmptyState>
          : zones.map(z => (
            <div key={z.id} className="border border-cc-line rounded px-2.5 py-1.5 bg-cc-panel2/30">
              <div className="flex items-center gap-2">
                <span className={`text-[11px] font-mono ${z.zone_type === 'RESTRICTED' ? 'text-cc-red' : 'text-cc-blue'}`}>
                  {z.name || z.id.slice(0, 11)}
                </span>
                <Pill tone={z.zone_type === 'RESTRICTED' ? 'red' : 'blue'}>{z.zone_type}</Pill>
                <span className="text-[9px] text-cc-dim font-mono">{z.kind}</span>
                {z.source_id === sessionSource && <Pill tone="green">THIS CAMERA</Pill>}
                <div className="ml-auto flex gap-1">
                  <button
                    onClick={() => void toggle(z)}
                    className={`text-[9px] font-mono px-1.5 py-0.5 border rounded-sm ${z.active
                      ? 'border-cc-accent/50 text-cc-accent'
                      : 'border-cc-line text-cc-dim'}`}
                  >
                    {z.active ? 'ACTIVE' : 'OFF'}
                  </button>
                  <button
                    onClick={() => void del(z)}
                    className="text-[9px] font-mono px-1.5 py-0.5 border border-cc-red/40 text-cc-red rounded-sm hover:bg-cc-red/10"
                  >
                    DEL
                  </button>
                </div>
              </div>
              <div className="text-[9px] font-mono text-cc-dim mt-0.5 truncate">
                {z.source_id} · {z.kind === 'polygon'
                  ? `${z.geometry.points?.length ?? 0} pts`
                  : `${z.geometry.p1} → ${z.geometry.p2} (${z.geometry.direction_mode ?? 'both'})`}
              </div>
            </div>
          ))}
      </div>
    </Panel>
  );
}
