// GeoMap — the ADR-003 fallback chain, in order:
//   satellite (Google) → roadmap (Google) → schematic (offline SVG).
// Google Maps JS is loaded with the key from /api/map/config (held in
// .env server-side; never in this source, never in git). ANY failure —
// no key, bad key, blocked CDN, timeout — lands on the offline
// schematic, which renders the same cameras/sectors/events from REAL
// backend state. The map can NEVER block the CV pipeline (ADR-003
// binding rule): this panel renders or degrades independently.

import { useEffect, useMemo, useRef, useState } from 'react';
import { loadGoogleMaps } from '../mapLoader';
import type { GMap, GMapTypeId, GMaps, GMarker, GPolygon } from '../mapTypes';
import type { Store } from '../store';
import { Panel, Pill } from './ui';

type Mode = 'loading' | 'satellite' | 'roadmap' | 'schematic';

// Demo deployment coordinates (EXPLICITLY SIMULATED — labeled as such
// in the UI; ADR-002 honesty rule). A real deployment configures real
// lat/lng per camera via PUT /api/map/cameras/{id}/geo.
const DEMO_CENTER = { lat: 28.6139, lng: 77.2090 };   // demo area anchor
const SECTOR_COLOR = '#2563EB';
const SECTOR_ACTIVE_FILL = 'rgba(37,99,235,0.10)';
const MARKER_LIVE = '#16A34A';
const MARKER_IDLE = '#5C6672';
const MARKER_ERR = '#DC2626';

