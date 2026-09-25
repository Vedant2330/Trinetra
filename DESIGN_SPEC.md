# TRINETRA VISUAL DESIGN SPECIFICATION
**Version:** 1.0  
**Date:** September 25, 2026  
**Author:** Framer (Athena)  
**Target:** `/Volumes/Vedant/vedantsecondary/Projects/SIH26/Trinetra/frontend`

---

## DESIGN PRINCIPLES

| Principle | Expression |
|-----------|------------|
| **Premium** | Apple-level finish; every pixel intentional; restraint over decoration |
| **Minimal** | Maximum signal, minimum chrome; no decorative charts or "AI" clichés |
| **Intelligent** | Information hierarchy mirrors cognitive load; progressive disclosure |
| **Spatial** | Consistent rhythm; surfaces have depth; motion is physical |
| **Calm** | No neon, no vibration; color is semantic, not decorative |
| **Precise** | Monospace for data; proportional for narrative; units are explicit |
| **Technical** | Honest about state (loading, error, empty); no fake data |
| **Human** | Readable at density; accessible contrast; respectful of attention |

---

## COLOR SYSTEM

### Semantic Palette (Light Mode) — **Current Base**
```css
--cc-bg:       #F6F7F9   /* page background */
--cc-panel:    #FFFFFF   /* card/panel surface */
--cc-panel2:   #F2F4F6   /* elevated/subtle surface */
--cc-line:     #E3E7EB   /* borders, dividers */
--cc-text:     #101418   /* primary text */
--cc-dim:      #5C6672   /* secondary/muted text */
--cc-accent:   #16A34A   /* success/online/positive */
--cc-red:      #DC2626   /* critical/error/high severity */
--cc-amber:    #D97706   /* warning/medium severity */
--cc-blue:     #2563EB   /* info/low severity/primary action */
```

### Semantic Palette (Dark Mode) — **New Addition**
```css
--cc-bg:       #0B0F14   /* page background - deep navy-black */
--cc-panel:    #11171E   /* card/panel surface */
--cc-panel2:   #161D26   /* elevated/subtle surface */
--cc-line:     #1E2834   /* borders, dividers */
--cc-text:     #E8EBF0   /* primary text */
--cc-dim:      #7A8796   /* secondary/muted text */
--cc-accent:   #22C55E   /* success/online/positive */
--cc-red:      #EF4444   /* critical/error/high severity */
--cc-amber:    #F59E0B   /* warning/medium severity */
--cc-blue:     #3B82F6   /* info/low severity/primary action */
```

### Severity Colors (Consistent Across Modes)
| Severity | Light | Dark | Usage |
|----------|-------|------|-------|
| HIGH | #DC2626 | #EF4444 | Immediate threat, unacked critical |
| MEDIUM | #D97706 | #F59E0B | Zone breach, loitering, abnormal |
| LOW | #2563EB | #3B82F6 | Detection, ANPR, face |
| INFO | #5C6672 | #7A8796 | Entry/exit, session events |

### State Overlays (8% opacity base)
```css
--cc-accent-bg:  rgba(22, 163, 74, 0.08)   /* success */
--cc-red-bg:     rgba(220, 38, 38, 0.08)    /* error */
--cc-amber-bg:   rgba(217, 119, 6, 0.08)    /* warning */
--cc-blue-bg:    rgba(37, 99, 235, 0.08)    /* info */
```

---

## TYPOGRAPHY SYSTEM

### Font Stack
```css
--font-mono:    'ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', monospace;
--font-sans:    'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', sans-serif;
```

### Type Scale (Mobile → Desktop)
| Token | Size/Line | Weight | Tracking | Usage |
|-------|-----------|--------|----------|-------|
| `--text-xs` | 10px / 14px | 400 | +0.08em | Labels, badges, timestamps |
| `--text-sm` | 11px / 16px | 400 | +0.04em | Body dense, metadata |
| `--text-base` | 13px / 20px | 400 | 0 | Default body |
| `--text-lg` | 15px / 24px | 400 | 0 | Comfortable reading |
| `--text-xl` | 18px / 28px | 500 | -0.01em | Section titles |
| `--text-2xl` | 22px / 32px | 600 | -0.02em | Page titles |
| `--text-3xl` | 32px / 40px | 600 | -0.03em | Hero/dashboards |

### Monospace Scale (Data)
| Token | Size/Line | Weight | Usage |
|-------|-----------|--------|-------|
| `--mono-xs` | 9px / 13px | 500 | +0.1em | Tiny badges, chips |
| `--mono-sm` | 10px / 14px | 500 | +0.08em | Counts, IDs, timestamps |
| `--mono-base` | 11px / 16px | 500 | +0.04em | Default data |
| `--mono-lg` | 13px / 20px | 600 | 0 | Emphasis numbers |
| `--mono-xl` | 18px / 26px | 700 | -0.01em | Hero metrics |

---

## SPACING RHYTHM

### Base Unit: 4px
All spacing is multiples of 4px. No arbitrary values.

