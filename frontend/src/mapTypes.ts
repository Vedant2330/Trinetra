// Minimal local shapes for the Google Maps JS API surface the Command
// Center actually uses (markers, polygons, map, latlng, events). NOT a
// full @types/google.maps mirror — declared as used, honest subset.

export interface GLatLngLiteral { lat: number; lng: number }

export interface GMapMouseEvent { latLng: GLatLngLiteral | null }

export interface GIcon {
  path: number | string;
  fillColor?: string;
  fillOpacity?: number;
  strokeColor?: string;
  strokeWeight?: number;
  scale?: number;
}

export interface GMarker {
  setPosition(p: GLatLngLiteral): void;
  setMap(m: GMap | null): void;
  addListener(ev: string, cb: () => void): void;
  setIcon(icon: GIcon | string): void;
}

export interface GPolygon {
  setMap(m: GMap | null): void;
  addListener(ev: string, cb: (e: GMapMouseEvent) => void): void;
  getPath(): { getArray(): GLatLngLiteral[] };
}

export type GMapTypeId = 'satellite' | 'roadmap' | 'hybrid' | 'terrain';

export interface GMapOptions {
  center: GLatLngLiteral;
  zoom: number;
  mapTypeId: GMapTypeId;
  tilt?: number;
  disableDefaultUI?: boolean;
  mapTypeControl?: boolean;
  streetViewControl?: boolean;
}

export interface GMap {
  setCenter(p: GLatLngLiteral): void;
  setZoom(z: number): void;
  setMapTypeId(t: GMapTypeId): void;
  panTo(p: GLatLngLiteral): void;
  addListener(ev: string, cb: () => void): void;
  getZoom(): number;
}

export interface GSymbolPath { CIRCLE: number; }

export interface GEvent {
  addListener(target: unknown, ev: string, cb: () => void): void;
  addListenerOnce(target: unknown, ev: string, cb: () => void): void;
  removeListener(h: unknown): void;
}

export interface GMaps {
  // Google Maps JS API exposes these as constructors — `new` is required
  // (calling without `new` throws "this.set is not a function").
  Map: { new (el: HTMLElement, opts: GMapOptions): GMap };
  Marker: { new (opts: {
    position: GLatLngLiteral;
    map: GMap;
    title?: string;
    label?: string | { text: string; color?: string; fontSize?: string };
    icon?: GIcon | string;
    zIndex?: number;
  }): GMarker };
  Polygon: { new (opts: {
    paths: GLatLngLiteral[];
    strokeColor?: string;
    strokeOpacity?: number;
    strokeWeight?: number;
    fillColor?: string;
    fillOpacity?: number;
    map: GMap;
  }): GPolygon };
  MapTypeId: {
    HYBRID: GMapTypeId;
    ROADMAP: GMapTypeId;
    SATELLITE: GMapTypeId;
    TERRAIN: GMapTypeId;
  };
  SymbolPath: GSymbolPath;
  AddListener: (target: unknown, ev: string, cb: () => void) => void;
  event: GEvent;
}