export default function GeoMap({ store }: { store: Store }) {
  const { mapConfig, cameras, sectors, events, selectedCamera,
    selectCamera, selectedEventId, selectEvent } = store;
  const hostRef = useRef<HTMLDivElement>(null);
  const gmapRef = useRef<GMap | null>(null);
  const gmapsRef = useRef<GMaps | null>(null);
  const markersRef = useRef<Map<string, { marker: GMarker }>>(new Map());
  const polysRef = useRef<Map<string, { poly: GPolygon }>>(new Map());
  const [mode, setMode] = useState<Mode>('loading');
  const [note, setNote] = useState('');
  const lastSectorKeyRef = useRef<string>('');
  // stable event-selection callback for map markers (no marker churn)
  const selectEventRef = useRef<((id: string) => void) | null>(null);
  selectEventRef.current = selectEvent;

  // active (new/unacked) events with a geo-located camera → map markers
  const activeEvents = useMemo(
    () => events.filter(e =>
      e.status === 'new'
      && (e.severity === 'HIGH' || e.severity === 'MEDIUM')
      && cameras.find(c => c.camera_id === e.source_id && c.has_coordinates)),
    [events, cameras],
  );
  const selectedEvent = events.find(e => e.id === selectedEventId) ?? null;
  const highlightCamera = selectedEvent?.source_id ?? null;
  const selectedCam = cameras.find(c => c.camera_id === selectedCamera) ?? null;

  // ---- load attempt: satellite primary, roadmap fallback, schematic last ----
  useEffect(() => {
    if (!mapConfig) return;
    if (!mapConfig.google_maps_key) {
      setMode('schematic');
      setNote('no Google Maps key — offline schematic');
      return;
    }
    let dead = false;
    setMode('loading');
    loadGoogleMaps(mapConfig).then(maps => {
      if (dead || !hostRef.current) return;
      gmapsRef.current = maps;
      const el = hostRef.current;
      const map = new maps.Map(el, {
        center: selectedCam?.has_coordinates
          ? { lat: selectedCam.latitude!, lng: selectedCam.longitude! }
          : DEMO_CENTER,
        zoom: 14,
        mapTypeId: (maps.MapTypeId?.SATELLITE as GMapTypeId | undefined) ?? 'satellite',
        disableDefaultUI: false,
        mapTypeControl: true,
      });
      gmapRef.current = map;
      setMode('satellite');
      setNote('Google satellite tiles');
    }).catch(() => {
      if (dead) return;
      // roadmap retry (tiles_error downgrade), then schematic
      setMode(prev => {
        if (prev === 'satellite') {
          setNote('satellite failed — roadmap tiles');
          return 'roadmap';
        }
        setNote('maps unavailable — offline schematic');
        return 'schematic';
      });
    });
    return () => { dead = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mapConfig?.google_maps_key]);

  // satellite → roadmap downgrade for an ALREADY loaded map
  useEffect(() => {
    if (mode === 'roadmap' && gmapRef.current && gmapsRef.current) {
      gmapRef.current.setMapTypeId?.(
        (gmapsRef.current.MapTypeId?.ROADMAP ?? 'roadmap'));
    }
  }, [mode]);

  // ---- camera markers (Google path) ----
  useEffect(() => {
    if ((mode !== 'satellite' && mode !== 'roadmap')
      || !gmapRef.current || !gmapsRef.current) return;
    const maps = gmapsRef.current;
    const map = gmapRef.current;
    const prev = markersRef.current;
    for (const c of cameras) {
      if (!c.has_coordinates) continue;
      const fill = c.status === 'live' ? MARKER_LIVE
        : c.status === 'error' ? MARKER_ERR : MARKER_IDLE;
      const scale = highlightCamera === c.camera_id ? 1.6 : 1.1;
      const existing = prev.get(c.camera_id);
      if (existing) {
        existing.marker.setPosition?.({ lat: c.latitude!, lng: c.longitude! });
        existing.marker.setIcon?.({
          path: maps.SymbolPath?.CIRCLE ?? 0,
          fillColor: fill, fillOpacity: 0.9,
          strokeColor: '#FFFFFF', strokeWeight: 2, scale,
        });
        continue;
      }
      const marker = new maps.Marker({
        position: { lat: c.latitude!, lng: c.longitude! },
        map,
        title: `${c.label} (${c.camera_id}) — ${c.status}`,
        // minimal circle glyph via built-in path (no external assets)
        icon: {
          path: maps.SymbolPath?.CIRCLE ?? 0,
          fillColor: fill,
          fillOpacity: 0.9,
          strokeColor: '#FFFFFF',
          strokeWeight: 2,
          scale,
        },
      });
      maps.event.addListener(marker, 'click', () => selectCamera(c.camera_id));
      prev.set(c.camera_id, { marker });
    }
    // §16: selecting a camera focuses the map on it (pan only, once
    // per selection — no per-event map recreation)
    if (selectedCam?.has_coordinates) {
      map.panTo?.({ lat: selectedCam.latitude!, lng: selectedCam.longitude! });
    }
  }, [cameras, mode, highlightCamera, selectCamera, selectedCam]);

  // ---- sector polygons (Google path) ----
  useEffect(() => {
    if ((mode !== 'satellite' && mode !== 'roadmap')
      || !gmapRef.current || !gmapsRef.current) return;
    const maps = gmapsRef.current;
    const map = gmapRef.current;
    const key = sectors.map(s => `${s.id}:${s.active}:${s.polygon.length}`).join('|');
    if (key === lastSectorKeyRef.current) return;
    lastSectorKeyRef.current = key;
    for (const p of polysRef.current.values()) p.poly.setMap?.(null);
    polysRef.current.clear();
    for (const s of sectors) {
      if (!s.polygon?.length) continue;
      const poly = new maps.Polygon({
        paths: s.polygon.map(([lat, lng]) => ({ lat, lng })),
        strokeColor: SECTOR_COLOR,
        strokeOpacity: 0.8,
        strokeWeight: 1.5,
        fillColor: SECTOR_COLOR,
        fillOpacity: s.active ? 0.10 : 0.03,
        map,
      });
      polysRef.current.set(s.id, { poly });
    }
  }, [sectors, mode]);

  const eventMarkers = useMemo(
    () => activeEvents.map(e => {
      const cam = cameras.find(c => c.camera_id === e.source_id);
      return cam ? { ev: e, lat: cam.latitude!, lng: cam.longitude! } : null;
    }).filter(Boolean) as { ev: { id: string; severity: string; type: string }; lat: number; lng: number }[],
    [activeEvents, cameras]);

  // ---- active event markers (Google path, §16) ----
  const evMarkerRef = useRef<Map<string, { marker: GMarker }>>(new Map());
  useEffect(() => {
    if ((mode !== 'satellite' && mode !== 'roadmap')
      || !gmapRef.current || !gmapsRef.current) return;
    const maps = gmapsRef.current;
    const map = gmapRef.current;
    const prev = evMarkerRef.current;
    const live = new Set(eventMarkers.map(m => m.ev.id));
    // drop stale ones (acked / filtered out)
    for (const [id, entry] of prev) {
      if (!live.has(id)) {
        entry.marker.setMap?.(null);
        prev.delete(id);
      }
    }
    for (const m of eventMarkers) {
      if (prev.has(m.ev.id)) continue;
      const high = m.ev.severity === 'HIGH';
      const marker = new maps.Marker({
        position: { lat: m.lat, lng: m.lng },
        map,
        title: `${m.ev.type} (${m.ev.severity})`,
        // ring glyph at the camera — severity-colored, no assets
        icon: {
          path: maps.SymbolPath?.CIRCLE ?? 0,
          fillColor: high ? '#DC2626' : '#D97706',
          fillOpacity: 0,
          strokeColor: high ? '#DC2626' : '#D97706',
          strokeWeight: 2,
          scale: high ? 7 : 5,
        },
        zIndex: 10,
      });
      maps.event.addListener(marker, 'click', () => {
        selectEventRef.current?.(m.ev.id);
      });
      prev.set(m.ev.id, { marker });
    }
  }, [eventMarkers, mode]);

  const modePill = mode === 'satellite' ? <Pill tone="green">SATELLITE</Pill>
    : mode === 'roadmap' ? <Pill tone="amber">ROADMAP FALLBACK</Pill>
    : mode === 'schematic' ? <Pill tone="dim">OFFLINE SCHEMATIC</Pill>
    : <Pill tone="dim">LOADING…</Pill>;

  return (
    <Panel
      title="Operational Map"
      right={
        <div className="flex items-center gap-2">
          {mapConfig?.simulated && <Pill tone="amber">DEMO AREA — SIMULATED</Pill>}
          {modePill}
        </div>
      }
      className="min-h-0"
    >
      <div className="relative w-full h-full min-h-0">
        {/* google host */}
        <div
          ref={hostRef}
          className={`absolute inset-0 ${mode === 'satellite' || mode === 'roadmap' ? '' : 'hidden'}`}
        />
        {/* offline schematic */}
        {mode === 'schematic' && (
          <SchematicMap
            cameras={cameras}
            sectors={sectors}
            eventMarkers={eventMarkers}
            selectedCamera={selectedCamera}
            highlightCamera={highlightCamera}
            onSelect={selectCamera}
            onSelectEvent={selectEvent}
          />
        )}
        {note && (
          <div className="absolute bottom-1 left-2 text-[9px] font-mono text-cc-dim bg-white/80 px-1.5 rounded">
            {note}
          </div>
        )}
      </div>
    </Panel>
  );
}

// ---- offline schematic: same REAL data, SVG equirectangular projection ----
function SchematicMap({ cameras, sectors, eventMarkers, selectedCamera,
  highlightCamera, onSelect, onSelectEvent }: {
  cameras: { camera_id: string; label: string; status: string; has_coordinates: boolean; latitude: number | null; longitude: number | null }[];
  sectors: { id: string; name: string; polygon: number[][]; active: boolean }[];
  eventMarkers: { ev: { id: string; severity: string; type: string }; lat: number; lng: number }[];
  selectedCamera: string | null;
  highlightCamera: string | null;
  onSelect: (id: string) => void;
  onSelectEvent: (id: string) => void;
}) {
  const W = 640, H = 400;
  const all = [
    ...cameras.filter(c => c.has_coordinates)
      .map(c => [c.latitude!, c.longitude!] as const),
    ...sectors.flatMap(s => s.polygon),
    [DEMO_CENTER.lat, DEMO_CENTER.lng] as const,
  ];
  const lats = all.map(p => p[0]), lngs = all.map(p => p[1]);
  const pad = 0.02;
  const minLat = Math.min(...lats) - pad, maxLat = Math.max(...lats) + pad;
  const minLng = Math.min(...lngs) - pad, maxLng = Math.max(...lngs) + pad;
  const x = (lng: number) => ((lng - minLng) / (maxLng - minLng)) * (W - 40) + 20;
  const y = (lat: number) => H - (((lat - minLat) / (maxLat - minLat)) * (H - 60) + 30);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full" preserveAspectRatio="xMidYMid meet">
      <defs>
        <pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
          <path d="M 32 0 L 0 0 0 32" fill="none" stroke="#D8DEE4" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width={W} height={H} fill="#E9EDF1" />
      <rect width={W} height={H} fill="url(#grid)" />
      <text x={W / 2} y={16} textAnchor="middle" fill="#5C6672" fontSize="10"
        fontFamily="monospace">OFFLINE SCHEMATIC — SIMULATED DEPLOYMENT (NO TILES)</text>
      {sectors.map(s => (
        <polygon
          key={s.id}
          points={s.polygon.map(([lat, lng]) => `${x(lng)},${y(lat)}`).join(' ')}
          fill={s.active ? SECTOR_ACTIVE_FILL : 'transparent'}
          stroke={SECTOR_COLOR}
          strokeWidth="1.5"
          strokeDasharray={s.active ? '' : '4 3'}
        />
      ))}
      {sectors.map(s => s.polygon[0] && (
        <text key={s.id} x={x(s.polygon[0][1]) + 6} y={y(s.polygon[0][0]) - 6}
          fill="#5C6672" fontSize="9" fontFamily="monospace">{s.name}</text>
      ))}
      {eventMarkers.map(m => (
        <circle key={m.ev.id} cx={x(m.lng)} cy={y(m.lat)} r="10"
          fill="none" stroke={m.ev.severity === 'HIGH' ? '#DC2626' : '#D97706'}
          strokeWidth="1.5" opacity="0.8"
          onClick={() => onSelectEvent(m.ev.id)} style={{ cursor: 'pointer' }}>
          <animate attributeName="r" values="6;14;6" dur="2s" repeatCount="indefinite" />
        </circle>
      ))}
      {cameras.filter(c => c.has_coordinates).map(c => {
        const sel = selectedCamera === c.camera_id;
        const hl = highlightCamera === c.camera_id;
        const color = c.status === 'live' ? MARKER_LIVE
          : c.status === 'error' ? MARKER_ERR : MARKER_IDLE;
        return (
          <g key={c.camera_id} transform={`translate(${x(c.longitude!)},${y(c.latitude!)})`}
            onClick={() => onSelect(c.camera_id)} style={{ cursor: 'pointer' }}>
            {(sel || hl) && <circle r="14" fill="none" stroke={sel ? '#2563EB' : '#D97706'} strokeWidth="1.5" />}
            <circle r="6" fill={color} stroke="#FFFFFF" strokeWidth="1.5" />
            <text x="10" y="4" fill={sel ? '#101418' : '#5C6672'} fontSize="10" fontFamily="monospace">
              {c.label}
            </text>
          </g>
        );
      })}
      <text x={W - 8} y={H - 8} textAnchor="end" fill="#8A94A0" fontSize="8"
        fontFamily="monospace">equirectangular · real registered coordinates only</text>
    </svg>
  );
}
