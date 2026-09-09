// Central store: REAL backend state only, refreshed by SSE pushes
// (ADR-002: 'live updates via EXISTING SSE — no polling').
// Health/session metrics poll at a slow cadence (they are pull-shaped
// endpoints by design); EVENTS arrive via /api/stream/events SSE.

import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';
import type {
  EventRow, GeoCamera, GeoSector, Health, MapConfig, SessionStatus, ZoneRow,
} from './types';

export type Page =
  | 'dashboard' | 'cameras' | 'events' | 'investigation'
  | 'geography' | 'analytics' | 'sources';

export interface Store {
  page: Page;
  setPage: (p: Page) => void;
  health: Health | null;
  healthError: string | null;
  status: SessionStatus;
  events: EventRow[];           // newest-first, capped
  zones: ZoneRow[];
  cameras: GeoCamera[];
  sectors: GeoSector[];
  mapConfig: MapConfig | null;
  selectedCamera: string | null;
  selectedEventId: string | null;
  sseState: 'connecting' | 'open' | 'closed';
  clock: Date;
  refreshAll: () => Promise<void>;
  refreshEvents: () => Promise<void>;
  refreshGeo: () => Promise<void>;
  refreshZones: () => Promise<void>;
  selectCamera: (id: string | null) => void;
  selectEvent: (id: string | null) => void;
  ack: (id: string) => Promise<void>;
}

const MAX_EVENTS = 500;

export function useStore(): Store {
  const [page, setPage] = useState<Page>('dashboard');
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [status, setStatus] = useState<SessionStatus>({ active: false, session: null });
  const [events, setEvents] = useState<EventRow[]>([]);
  const [zones, setZones] = useState<ZoneRow[]>([]);
  const [cameras, setCameras] = useState<GeoCamera[]>([]);
  const [sectors, setSectors] = useState<GeoSector[]>([]);
  const [mapConfig, setMapConfig] = useState<MapConfig | null>(null);
  const [selectedCamera, setSelectedCamera] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [sseState, setSseState] = useState<'connecting' | 'open' | 'closed'>('connecting');
  const [clock, setClock] = useState(new Date());
  const eventsRef = useRef<EventRow[]>([]);
  eventsRef.current = events;

  const refreshEvents = useCallback(async () => {
    try {
      const r = await api.events({ limit: 100 });
      setEvents(r.events);
    } catch { /* transient — SSE will refill */ }
  }, []);

  const refreshGeo = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([api.mapCameras(), api.mapSectors()]);
      setCameras(c.cameras);
      setSectors(s.sectors);
    } catch { /* map layer degrades; never blocks */ }
  }, []);

  const refreshZones = useCallback(async () => {
    try {
      const z = await api.zones();
      setZones(z.zones);
    } catch { /* transient */ }
  }, []);

  const refreshAll = useCallback(async () => {
    try {
      const [h, st, z, mc] = await Promise.all([
        api.health(), api.sessionStatus(), api.zones(), api.mapConfig(),
      ]);
      setHealth(h);
      setHealthError(null);
      setStatus(st);
      setZones(z.zones);
      setMapConfig(mc);
    } catch (e) {
      setHealthError(String(e));
    }
    await Promise.all([refreshEvents(), refreshGeo()]);
  }, [refreshEvents, refreshGeo]);

  // initial load
  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  // slow poll of pull-shaped endpoints (health/session/zones)
  useEffect(() => {
    const iv = setInterval(() => {
      void refreshAll();
    }, 5000);
    return () => clearInterval(iv);
  }, [refreshAll]);

  // operator wall clock (1s tick — display only, no API)
  useEffect(() => {
    const iv = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(iv);
  }, []);

  // SSE: live events (auto-reconnect is EventSource-native)
  useEffect(() => {
    const es = new EventSource('/api/stream/events');
    es.onopen = () => setSseState('open');
    es.onerror = () => setSseState('connecting');
    es.onmessage = (msg) => {
      try {
        const ev = JSON.parse(msg.data) as EventRow;
        if (ev.keepalive) return;
        setEvents(prev => {
          if (prev.some(e => e.id === ev.id)) return prev;   // idempotent
          const next = [ev, ...prev];
          return next.length > MAX_EVENTS ? next.slice(0, MAX_EVENTS) : next;
        });
        // live geo refresh on system events (camera status changes)
        if (ev.type.startsWith('SOURCE_') || ev.type.startsWith('SESSION_')) {
          void refreshGeo();
          void api.sessionStatus().then(setStatus).catch(() => {});
        }
      } catch { /* ignore malformed frame */ }
    };
    return () => es.close();
  }, [refreshGeo]);

  const ack = useCallback(async (id: string) => {
    await api.ackEvent(id);
    setEvents(prev => prev.map(e => (e.id === id ? { ...e, status: 'acked' } : e)));
  }, []);

  return {
    page, setPage,
    health, healthError, status, events, zones, cameras, sectors, mapConfig,
    selectedCamera, selectedEventId, sseState, clock,
    refreshAll, refreshEvents, refreshGeo, refreshZones,
    selectCamera: setSelectedCamera,
    selectEvent: setSelectedEventId,
    ack,
  };
}