| Token | Value | Usage |
|-------|-------|-------|
| `--space-0` | 0 | Reset |
| `--space-1` | 4px | Micro (icon gaps, inline) |
| `--space-2` | 8px | Tight (control gaps) |
| `--space-3` | 12px | Compact (card padding) |
| `--space-4` | 16px | Standard (section gaps) |
| `--space-5` | 20px | Comfortable (panel padding) |
| `--space-6` | 24px | Generous (page margins) |
| `--space-8` | 32px | Section separation |
| `--space-10` | 40px | Major sections |
| `--space-12` | 48px | Hero spacing |

### Layout Grid
- **Content max-width:** 1440px (dense command center)
- **Sidebar width:** 280px (expanded) / 56px (collapsed)
- **Top bar height:** 44px
- **Bottom bar height:** 36px
- **Panel border radius:** 8px (cards), 6px (dense), 4px (chips)
- **Focus ring:** 2px solid var(--cc-blue), offset 1px

---

## MOTION SYSTEM

### Durations
| Token | Value | Usage |
|-------|-------|-------|
| `--duration-instant` | 0ms | State toggles |
| `--duration-fast` | 100ms | Hover, focus |
| `--duration-base` | 160ms | Panel expand, tabs |
| `--duration-slow` | 240ms | Modal, drawer |
| `--duration-slower` | 320ms | Page transitions |

### Easings
| Token | Curve | Usage |
|-------|-------|-------|
| `--ease-standard` | cubic-bezier(0.4, 0, 0.2, 1) | Default |
| `--ease-emphasized` | cubic-bezier(0.2, 0, 0, 1) | Entrance |
| `--ease-decelerate` | cubic-bezier(0, 0, 0.2, 1) | Exit |
| `--ease-spring` | cubic-bezier(0.34, 1.56, 0.64, 1) | Playful (rare) |

### Motion Rules
- **Respect `prefers-reduced-motion`** — all animations disabled
- **No auto-playing** video/GIF without user action
- **Panel transitions** — opacity + transform Y(4px) on mount
- **Hover states** — background color only, no transform
- **Loading skeletons** — subtle pulse (1.5s ease-in-out)

---

## COMPONENT SPECIFICATIONS

### 1. Panel (Surface)
```tsx
// Three densities
<Panel density="comfortable">  // p-5, gap-4
<Panel density="compact">      // p-3, gap-2  
<Panel density="dense">        // p-2, gap-1.5

// Variants
<Panel variant="default">      // bg-panel, border-line
<Panel variant="elevated">     // bg-panel2, shadow-sm, border-line/60
<Panel variant="subtle">       // bg-panel2, no border
```

### 2. Pill (Status Badge)
```tsx
<Pill tone="green" size="sm">ONLINE</Pill>      // accent bg/border
<Pill tone="amber" size="sm">PENDING</Pill>    // amber bg/border
<Pill tone="red" size="sm">ERROR</Pill>        // red bg/border
<Pill tone="blue" size="sm">INFO</Pill>        // blue bg/border
<Pill tone="dim" size="sm">IDLE</Pill>         // dim bg/border
```

### 3. SeverityChip
```tsx
<SevChip severity="HIGH" />    // red, bold
<SevChip severity="MEDIUM" />  // amber
<SevChip severity="LOW" />     // blue
<SevChip severity="INFO" />    // dim
```

### 4. Metric Card
```tsx
<Metric 
  label="People Detected" 
  value={42} 
  unit="tracks"
  tone="text"      // | "accent" | "red" | "amber" | "blue" | "dim"
  trend={{ value: "+12%", direction: "up" }}
  sparse={false}   // compact variant for dense grids
/>
```

### 5. Data Table
```tsx
<DataTable
  columns={[
    { key: 'time', header: 'Time', width: '120px', align: 'right', mono: true },
    { key: 'type', header: 'Event Type', width: '1fr' },
    { key: 'severity', header: 'Severity', width: '90px', render: SevChip },
    { key: 'source', header: 'Source', width: '140px', mono: true },
  ]}
  rows={events}
  sortKey="time"
  sortDir="desc"
  onSort={...}
  selection={selectedIds}
  onSelectionChange={...}
  density="compact"  // | "comfortable"
/>
```

### 6. Event Row (Timeline)
```tsx
<EventRow
  event={{
    id: 'evt_001',
    ts: '2026-09-25T14:30:22.123Z',
    type: 'ZONE_ENTRY',
    severity: 'HIGH',
    source_id: 'camera_north',
    zone_id: 'zone_perimeter_1',
    track_ids: [42, 43],
    direction: 'ENTRY',
    video_ts: 12.4,
    status: 'new' | 'acked'
  }}
  compact={false}
  onSelect={() => {}}
  onAcknowledge={() => {}}
/>
```

### 7. Live Feed
```tsx
<LiveFeed
  streamUrl="/api/stream.mjpg"
  fallbackUrl="/api/frame.jpg"
  overlayLayers={['detections', 'tracks', 'zones', 'faces']}
  stats={{ fps: 29.8, latency: 42, tracks: 12, detections: 18 }}
  compact={false}
  onLayerToggle={(layer, enabled) => {}}
/>
```

