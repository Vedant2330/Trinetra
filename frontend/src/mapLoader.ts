// Google Maps JS loader — ADR-003 fallback chain:
//   1. satellite (primary)
//   2. roadmap (same key)
//   3. offline schematic (SVG — no network at all)
// The key comes from /api/map/config (which reads .env server-side).
// It NEVER appears in this source file, and the map failing NEVER
// affects the CV/event pipeline — worst case is the schematic panel.
//
// NOTE: no @types/google.maps dependency — a minimal local shape is
// declared in mapTypes.ts; anything the UI doesn't use isn't declared.

import type { MapConfig } from './types';
import type { GMaps } from './mapTypes';

export type MapMode = 'satellite' | 'roadmap' | 'schematic';

export interface WindowWithGoogle {
  google?: { maps: GMaps };
  __trinetraMapsCb?: () => void;
}

let loadPromise: Promise<GMaps> | null = null;
let attempted = false;          // one attempt per page load — no retry storm

export function mapsAvailable(): boolean {
  const w = window as unknown as WindowWithGoogle;
  return !!w.google?.maps;
}

export function loadGoogleMaps(config: MapConfig): Promise<GMaps> {
  if (!config.google_maps_key) {
    return Promise.reject(new Error('no key — schematic fallback'));
  }
  if (mapsAvailable()) {
    return Promise.resolve((window as unknown as WindowWithGoogle).google!.maps);
  }
  if (attempted) return Promise.reject(new Error('maps already failed'));
  if (loadPromise) return loadPromise;

  attempted = true;
  loadPromise = new Promise<GMaps>((resolve, reject) => {
    const w = window as unknown as WindowWithGoogle;
    const s = document.createElement('script');
    const cb = '__trinetraMapsCb';
    s.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(
      config.google_maps_key)}&callback=${cb}`;
    s.async = true;
    s.onerror = () => reject(new Error('script load failed'));
    w[cb as '__trinetraMapsCb'] = () => {
      if (w.google?.maps) resolve(w.google.maps);
      else reject(new Error('maps namespace missing'));
    };
    document.head.appendChild(s);
    // hard timeout — slow/failed CDN must not leave the panel stuck
    setTimeout(() => {
      if (!mapsAvailable()) reject(new Error('maps load timeout'));
    }, 10_000);
  });
  return loadPromise;
}
