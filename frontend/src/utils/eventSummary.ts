// EventSummary Generator — Deterministic Structured Event Summaries (V3.5 / Phase 6).
// Answers WHAT / WHO / WHERE / WHEN / MOVEMENT / WHY / EVIDENCE from real data.
// Every absent field is explicitly labeled 'Not available'.
// Deterministic — same event, same summary.

import type { EventRow, EventSummaryData, GeoCamera, GeoSector, ZoneRow } from '../types';
import { eventTypeLabel } from '../components/ui';
import { pointInSector } from '../components/EventDetail';

export function buildEventSummary(
  e: EventRow,
  zones: ZoneRow[] = [],
  cameras: GeoCamera[] = [],
  sectors: GeoSector[] = [],
): EventSummaryData {
  // 1. WHAT
  const typeLabel = eventTypeLabel(e.type);
  const confPct = `${(e.confidence * 100).toFixed(1)}%`;
  const what = `${e.type} (${e.severity} severity, ${confPct} confidence)`;

  // 2. WHO
  const trackIds = e.track_ids || [];
  const trackStr = trackIds.length > 0 ? trackIds.map(t => `Track #${t}`).join(', ') : 'Not available (no track binding)';

  const globalPid = e.metadata?.global_person_id as string | undefined;
  const identityCameras = e.metadata?.identity_cameras as string[] | undefined;
  let reidStr = 'Re-ID: Not available';
  if (globalPid) {
    const cams = identityCameras?.length ? `seen on ${identityCameras.join(', ')}` : 'cross-camera match';
    reidStr = `Re-ID Identity: ${globalPid} (${cams})`;
  }
  const who = trackIds.length > 0 ? `${trackStr} | ${reidStr}` : 'Not available (no track binding)';

  // 3. WHERE
  const cam = cameras.find(c => c.camera_id === e.source_id);
  const sourceLabel = cam?.label || e.source_id;
  const coordsStr = cam?.has_coordinates && cam.latitude != null && cam.longitude != null
    ? `Coords: ${cam.latitude.toFixed(4)}, ${cam.longitude.toFixed(4)}`
    : 'Coords: Not available';

  let zoneName: string | null = null;
  let zoneKind: string | null = null;
  let zoneType: string | null = null;
  let zoneStr = 'Zone: Not available';
  if (e.zone_id) {
    const z = zones.find(z => z.id === e.zone_id);
    if (z) {
      zoneName = z.name || z.id;
      zoneKind = z.kind;
      zoneType = z.zone_type;
      zoneStr = `Zone: ${zoneName} (${z.kind}, ${z.zone_type})`;
    } else {
      zoneStr = `Zone: ${e.zone_id} (deleted zone)`;
    }
  }

  const containingSectors = cam?.has_coordinates && cam.latitude != null && cam.longitude != null
    ? sectors
        .filter(s => s.active && s.polygon?.length >= 3)
        .filter(s => pointInSector(cam.latitude!, cam.longitude!, s.polygon))
        .map(s => s.name)
    : [];

  const geoSectorStr = cam?.has_coordinates
    ? containingSectors.length > 0
      ? `Geo Sector: ${containingSectors.join(', ')}`
      : 'Geo Sector: None containing camera'
    : 'Geo Sector: Not available (camera unplaced)';

  const where = `Source: ${sourceLabel} | ${coordsStr} | ${zoneStr} | ${geoSectorStr}`;

  // 4. WHEN
  const tsFormatted = e.ts;
  const vtsStr = e.video_ts != null ? `+${e.video_ts.toFixed(2)}s` : 'Not available';
  const nightStr = e.is_night ? 'Active' : 'Inactive';
  const when = `Time: ${tsFormatted} | Video offset: ${vtsStr} | Night mode: ${nightStr}`;

  // 5. MOVEMENT
  const dirStr = e.direction ? e.direction : 'Not available';
  const meta = e.metadata || {};
  const kinParts: string[] = [];
  if (meta.velocity != null) kinParts.push(`velocity: ${Number(meta.velocity).toFixed(1)}px/s`);
  if (meta.acceleration != null) kinParts.push(`accel: ${Number(meta.acceleration).toFixed(1)}px/s²`);
  if (meta.straightness != null) kinParts.push(`straightness: ${Number(meta.straightness).toFixed(2)}`);
  if (meta.dwell_time != null) kinParts.push(`dwell: ${Number(meta.dwell_time).toFixed(1)}s`);
  if (meta.person_count != null) kinParts.push(`count: ${meta.person_count}`);

  const kinStr = kinParts.length > 0 ? `Kinematics: ${kinParts.join(', ')}` : 'Kinematics: Not available';
  const movement = `Direction: ${dirStr} | ${kinStr}`;

  // 6. WHY
  const sevReason = (e.metadata?.severity_reason || e.severity_reason) as string | undefined;
  let why = '';
  if (sevReason) {
    why = sevReason;
  } else {
    const reasons: string[] = [`Triggered by ${e.type} event rule`];
    if (e.is_night) reasons.push('night-time detection policy (+1 severity)');
    if (zoneType === 'RESTRICTED') reasons.push('restricted perimeter escalation (+1 severity)');
    why = `${reasons.join('; ')}.`;
  }

  // 7. EVIDENCE
  let evidence = '';
  let snapshotAvailable = false;
  let skipReason: string | null = null;
  if (e.snapshot_path) {
    evidence = `Snapshot available (${e.snapshot_path})`;
    snapshotAvailable = true;
  } else if (e.metadata?.snapshot_skipped_low_disk) {
    evidence = 'Snapshot skipped — low disk threshold';
    skipReason = 'low_disk';
  } else {
    evidence = 'Not available (no evidence registered for this event)';
    skipReason = 'none_registered';
  }

  // Multi-clause narrative
  const narrative = `At ${e.ts}, ${what} was detected on ${sourceLabel}. Who: ${who}. Location: ${zoneStr}, ${coordsStr}, ${geoSectorStr}. Movement: ${movement}. Assessment: ${why} Evidence: ${evidence}.`;

  return {
    event_id: e.id,
    session_id: e.session_id,
    source_id: e.source_id,
    what,
    who,
    where,
    when,
    movement,
    why,
    evidence,
    narrative,
    structured: {
      what: {
        type: e.type,
        label: typeLabel,
        severity: e.severity,
        confidence: e.confidence,
      },
      who: {
        track_ids: trackIds,
        class_names: trackIds.map(() => 'target'),
        identity: globalPid || null,
        identity_cameras: identityCameras || [],
      },
      where: {
        source_id: e.source_id,
        source_label: sourceLabel,
        coordinates: cam?.has_coordinates && cam.latitude != null && cam.longitude != null
          ? { latitude: cam.latitude, longitude: cam.longitude }
          : null,
        zone_id: e.zone_id,
        zone_name: zoneName,
        zone_kind: zoneKind,
        zone_type: zoneType,
        geo_sectors: containingSectors,
      },
      when: {
        ts: e.ts,
        video_ts: e.video_ts,
        is_night: e.is_night,
      },
      movement: {
        direction: e.direction,
        kinematics: kinParts.length > 0 ? meta : null,
      },
      why: {
        severity_reason: sevReason || null,
        summary: why,
      },
      evidence: {
        snapshot_path: e.snapshot_path,
        snapshot_available: snapshotAvailable,
        skip_reason: skipReason,
      },
    },
  };
}