### 8. Map Viewport
```tsx
<GeoMap
  center={[34.0522, -118.2437]}
  zoom={14}
  cameras={[
    { id: 'cam_1', lat: 34.0522, lng: -118.2437, status: 'live', name: 'North Gate' }
  ]}
  sectors={[
    { id: 'sector_1', name: 'Sector Alpha', polygon: [...], color: '#3B82F6' }
  ]}
  events={[
    { id: 'evt_1', lat: 34.0525, lng: -118.2430, severity: 'HIGH', type: 'ZONE_ENTRY' }
  ]}
  onCameraSelect={(id) => {}}
  onEventSelect={(id) => {}}
  layerToggles={{ cameras: true, sectors: true, zones: true, heatmap: false, events: true }}
/>
```

### 9. Trajectory Canvas
```tsx
<TrajectoryCanvas
  trajectory={[{ x: 0.1, y: 0.2, t: 0 }, ...]}  // normalized 0-1
  isVehicle={false}
  size="sm"  // | "md" | "lg"
  showWaypoints={false}
  showDirection={true}
/>
```

### 10. Layer Toggles
```tsx
<LayerToggles
  layers={[
    { id: 'detections', label: 'Detections', enabled: true, color: '#3B82F6' },
    { id: 'tracks', label: 'Tracks', enabled: true, color: '#8B5CF6' },
    { id: 'zones', label: 'Zones', enabled: true, color: '#10B981' },
    { id: 'faces', label: 'Faces', enabled: false, color: '#F59E0B' },
  ]}
  onChange={(id, enabled) => {}}
  compact={false}
/>
```

---

## PAGE COMPOSITIONS

### 1. Dashboard (Command Center)
```
┌─────────────────────────────────────────────────────────────────┐
│ TOP BAR: TRINETRA | System Status | SSE | Session | Clock       │
├──────────┬──────────────────────────────────────────────────────┤
│ NAV      │  ┌─────────────────────────────────────────────────┐  │
│ ▦ Cmd    │  │ METRICS ROW (4 cards): People | Vehicles │       │
│ ◎ Live   │  │ Active Alerts | System Status                     │
│ ⚡ Alerts │  ├─────────────────────────────────────────────────┤  │
│ ≡ Log    │  │                                                 │  │
│ ⌕ Invest │  │         LIVE FEED (2.2fr)        │ Alerts (1fr)  │
│ ⌖ Map    │  │    [MJPEG stream + overlay]     │ [Timeline]    │
│ ∿ Analytics│  │                                                 │  │
│ ⬒ Sources │  ├─────────────────────────────────────────────────┤  │
│          │  │ ALERTS SUMMARY (4 severity chips)  │ AI SUMMARY  │
└──────────┴──────────────────────────────────────────────────────┘
│ BOTTOM BAR: Detector | Tracker | Pipeline | DB | Writer | Uptime│
```

### 2. Live View
```
┌─────────────────────────────────────────────────────────────────┐
│ TOP BAR                                                         │
├──────────┬──────────────────────────────────────────────────────┤
│ NAV      │  ┌─────────────────────────────────────────────────┐  │
│          │  │ FULL-SCREEN LIVE FEED (primary)                 │  │
│          │  │ [MJPEG + server-rendered annotations]           │  │
│          │  │ Header: Camera selector | Session pill | Stats  │  │
│          │  │ Footer: Layer toggles (5) | FPS/latency/tracks  │  │
│          │  └─────────────────────────────────────────────────┘  │
└──────────┴──────────────────────────────────────────────────────┘
│ BOTTOM BAR                                                      │
```

### 3. Alerts (Event Stream)
```
┌─────────────────────────────────────────────────────────────────┐
│ TOP BAR                                                         │
├──────────┬──────────────────────────────────────────────────────┤
│ NAV      │  ┌─────────────────────────────────────────────────┐  │
│          │  │ FILTER BAR: [ALL] [HIGH] [MED] [LOW] [INFO]     │  │
│          │  │         [Type ▼] [Source ▼] [● LIVE]            │  │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ EVENT LIST (scrollable, virtualized)            │  │
│          │  │ ┌─────────────────────────────────────────────┐  │  │
│          │  │ │ 14:30:22 │ 🔴 HIGH │ Zone Entry            │  │  │
│          │  │ │          │ camera_north │ zone_perim_1      │  │  │
│          │  │ │          │ track #42, #43 │ ENTRY │ v+12.4s │  │  │
│          │  │ ├─────────────────────────────────────────────┤  │  │
│          │  │ │ 14:28:45 │ 🟡 MED  │ Person Detected       │  │  │
│          │  │ └─────────────────────────────────────────────┘  │  │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ [LOAD OLDER 50]                                 │  │
│          │  └─────────────────────────────────────────────────┘  │
└──────────┴──────────────────────────────────────────────────────┘
│ BOTTOM BAR                                                      │
```

