// GeoSectors — geographic sector CRUD via /api/map/sectors (real DB
// rows, lat/lng polygons — DISTINCT from video zones, ADR-002).

import { useState } from 'react';
import { api } from '../api';
import type { Store } from '../store';
import { EmptyState, Panel, Pill } from './ui';

export default function GeoSectors({ store }: { store: Store }) {
  const { sectors, refreshGeo } = store;
  const [name, setName] = useState('');
  const [polygon, setPolygon] = useState('12.970,77.590 12.975,77.593 12.972,77.598 12.968,77.595');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const create = async () => {
    setBusy(true); setErr(null);
    try {
      const pts = polygon.trim().split(/\s+/).map(pair => {
        const [lat, lng] = pair.split(',').map(Number);
        return [lat, lng];
      });
      await api.createSector({ name: name || 'sector', polygon: pts });
      await refreshGeo();
    } catch (e) {
      setErr(String((e as Error).message));
    } finally { setBusy(false); }
  };

  return (
    <Panel title="Geographic Sectors" scroll className="min-h-0">
      <div className="p-2 space-y-2">
        {err && (
          <div className="text-[10px] font-mono text-cc-red bg-cc-red/5 border border-cc-red/30 rounded px-2 py-1">
            {err}
          </div>
        )}
        <div className="border border-cc-line rounded p-2 space-y-1.5 bg-cc-panel2/50">
          <div className="text-[9px] uppercase tracking-wider text-cc-dim">New Sector (lat,lng points)</div>
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="sector name"
            className="w-full bg-cc-bg border border-cc-line rounded px-2 py-1 text-[11px] font-mono"
          />
          <input
            value={polygon}
            onChange={e => setPolygon(e.target.value)}
            className="w-full bg-cc-bg border border-cc-line rounded px-2 py-1 text-[10px] font-mono"
            placeholder="lat,lng lat,lng lat,lng (>= 3 points)"
          />
          <button
            disabled={busy}
            onClick={() => void create()}
            className="w-full text-[10px] font-mono px-2 py-1 border border-cc-accent/60 text-cc-accent rounded-sm hover:bg-cc-accent/10 disabled:opacity-40"
          >
            CREATE SECTOR
          </button>
        </div>
        {sectors.length === 0
          ? <EmptyState>no geo sectors defined</EmptyState>
          : sectors.map(s => (
            <div key={s.id} className="border border-cc-line rounded px-2.5 py-1.5 bg-cc-panel2/30">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-mono text-cc-blue">{s.name}</span>
                <Pill tone={s.active ? 'green' : 'dim'}>{s.active ? 'ACTIVE' : 'INACTIVE'}</Pill>
                <button
                  onClick={async () => {
                    try { await api.deleteSector(s.id); await refreshGeo(); }
                    catch (e) { setErr(String((e as Error).message)); }
                  }}
                  className="ml-auto text-[9px] font-mono px-1.5 py-0.5 border border-cc-red/40 text-cc-red rounded-sm hover:bg-cc-red/10"
                >
                  DEL
                </button>
              </div>
              <div className="text-[9px] font-mono text-cc-dim mt-0.5">
                {s.polygon.length} pts {s.description ? `· ${s.description}` : ''}
              </div>
            </div>
          ))}
      </div>
    </Panel>
  );
}
