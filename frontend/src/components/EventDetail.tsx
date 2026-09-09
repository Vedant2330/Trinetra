// EventDetail — the operator investigation chain for ONE event:
// EVENT → CAMERA → TRACK → VIDEO ZONE → GEO SECTOR → EVIDENCE.
// Everything shown comes from the real event row (+ zone/camera joins).
// Geo-sector correlation (§13): point-in-polygon of the CAMERA's real
// coordinates against active geo sectors — deterministic geometry, no
// backend invention; '—' when the camera is unplaced.

import { evidenceUrl } from '../api';
import type { Store } from '../store';
import { EmptyState, Panel, SevChip, eventTypeLabel } from './ui';

// ray-casting point-in-polygon over [[lat,lng], ...] sectors
export function pointInSector(
  lat: number, lng: number, polygon: number[][],
): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [latI, lngI] = polygon[i];
    const [latJ, lngJ] = polygon[j];
    const intersects = (latI > lat) !== (latJ > lat)
      && lng < ((lngJ - lngI) * (lat - latI)) / (latJ - latI || 1e-12) + lngI;
    if (intersects) inside = !inside;
  }
  return inside;
}

function containingSectors(store: Store, cameraId: string): string[] {
  const cam = store.cameras.find(c => c.camera_id === cameraId);
  if (!cam?.has_coordinates) return [];
  return store.sectors
    .filter(s => s.active && s.polygon?.length >= 3)
    .filter(s => pointInSector(cam.latitude!, cam.longitude!, s.polygon))
    .map(s => s.name);
}

export default function EventDetail({ store }: { store: Store }) {
  const ev = store.events.find(e => e.id === store.selectedEventId) ?? null;
  if (!ev) {
    return (
      <Panel title="Event Detail" className="min-h-0">
        <EmptyState>select an event to investigate</EmptyState>
      </Panel>
    );
  }
  const zone = ev.zone_id ? store.zones.find(z => z.id === ev.zone_id) ?? null : null;
  const camera = store.cameras.find(c => c.camera_id === ev.source_id) ?? null;
  const evUrl = evidenceUrl(ev);
  const sectors = containingSectors(store, ev.source_id);

  return (
    <Panel
      title="Event Detail — Investigation Chain"
      right={
        <div className="flex items-center gap-2">
          <SevChip severity={ev.severity} />
          {ev.status === 'new' ? (
            <button
              onClick={() => void store.ack(ev.id)}
              className="text-[10px] font-mono px-2 py-0.5 border border-cc-amber/60 text-cc-amber rounded-sm hover:bg-cc-amber/10"
            >
              ACK
            </button>
          ) : (
            <span className="text-[10px] font-mono text-cc-dim">ACKED</span>
          )}
        </div>
      }
      className="min-h-0"
      scroll
    >
      <div className="p-3 space-y-3">
        {/* headline */}
        <div className="flex items-baseline gap-2 flex-wrap">
          <span className={`text-[15px] font-semibold ${ev.severity === 'HIGH' ? 'text-cc-red' : 'text-cc-text'}`}>
            {eventTypeLabel(ev.type)}
          </span>
          <span className="text-[11px] font-mono text-cc-dim">{ev.ts}</span>
          {ev.video_ts != null && (
            <span className="text-[10px] font-mono text-cc-dim">video +{ev.video_ts.toFixed(2)}s</span>
          )}
          {ev.is_night && <span className="text-[10px] font-mono text-cc-blue">NIGHT</span>}
        </div>

        {/* severity reason (engine explanation — real, deterministic) */}
        {ev.metadata?.severity_reason && (
          <div className="text-[11px] text-cc-dim font-mono bg-cc-panel2 border border-cc-line rounded px-2.5 py-1.5">
            {String(ev.metadata.severity_reason)}
          </div>
        )}

        {/* chain grid */}
        <div className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-[11px] font-mono">
          <span className="text-cc-dim uppercase text-[9px] tracking-wider self-center">Camera</span>
          <button
            className="text-left text-cc-text hover:text-cc-blue truncate"
            onClick={() => store.selectCamera(ev.source_id)}
          >
            {ev.source_id}
            {camera?.has_coordinates
              && <span className="text-cc-dim"> · {camera.latitude!.toFixed(4)}, {camera.longitude!.toFixed(4)}</span>}
          </button>

          <span className="text-cc-dim uppercase text-[9px] tracking-wider self-center">Track</span>
          <span className="text-cc-text">
            {ev.track_ids.length
              ? ev.track_ids.map(t => `#${t}`).join('  ')
              : '—'}
          </span>

          <span className="text-cc-dim uppercase text-[9px] tracking-wider self-center">Video Zone</span>
          <span className="text-cc-text truncate">
            {zone
              ? `${zone.name} (${zone.kind}, ${zone.zone_type})`
              : ev.zone_id ? `${ev.zone_id} (deleted zone)` : '—'}
          </span>

          {ev.direction && (
            <>
              <span className="text-cc-dim uppercase text-[9px] tracking-wider self-center">Direction</span>
              <span className="text-cc-blue">{ev.direction}</span>
            </>
          )}

          <span className="text-cc-dim uppercase text-[9px] tracking-wider self-center">Geo Sector</span>
          <span className={sectors.length ? 'text-cc-blue' : 'text-cc-dim'}>
            {camera?.has_coordinates
              ? (sectors.length
                ? sectors.join(', ')
                : 'no containing sector')
              : '— (camera unplaced)'}
          </span>

          <span className="text-cc-dim uppercase text-[9px] tracking-wider self-center">Session</span>
          <span className="text-cc-dim truncate">{ev.session_id.slice(0, 13)}…</span>

          <span className="text-cc-dim uppercase text-[9px] tracking-wider self-center">Confidence</span>
          <span className="text-cc-text">{(ev.confidence * 100).toFixed(1)}%</span>
        </div>

        {/* evidence */}
        <div>
          <div className="text-[9px] uppercase tracking-wider text-cc-dim mb-1">Evidence Snapshot</div>
          {evUrl ? (
            <img
              src={evUrl}
              alt="event evidence"
              className="max-h-52 w-auto border border-cc-line rounded"
            />
          ) : (
            <div className="text-[11px] font-mono text-cc-dim border border-dashed border-cc-line rounded px-3 py-4 text-center">
              {ev.metadata?.snapshot_skipped_low_disk
                ? 'snapshot skipped — low disk (event still committed)'
                : 'no snapshot registered for this event (severity below threshold or system event)'}
            </div>
          )}
        </div>
      </div>
    </Panel>
  );
}