### 4. Event Log (Full History)
```
┌─────────────────────────────────────────────────────────────────┐
│ TOP BAR                                                         │
├──────────┬──────────────────────────────────────────────────────┤
│ NAV      │  ┌─────────────────────────────────────────────────┐  │
│          │  │ TOOLBAR: Search [________] | Filters: Severity  │  │
│          │  │         Type ▼ | Source ▼ | Date Range ▼ | Export│  │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ DATA TABLE (sortable, paginated, selectable)    │  │
│          │  │ ┌─────┬──────────┬────────┬────────┬────────┐    │  │
│          │  │ │ ☐   │ Time     │ Type   │ Sev    │ Source │    │  │
│          │  │ ├─────┼──────────┼────────┼────────┼────────┤    │  │
│          │  │ │ ☐   │ 14:30:22 │ Zone   │ 🔴 HIGH│ cam_n  │    │  │
│          │  │ │ ☐   │ 14:28:45 │ Person │ 🟡 MED │ cam_e  │    │  │
│          │  │ └─────┴──────────┴────────┴────────┴────────┘    │  │
│          │  │ Pagination: [← Prev]  1-50 of 1,247  [Next →]   │  │
│          │  └─────────────────────────────────────────────────┘  │
└──────────┴──────────────────────────────────────────────────────┘
│ BOTTOM BAR                                                      │
```

### 5. Investigation
```
┌─────────────────────────────────────────────────────────────────┐
│ TOP BAR                                                         │
├──────────┬──────────────────────────────────────────────────────┤
│ NAV      │  ┌──────────────┬──────────────────────────────────┐  │
│          │  │ SESSIONS     │ CLIP SUMMARY                     │  │
│          │  │ (300px)      │ [Stat grid: 6-12 cards]          │  │
│          │  │ ┌──────────┐  │                                  │  │
│          │  │ │ 14:30 ●  │  │ AUDIT TRAIL                      │  │
│          │  │ │ COMPLETED│  │ › Session started                │  │
│          │  │ │ cam_north│  │ › Zone Alpha breached            │  │
│          │  │ ├──────────┤  │ › 3 persons, 1 vehicle tracked   │  │
│          │  │ │ 12:15 ○  │  │ › Session completed cleanly      │  │
│          │  │ │ RUNNING  │  │                                  │  │
│          │  │ └──────────┘  └──────────────────────────────────┘  │
│          │  ├──────────────────────────────────────────────────┤  │
│          │  │ TRACKS TABLE (all flushed aggregates)            │  │
│          │  │ ┌────┬───────┬──────────┬────────┬────────┬────┐  │  │
│          │  │ │Track│ Class │Trajectory│ First  │ Last   │Frames│  │  │
│          │  │ ├────┼───────┼──────────┼────────┼────────┼────┤  │  │
│          │  │ │ #42 │ person│ ━━━━━━●  │ 14:28  │ 14:30  │  124 │  │  │
│          │  │ │ #43 │ car   │ ━━━━━━━● │ 14:28  │ 14:29  │   87 │  │  │
│          │  │ └────┴───────┴──────────┴────────┴────────┴────┘  │  │
│          │  └──────────────────────────────────────────────────┘  │
└──────────┴──────────────────────────────────────────────────────┘
│ BOTTOM BAR                                                      │
```

### 6. Map (Geography)
```
┌─────────────────────────────────────────────────────────────────┐
│ TOP BAR: [Satellite] [Standard] [Layers ▼]                     │
├──────────┬──────────────────────────────────────────────────────┤
│ NAV      │  ┌────────────────────────────┬────────────────────┐  │
│          │  │                            │ CAMERA INFO        │  │
│          │  │      GOOGLE MAP            │ (300px panel)      │  │
│          │  │  ● cam_north (LIVE)        │ ┌────────────────┐  │  │
│          │  │  ○ cam_east (IDLE)         │ │ Name: North Gate│  │  │
│          │  │  ⚠ cam_west (WARNING)      │ │ Status: LIVE    │  │  │
│          │  │  ▢ Sector Alpha (dashed)   │ │ Type: IP Camera │  │  │
│          │  │  ▢ Sector Bravo            │ │ Coords: 34.05,  │  │  │
│          │  │                            │ │      -118.24    │  │  │
│          │  │  🔴 HIGH event             │ ├────────────────┤  │  │
│          │  │  🟡 MED event              │ │ PLACEMENT       │  │  │
│          │  │                            │ │ Lat: [____]     │  │  │
│          │  │                            │ │ Lng: [____]     │  │  │
│          │  │                            │ │ Label: [____]   │  │  │
│          │  │                            │ │ [SET COORDS]    │  │  │
│          │  │                            │ └────────────────┘  │  │
│          │  ├────────────────────────────┼────────────────────┤  │
│          │  │ GEO SECTORS (CRUD)         │ CAMERA REGISTRY   │  │
│          │  │ ┌────────────────────────┐ │ (scrollable list) │  │
│          │  │ │ Sector Alpha    [Edit] │ │ ┌──────────────┐  │  │
│          │  │ │ Sector Bravo     [Edit] │ │ │ ● North Gate │  │  │
│          │  │ │ [+ Add Sector]         │ │ │ ○ East Fence │  │  │
│          │  │ └────────────────────────┘ │ │ ⚠ West Perim │  │  │
│          │  └────────────────────────────┴────────────────────┘  │
└──────────┴──────────────────────────────────────────────────────┘
│ BOTTOM BAR                                                      │
```

### 7. Analytics
```
┌─────────────────────────────────────────────────────────────────┐
│ TOP BAR: [1H] [6H] [24H] [7D]                                  │
├──────────┬──────────────────────────────────────────────────────┤
│ NAV      │  ┌─────────────────────────────────────────────────┐  │
│          │  │ RUNTIME PANEL (13 metric cards, 2 rows)         │  │
│          │  │ People | Vehicles | Tracks | FPS | Frames | Dev │  │
│          │  │ Uptime | Active Ppl | Active Veh | Total Trks   │  │
│          │  │ Trajectory Depth | Active Zones | Events Committed│ │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ VISUALIZATION CONTROLS (LayerToggles)           │  │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ EVENTS BY TYPE (horizontal bars, top 12)        │  │
│          │  │ Zone Entry      ████████████████████  234       │  │
│          │  │ Person Detected ████████████████       189       │  │
│          │  │ Vehicle Detected████████████           145       │  │
│          │  │ ...                                                   │  │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ ACTIVITY BY HOUR (24-bar histogram)             │  │
│          │  │ 00 01 02 03 04 05 06 07 08 09 10 11 12 13 14... │  │
│          │  │ ▁  ▁  ▁  ▁  ▁  ▂  ▃  ▅  ▇  ▆  ▅  ▄  ▃  ▂  ▁ ... │  │
│          │  └─────────────────────────────────────────────────┘  │
└──────────┴──────────────────────────────────────────────────────┘
│ BOTTOM BAR                                                      │
```

### 8. Sources (Camera Management)
```
┌─────────────────────────────────────────────────────────────────┐
│ TOP BAR: [+ Add Source]                                        │
├──────────┬──────────────────────────────────────────────────────┤
│ NAV      │  ┌─────────────────────────────────────────────────┐  │
│          │  │ STATS: Total: 8 | ● 5 | ⚠ 1 | ○ 2               │  │
│          │  │ FILTERS: [Status ▼] [Type ▼]                    │  │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ SOURCE CARDS (scrollable list)                  │  │
│          │  │ ┌─────────────────────────────────────────────┐  │  │
│          │  │ │ 📷 North Gate Camera          ● ONLINE      │  │  │
│          │  │ │ IP Camera • 1920x1080 @ 30fps • H.264       │  │  │
│          │  │ │ Zone: Zone A | Codec: H.264                 │  │  │
│          │  │ │ rtsp://192.168.1.100:554/stream1       [ON] │  │  │
│          │  │ ├─────────────────────────────────────────────┤  │  │
│          │  │ │ 📷 East Fence Camera          ● ONLINE      │  │  │
│          │  │ │ IP Camera • 1920x1080 @ 30fps • H.264       │  │  │
│          │  │ │ Zone: Zone B | Codec: H.264                 │  │  │
│          │  │ │ rtsp://192.168.1.101:554/stream1       [ON] │  │  │
│          │  │ ├─────────────────────────────────────────────┤  │  │
│          │  │ │ 💻 Building A Webcam          ⚠ WARNING    │  │  │
│          │  │ │ Webcam • 1280x720 @ 30fps • MJPEG           │  │  │
│          │  │ │ Zone: Zone A | Codec: MJPEG                 │  │  │
│          │  │ │ webcam://0                            [ON]  │  │  │
│          │  │ └─────────────────────────────────────────────┘  │  │
│          │  └─────────────────────────────────────────────────┘  │
└──────────┴──────────────────────────────────────────────────────┘
│ BOTTOM BAR                                                      │
```

### 9. Settings (New Page)
```
┌─────────────────────────────────────────────────────────────────┐
│ TOP BAR: [Save Changes]                                        │
├──────────┬──────────────────────────────────────────────────────┤
│ NAV      │  ┌─────────────────────────────────────────────────┐  │
│          │  │ GENERAL                                         │  │
│          │  │ ├─ Auto-start Session          [ ]              │  │
│          │  │ ├─ Session Timeout (min)       [30]             │  │
│          │  │ ├─ Default Camera              [North Gate ▼]   │  │
│          │  │ ├─ Language                    [English ▼]      │  │
│          │  │ └─ Timezone                    [UTC ▼]          │  │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ ANALYTICS THRESHOLDS                            │  │
│          │  │ ├─ Running Speed (m/s)         [4.0]            │  │
│          │  │ ├─ Loitering Duration (sec)    [300]            │  │
│          │  │ ├─ Crowd Density (per 50m²)    [10]             │  │
│          │  │ └─ Zone Entry Cooldown (sec) [10]               │  │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ RE-ID CONFIGURATION                             │  │
│          │  │ ├─ Enable Re-ID                  [●]            │  │
│          │  │ ├─ Similarity Threshold (0-1)  [0.75]           │  │
│          │  │ ├─ Max Gallery Size            [1000]           │  │
│          │  │ └─ Cross-Camera Window (sec)   [30]             │  │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ NOTIFICATIONS                                   │  │
│          │  │ ├─ Email Alerts                  [●]            │  │
│          │  │ ├─ SMS Alerts                    [ ]            │  │
│          │  │ ├─ Push Notifications            [●]            │  │
│          │  │ ├─ Min Alert Severity          [MEDIUM ▼]       │  │
│          │  │ └─ Notification Cooldown (sec) [60]             │  │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ VIDEO & RECORDING                               │  │
│          │  │ ├─ Stream Quality (%)          [80]             │  │
│          │  │ ├─ Target FPS                  [30]             │  │
│          │  │ ├─ Enable Recording            [●]              │  │
│          │  │ ├─ Retention (days)            [7]              │  │
│          │  │ └─ Snapshot on Event         [●]              │  │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ SYSTEM (read-only)                              │  │
│          │  │ Model Path: /models/yolov8n.onnx                │  │
│          │  │ Face Model: /models/face_detector.onnx          │  │
│          │  │ Database: ./data/trinetra.db                    │  │
│          │  │ Log Level: info                                 │  │
│          │  │ API Port: 8000                                  │  │
│          │  ├─────────────────────────────────────────────────┤  │
│          │  │ ⚠️ DANGER ZONE                                  │  │
│          │  │ [Reset All Settings] [Clear All Data] [Restart] │  │
│          │  └─────────────────────────────────────────────────┘  │
└──────────┴──────────────────────────────────────────────────────┘
│ BOTTOM BAR                                                      │
```

---

## RESPONSIVE BEHAVIOR

### Breakpoints
```css
--bp-sm:  640px   /* Mobile landscape */
--bp-md:  768px   /* Tablet portrait */
--bp-lg:  1024px  /* Tablet landscape / small laptop */
--bp-xl:  1280px  /* Laptop */
--bp-2xl: 1536px  /* Desktop */
```

### Layout Adaptations
| Breakpoint | Nav | Content Grid | Panels |
|------------|-----|--------------|--------|
| `< 768px` | Collapsible drawer (hamburger) | Single column | Full width, stacked |
| `768-1024px` | Collapsible (icon-only default) | 2-col where appropriate | Side-by-side on wide |
| `> 1024px` | Persistent expanded | 3-col dashboard, 2-col others | As designed |

### Component Responsiveness
- **Metric cards:** 4-col → 2-col → 1-col
- **Data tables:** Horizontal scroll on `< 1024px`, sticky first col
- **Live Feed:** 100% width, 16:9 aspect ratio maintained
- **Map:** 100% width, fixed min-height 400px
- **Charts:** Resize with container, maintain aspect

---

## ACCESSIBILITY

### WCAG 2.1 AA Compliance
- **Contrast:** All text ≥ 4.5:1 (UI ≥ 3:1)
- **Focus:** Visible 2px ring on all interactive elements
- **Keyboard:** Full tab order, logical flow, skip links
- **Screen Reader:** ARIA labels on all icon-only buttons, live regions for alerts
- **Color Blindness:** No red/green-only distinction; severity uses shape + text + color

### Semantic HTML
```tsx
// Top bar
<header role="banner">...</header>

// Navigation
<nav role="navigation" aria-label="Main navigation">...</nav>

// Main content
<main role="main">...</main>

// Live region for alerts
<div aria-live="polite" aria-atomic="true">...</div>

// Status bar
<footer role="contentinfo">...</footer>
```

---

## IMPLEMENTATION ROADMAP

### Phase 1: Foundation (Week 1)
1. ✅ **Tailwind config** — extend with full token system (light + dark)
2. ✅ **CSS variables** — define in `:root` and `[data-theme="dark"]`
3. ✅ **Base styles** — reset, scrollbars, focus rings, selection
4. **Theme provider** — context + localStorage persistence + system preference

### Phase 2: Core Primitives (Week 1-2)
5. **Panel** — 3 densities, 3 variants, scroll control
6. **Pill** — 5 tones, 2 sizes, icon support
7. **SevChip** — 4 severities, accessible markup
8. **Metric** — trend, tone, sparse variant
9. **Button** — primary/secondary/ghost, loading, sizes
10. **Input/Select** — consistent styling, error state
11. **DataTable** — virtualized, sortable, selectable, keyboard nav

### Phase 3: Domain Components (Week 2)
12. **LiveFeed** — MJPEG + snapshot fallback + layer toggles + stats overlay
13. **EventTimeline / EventRow** — live SSE + REST merge, severity, ack
14. **GeoMap** — Google Maps + camera markers + sectors + events
15. **TrajectoryCanvas** — animated path, start/end, vehicle/person
16. **LayerToggles** — toggle group with color indicators
17. **EventDetail** — side panel, acknowledge, export

### Phase 4: Pages (Week 2-3)
18. **Dashboard** — metrics → live feed + alerts → summary + AI
19. **Live View** — full-screen feed, camera selector, layer toggles
20. **Alerts** — filterable stream, pagination, live badge
21. **Event Log** — searchable table, export, deep filters
22. **Investigation** — session picker → summary + audit trail → tracks table
23. **Map** — map viewport + sectors + camera registry + placement
24. **Analytics** — runtime panel → layer toggles → type/hour charts
25. **Sources** — source cards, add/edit dialog, test connection
26. **Settings** — 6 sections, danger zone, persistence

### Phase 5: Polish (Week 3)
27. **Dark mode** — complete implementation, no flash
28. **Micro-interactions** — hover, focus, loading skeletons, transitions
29. **Responsive** — test all breakpoints, fix layout breaks
30. **Accessibility audit** — axe, keyboard, screen reader
31. **Performance** — virtualize lists, memoize, code-split pages
32. **Documentation** — Storybook or component README

---

## DESIGN TOKENS (Tailwind Config)

```js
// tailwind.config.js
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        cc: {
          // Light (default)
          bg: '#F6F7F9',
          panel: '#FFFFFF',
          panel2: '#F2F4F6',
          line: '#E3E7EB',
          text: '#101418',
          dim: '#5C6672',
          accent: '#16A34A',
          red: '#DC2626',
          amber: '#D97706',
          blue: '#2563EB',
          // Dark (via .dark class)
          'bg-dark': '#0B0F14',
          'panel-dark': '#11171E',
          'panel2-dark': '#161D26',
          'line-dark': '#1E2834',
          'text-dark': '#E8EBF0',
          'dim-dark': '#7A8796',
          'accent-dark': '#22C55E',
          'red-dark': '#EF4444',
          'amber-dark': '#F59E0B',
          'blue-dark': '#3B82F6',
        },
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
        sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
      },
      fontSize: {
        'xs': ['10px', { lineHeight: '14px', letterSpacing: '0.08em' }],
        'sm': ['11px', { lineHeight: '16px', letterSpacing: '0.04em' }],
        'base': ['13px', { lineHeight: '20px' }],
        'lg': ['15px', { lineHeight: '24px' }],
        'xl': ['18px', { lineHeight: '28px', letterSpacing: '-0.01em', fontWeight: '500' }],
        '2xl': ['22px', { lineHeight: '32px', letterSpacing: '-0.02em', fontWeight: '600' }],
        '3xl': ['32px', { lineHeight: '40px', letterSpacing: '-0.03em', fontWeight: '600' }],
        'mono-xs': ['9px', { lineHeight: '13px', letterSpacing: '0.1em', fontWeight: '500' }],
        'mono-sm': ['10px', { lineHeight: '14px', letterSpacing: '0.08em', fontWeight: '500' }],
        'mono-base': ['11px', { lineHeight: '16px', letterSpacing: '0.04em', fontWeight: '500' }],
        'mono-lg': ['13px', { lineHeight: '20px', fontWeight: '600' }],
        'mono-xl': ['18px', { lineHeight: '26px', letterSpacing: '-0.01em', fontWeight: '700' }],
      },
      spacing: {
        '0': '0',
        '1': '4px',
        '2': '8px',
        '3': '12px',
        '4': '16px',
        '5': '20px',
        '6': '24px',
        '8': '32px',
        '10': '40px',
        '12': '48px',
      },
      borderRadius: {
        'sm': '4px',
        'md': '6px',
        'lg': '8px',
        'xl': '12px',
        'full': '9999px',
      },
      boxShadow: {
        'sm': '0 1px 2px 0 rgb(0 0 0 / 0.05)',
        'DEFAULT': '0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)',
        'md': '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
        'lg': '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
      },
      transitionDuration: {
        'instant': '0ms',
        'fast': '100ms',
        'base': '160ms',
        'slow': '240ms',
        'slower': '320ms',
      },
      transitionTimingFunction: {
        'standard': 'cubic-bezier(0.4, 0, 0.2, 1)',
        'emphasized': 'cubic-bezier(0.2, 0, 0, 1)',
        'decelerate': 'cubic-bezier(0, 0, 0.2, 1)',
      },
      animation: {
        'pulse-subtle': 'pulse-subtle 1.5s ease-in-out infinite',
        'fade-in': 'fade-in 160ms ease-out',
        'slide-up': 'slide-up 160ms ease-out',
        'slide-down': 'slide-down 160ms ease-out',
      },
      keyframes: {
        'pulse-subtle': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-down': {
          '0%': { opacity: '0', transform: 'translateY(-4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
```

---

## CSS VARIABLES (index.css)

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  /* Light mode (default) */
  --cc-bg: #F6F7F9;
  --cc-panel: #FFFFFF;
  --cc-panel2: #F2F4F6;
  --cc-line: #E3E7EB;
  --cc-text: #101418;
  --cc-dim: #5C6672;
  --cc-accent: #16A34A;
  --cc-red: #DC2626;
  --cc-amber: #D97706;
  --cc-blue: #2563EB;
  
  /* State overlays */
  --cc-accent-bg: rgba(22, 163, 74, 0.08);
  --cc-red-bg: rgba(220, 38, 38, 0.08);
  --cc-amber-bg: rgba(217, 119, 6, 0.08);
  --cc-blue-bg: rgba(37, 99, 235, 0.08);
}

.dark {
  --cc-bg: #0B0F14;
  --cc-panel: #11171E;
  --cc-panel2: #161D26;
  --cc-line: #1E2834;
  --cc-text: #E8EBF0;
  --cc-dim: #7A8796;
  --cc-accent: #22C55E;
  --cc-red: #EF4444;
  --cc-amber: #F59E0B;
  --cc-blue: #3B82F6;
  
  --cc-accent-bg: rgba(34, 197, 94, 0.12);
  --cc-red-bg: rgba(239, 68, 68, 0.12);
  --cc-amber-bg: rgba(245, 158, 11, 0.12);
  --cc-blue-bg: rgba(59, 130, 246, 0.12);
}

/* Base */
html, body, #root {
  height: 100%;
  background: var(--cc-bg);
  color: var(--cc-text);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Scrollbars */
*::-webkit-scrollbar { width: 8px; height: 8px; }
*::-webkit-scrollbar-track { background: transparent; }
*::-webkit-scrollbar-thumb { background: var(--cc-line); border-radius: 4px; }
*::-webkit-scrollbar-thumb:hover { background: var(--cc-dim); }

/* Focus rings */
:focus-visible {
  outline: 2px solid var(--cc-blue);
  outline-offset: 1px;
  border-radius: 2px;
}

/* Selection */
::selection {
  background: var(--cc-blue);
  color: white;
}

/* Severity chips (light) */
.sev-INFO    { color: var(--cc-dim); border-color: var(--cc-line); }
.sev-LOW     { color: var(--cc-blue); border-color: var(--cc-blue); }
.sev-MEDIUM  { color: var(--cc-amber); border-color: var(--cc-amber); }
.sev-HIGH    { color: var(--cc-red); border-color: var(--cc-red); font-weight: 600; }

/* Dark mode severity overrides */
.dark .sev-INFO    { color: var(--cc-dim); border-color: var(--cc-line); }
.dark .sev-LOW     { color: var(--cc-blue); border-color: var(--cc-blue); }
.dark .sev-MEDIUM  { color: var(--cc-amber); border-color: var(--cc-amber); }
.dark .sev-HIGH    { color: var(--cc-red); border-color: var(--cc-red); font-weight: 600; }

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

---

## HANDOFF TO ORION

### Files to Create/Modify

| File | Action | Priority |
|------|--------|----------|
| `tailwind.config.js` | Replace with full token config | P0 |
| `src/index.css` | Replace with CSS variables + base styles | P0 |
| `src/components/ui.tsx` | Rewrite with full component library | P0 |
| `src/components/LiveFeed.tsx` | Enhance with layer toggles, stats overlay | P0 |
| `src/components/EventTimeline.tsx` | Polish EventRowView, add virtualization | P0 |
| `src/components/GeoMap.tsx` | Add layer toggles, event markers, sector editing | P1 |
| `src/components/TrajectoryCanvas.tsx` | New component | P1 |
| `src/components/LayerToggles.tsx` | New component | P1 |
| `src/components/DataTable.tsx` | New component | P1 |
| `src/pages/Dashboard.tsx` | Refine layout, densities, real data | P0 |
| `src/pages/Cameras.tsx` (Live View) | Full-screen feed, camera selector | P0 |
| `src/pages/Events.tsx` | Filter bar, pagination, density | P0 |
| `src/pages/EventLog.tsx` | DataTable, export, deep filters | P1 |
| `src/pages/Investigation.tsx` | Session picker, audit trail, tracks table | P1 |
| `src/pages/Geography.tsx` | Map + sectors + registry + placement | P1 |
| `src/pages/Analytics.tsx` | Runtime panel, layer toggles, real charts | P1 |
| `src/pages/Sources.tsx` | Source cards, add/edit dialog, test | P1 |
| `src/pages/Settings.tsx` | **NEW** — 6 sections, danger zone | P1 |
| `src/App.tsx` | Add Settings to NAV, theme provider | P0 |
| `src/store.ts` | Add theme state, theme actions | P0 |
| `src/hooks/useTheme.ts` | **NEW** — theme context hook | P0 |

### Coordination Notes
- **Apollo**: Architecture review of Settings page API contracts
- **Juno**: Validate all 25+ endpoints still work with new UI
- **Orion**: Implementation lead — I'll provide component specs as you build

---

## VALIDATION CHECKLIST

### Visual QA
- [ ] Light mode: all contrasts ≥ 4.5:1
- [ ] Dark mode: all contrasts ≥ 4.5:1
- [ ] No hardcoded colors — all semantic tokens
- [ ] Consistent 4px spacing rhythm everywhere
- [ ] Monospace used for ALL data (counts, IDs, timestamps, coords)
- [ ] Proportional used for ALL labels/narrative
- [ ] Severity colors consistent across all pages
- [ ] Focus rings visible on every interactive element
- [ ] Loading skeletons match final layout

### Functional QA
- [ ] Theme toggle persists + respects system preference
- [ ] Live feed: MJPEG + snapshot fallback works
- [ ] Layer toggles control server render layers
- [ ] Event stream: SSE live + REST backfill merge
- [ ] Event Log: sort, filter, paginate, export
- [ ] Map: camera click → info panel, placement works
- [ ] Investigation: session pick → tracks table renders
- [ ] Analytics: runtime panel updates live
- [ ] Sources: add/edit/delete, test connection
- [ ] Settings: all fields persist, danger zone confirms

### Performance
- [ ] Virtualized lists for >100 rows
- [ ] Memoized derived state (useMemo)
- [ ] Code-split pages (React.lazy)
- [ ] Bundle size < 300KB JS gzipped
- [ ] No layout shift on theme toggle

---

**STATUS:** SPECIFICATION COMPLETE — READY FOR IMPLEMENTATION  
**NEXT:** Begin Phase 1 with Orion on Tailwind config + CSS variables + ThemeProvider