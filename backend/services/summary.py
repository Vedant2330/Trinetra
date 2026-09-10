"""TRINETRA Summary Service — Deterministic Session & Event Summaries (V3.5 / Phase 5 & 6).

Generates factual, structured audit summaries computed solely from database
rows (sessions, tracks, events, zones, sources, geo sectors) and session metrics
without LLM hallucinations.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from backend.db.dao import DAO

log = logging.getLogger("trinetra.services.summary")

_VEHICLE_CLASSES = frozenset({"car", "truck", "bus", "motorcycle", "bicycle"})


def point_in_sector(lat: float, lng: float, polygon: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon algorithm over [[lat, lng], ...] geographic coordinates."""
    if not polygon or len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    for i in range(n):
        j = (i - 1) % n
        lat_i, lng_i = polygon[i][0], polygon[i][1]
        lat_j, lng_j = polygon[j][0], polygon[j][1]
        denom = (lat_j - lat_i) if (lat_j != lat_i) else 1e-12
        intersects = ((lat_i > lat) != (lat_j > lat)) and (
            lng < (lng_j - lng_i) * (lat - lat_i) / denom + lng_i
        )
        if intersects:
            inside = not inside
    return inside


def _parse_iso(ts_str: Optional[str]) -> Optional[datetime]:
    if not ts_str:
        return None
    try:
        clean_str = ts_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is not None:
            # normalize to naive UTC datetime for arithmetic comparison
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _calculate_max_concurrent(tracks: list[Any], class_filter: Optional[frozenset[str]] = None, single_class: Optional[str] = None) -> int:
    """Compute peak concurrent active tracks from first_seen/last_seen intervals."""
    intervals: list[tuple[str, int]] = []
    for t in tracks:
        cname = t["class_name"] if isinstance(t, dict) or hasattr(t, "__getitem__") else getattr(t, "class_name", "")
        match = False
        if single_class and cname == single_class:
            match = True
        elif class_filter and cname in class_filter:
            match = True
        elif not single_class and not class_filter:
            match = True

        if match:
            f_seen = t["first_seen"] if isinstance(t, dict) or hasattr(t, "__getitem__") else getattr(t, "first_seen", "")
            l_seen = t["last_seen"] if isinstance(t, dict) or hasattr(t, "__getitem__") else getattr(t, "last_seen", "")
            if f_seen and l_seen:
                intervals.append((str(f_seen), 1))
                intervals.append((str(l_seen), -1))
    # Sort: arrivals before departures if timestamps are equal
    intervals.sort(key=lambda x: (x[0], -x[1]))
    curr = 0
    max_c = 0
    for _, delta in intervals:
        curr += delta
        if curr > max_c:
            max_c = curr
    return max_c


def generate_session_summary(dao: DAO, session_id: str) -> Optional[dict[str, Any]]:
    """Compute deterministic session summary dictionary from database rows.

    Returns None if session does not exist.
    If session is not finalized / still running, returns partial summary with honest status.
    """
    session_row = dao.get_session(session_id)
    if session_row is None:
        return None

    source_id = session_row["source_id"]
    status = session_row["status"]
    started_at = session_row["started_at"]
    ended_at = session_row["ended_at"]

    source_row = dao.get_source(source_id) if source_id else None
    source_name = source_row["name"] if source_row and "name" in source_row.keys() and source_row["name"] else (
        source_row["label"] if source_row and "label" in source_row.keys() and source_row["label"] else source_id
    )

    stats = {}
    if session_row["stats"]:
        try:
            stats = json.loads(session_row["stats"])
        except Exception:
            stats = {}

    # 1. Frames and Duration
    frames = stats.get("frames_processed", 0)
    duration_s = 0.0

    start_dt = _parse_iso(started_at)
    end_dt = _parse_iso(ended_at)
    if start_dt and end_dt:
        duration_s = max(0.0, (end_dt - start_dt).total_seconds())

    # 2. Tracks Breakdown
    track_rows = dao.get_tracks(session_id)
    unique_tracks = len(track_rows)
    people_detected = 0
    vehicles_detected = 0

    for t in track_rows:
        cname = t["class_name"]
        if cname == "person":
            people_detected += 1
        elif cname in _VEHICLE_CLASSES:
            vehicles_detected += 1

    other_tracks = max(0, unique_tracks - people_detected - vehicles_detected)
    max_concurrent_people = _calculate_max_concurrent(track_rows, single_class="person")
    max_concurrent_vehicles = _calculate_max_concurrent(track_rows, class_filter=_VEHICLE_CLASSES)

    # 3. Events Breakdown
    event_rows = dao.query_events(session_id=session_id, limit=5000)
    events_by_severity: dict[str, int] = {}
    events_by_type: dict[str, int] = {}
    zones_breached_set: set[str] = set()

    for e in event_rows:
        sev = e["severity"] or "UNKNOWN"
        etype = e["type"] or "UNKNOWN"
        events_by_severity[sev] = events_by_severity.get(sev, 0) + 1
        events_by_type[etype] = events_by_type.get(etype, 0) + 1
        if e["zone_id"]:
            zones_breached_set.add(e["zone_id"])

    zones_breached = sorted(list(zones_breached_set))
    first_event_ts = event_rows[0]["ts"] if event_rows else None
    last_event_ts = event_rows[-1]["ts"] if event_rows else None

    # Geo Resolution
    lat = source_row["latitude"] if (source_row and "latitude" in source_row.keys()) else None
    lng = source_row["longitude"] if (source_row and "longitude" in source_row.keys()) else None
    geo_sector = None
    if lat is not None and lng is not None and dao._has_geo_sectors():
        all_sectors = dao.geo_sectors_rows()
        for sec in all_sectors:
            is_active = bool(sec["active"]) if "active" in sec.keys() else True
            if is_active:
                try:
                    poly = json.loads(sec["polygon"])
                    if point_in_sector(lat, lng, poly):
                        geo_sector = sec["name"]
                        break
                except Exception:
                    pass

    critical_events = events_by_severity.get("CRITICAL", 0)
    warning_events = events_by_severity.get("WARNING", 0) + events_by_severity.get("HIGH", 0)
    info_events = events_by_severity.get("INFO", 0) + events_by_severity.get("LOW", 0)
    threat_level = "CRITICAL" if critical_events > 0 else ("WARNING" if warning_events > 0 else "NORMAL")

    fps_val = stats.get("pipeline_fps", 0.0)
    if fps_val == 0.0 and duration_s > 0 and frames > 0:
        fps_val = round(frames / duration_s, 2)

    # 4. Factual Template-Generated Notes
    notes: list[str] = []
    notes.append(
        f"Session '{session_id}' on source '{source_name or source_id}' ({status}): "
        f"{frames} frames processed in {duration_s:.1f}s."
    )
    notes.append(
        f"Tracks recorded: {unique_tracks} total ({people_detected} people, "
        f"{vehicles_detected} vehicles, max concurrent people: {max_concurrent_people})."
    )

    if event_rows:
        high_crit_count = critical_events + events_by_severity.get("HIGH", 0)
        notes.append(
            f"Events summary: {len(event_rows)} total events across {len(events_by_type)} categories "
            f"({high_crit_count} high/critical priority)."
        )
        if zones_breached:
            notes.append(f"Monitored zones with activity: {', '.join(zones_breached)}.")

        # Notable high-severity event callouts (max 3)
        notable = [e for e in event_rows if e["severity"] in ("CRITICAL", "HIGH")][:3]
        for ne in notable:
            vts = f" at video_ts {ne['video_ts']:.1f}s" if ne["video_ts"] is not None else ""
            zone_info = f" in zone '{ne['zone_id']}'" if ne["zone_id"] else ""
            notes.append(f"Security Alert: {ne['type']} ({ne['severity']}){zone_info}{vts}.")
    else:
        notes.append("No security events triggered during this session.")

    return {
        "session_id": session_id,
        "source_id": source_id,
        "source_name": source_name,
        "status": status,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_s": duration_s,
        "frames_processed": frames,
        "frames": frames,
        "fps": fps_val,
        "people_detected": people_detected,
        "vehicles_detected": vehicles_detected,
        "unique_tracks": unique_tracks,
        "events_by_severity": events_by_severity,
        "events_by_type": events_by_type,
        "zones_breached": zones_breached,
        "max_concurrent_people": max_concurrent_people,
        "first_event_ts": first_event_ts,
        "last_event_ts": last_event_ts,
        "tracks_summary": {
            "total_tracks": unique_tracks,
            "person_tracks": people_detected,
            "vehicle_tracks": vehicles_detected,
            "other_tracks": other_tracks,
            "max_concurrent_persons": max_concurrent_people,
            "max_concurrent_vehicles": max_concurrent_vehicles,
        },
        "events_summary": {
            "total_events": len(event_rows),
            "critical": critical_events,
            "warning": warning_events,
            "info": info_events,
            "by_type": events_by_type,
        },
        "geographic": {
            "source_id": source_id,
            "latitude": lat,
            "longitude": lng,
            "sector": geo_sector,
            "threat_level": threat_level,
        },
        "notes": notes,
        "narrative": " ".join(notes),
        "structured": {
            "session_id": session_id,
            "duration_s": duration_s,
            "frames": frames,
            "fps": fps_val,
            "tracks": {
                "total": unique_tracks,
                "people": people_detected,
                "vehicles": vehicles_detected,
                "other": other_tracks,
                "max_concurrent_people": max_concurrent_people,
                "max_concurrent_vehicles": max_concurrent_vehicles,
            },
            "events": {
                "total": len(event_rows),
                "by_severity": events_by_severity,
                "by_type": events_by_type,
                "zones": zones_breached,
            },
        },
    }


def generate_event_summary(dao: DAO, event_id: str) -> Optional[dict[str, Any]]:
    """Compute structured-template summary answering WHAT/WHO/WHERE/WHEN/MOVEMENT/WHY/EVIDENCE

    Computed purely from real database rows (EventRow + tracks + zones + source + geo sectors).
    Every absent field is explicitly labeled 'Not available'.
    Deterministic — same event, same summary.
    """
    event_row = dao.get_event(event_id)
    if event_row is None:
        return None

    session_id = event_row["session_id"]
    source_id = event_row["source_id"]
    ts = event_row["ts"]
    video_ts = event_row["video_ts"]
    event_type = event_row["type"] or "UNKNOWN_EVENT"
    severity = event_row["severity"] or "INFO"
    confidence = float(event_row["confidence"] if event_row["confidence"] is not None else 1.0)
    zone_id = event_row["zone_id"]
    direction = event_row["direction"]
    is_night = bool(event_row["is_night"])
    snapshot_path = event_row["snapshot_path"]
    status = event_row["status"]

    track_ids: list[int] = []
    if event_row["track_ids"]:
        try:
            track_ids = json.loads(event_row["track_ids"])
        except Exception:
            track_ids = []

    metadata: dict[str, Any] = {}
    if event_row["metadata"]:
        try:
            metadata = json.loads(event_row["metadata"])
        except Exception:
            metadata = {}

    # 1. WHAT (Event type, severity level, confidence percentage)
    type_label = event_type.replace("_", " ").title()
    conf_pct = f"{confidence * 100:.1f}%"
    what_summary_str = f"{event_type} ({severity} severity, {conf_pct} confidence)"

    # 2. WHO (Tracks, class names, Re-ID identity)
    track_details: list[str] = []
    class_names: list[str] = []
    track_traj: list[Any] = []
    if track_ids and session_id:
        db_tracks = dao.get_tracks(session_id)
        track_map = {t["track_id"]: t for t in db_tracks}
        for tid in track_ids:
            t = track_map.get(tid)
            cname = t["class_name"] if t else "target"
            class_names.append(cname)
            track_details.append(f"Track #{tid} ({cname})")
            if t and "trajectory" in t.keys() and t["trajectory"]:
                try:
                    track_traj = json.loads(t["trajectory"])
                except Exception:
                    pass
    elif track_ids:
        for tid in track_ids:
            class_names.append("target")
            track_details.append(f"Track #{tid}")

    reid_pid = metadata.get("global_person_id")
    reid_cams = metadata.get("identity_cameras") or []
    if reid_pid:
        cams_str = f"seen on {', '.join(reid_cams)}" if reid_cams else "cross-camera match"
        reid_clause = f"Re-ID Identity: {reid_pid} ({cams_str})"
    else:
        reid_clause = "Re-ID: Not available"

    if track_details:
        who_summary_str = f"{', '.join(track_details)} | {reid_clause}"
    else:
        who_summary_str = "Not available (no track binding)"

    # 3. WHERE (Source ID, GPS Coordinates, Video Zone, Geo Sector)
    source_row = dao.get_source(source_id) if source_id else None
    source_label = source_row["label"] if (source_row and "label" in source_row.keys() and source_row["label"]) else (
        source_row["name"] if (source_row and "name" in source_row.keys() and source_row["name"]) else source_id
    )
    lat = source_row["latitude"] if (source_row and "latitude" in source_row.keys()) else None
    lng = source_row["longitude"] if (source_row and "longitude" in source_row.keys()) else None

    if lat is not None and lng is not None:
        coords_clause = f"Coords: {lat:.4f}, {lng:.4f}"
    else:
        coords_clause = "Coords: Not available"

    # Zone resolution
    zone_name = None
    zone_kind = None
    zone_type = None
    if zone_id:
        zone_row = dao.get_zone(zone_id)
        if zone_row:
            zone_name = zone_row["name"]
            zone_kind = zone_row["kind"]
            zone_type = zone_row["zone_type"]
            zone_clause = f"Zone: {zone_name} ({zone_kind}, {zone_type})"
        else:
            zone_clause = f"Zone: {zone_id} (deleted zone)"
    else:
        zone_clause = "Zone: Not available"

    # Geo Sector point-in-polygon resolution
    geo_sectors_matched: list[str] = []
    if lat is not None and lng is not None and dao._has_geo_sectors():
        all_sectors = dao.geo_sectors_rows()
        for sec in all_sectors:
            is_active = bool(sec["active"]) if "active" in sec.keys() else True
            if is_active:
                try:
                    poly = json.loads(sec["polygon"])
                    if point_in_sector(lat, lng, poly):
                        geo_sectors_matched.append(sec["name"])
                except Exception:
                    pass

    if geo_sectors_matched:
        geo_clause = f"Geo Sector: {', '.join(geo_sectors_matched)}"
    elif lat is not None and lng is not None:
        geo_clause = "Geo Sector: None containing camera"
    else:
        geo_clause = "Geo Sector: Not available (camera unplaced)"

    where_summary_str = f"Source: {source_label} | {coords_clause} | {zone_clause} | {geo_clause}"

    # 4. WHEN (Timestamp, Video Offset, Night Mode)
    vts_str = f"+{video_ts:.2f}s" if video_ts is not None else "Not available"
    clock_time_str = ts.split("T")[1][:8] if (ts and "T" in ts) else (ts or "Live")
    night_str = "Active" if is_night else "Inactive"
    when_summary_str = f"Time: {ts} | Video offset: {vts_str} | Night mode: {night_str}"

    # 5. MOVEMENT (Direction, Kinematics metrics)
    dir_str = direction if direction else "Not available"
    kin_parts: list[str] = []
    speed_px_s: Optional[float] = None
    if "velocity" in metadata:
        speed_px_s = float(metadata["velocity"])
        kin_parts.append(f"velocity: {speed_px_s:.1f}px/s")
    if "acceleration" in metadata:
        kin_parts.append(f"accel: {float(metadata['acceleration']):.1f}px/s²")
    if "straightness" in metadata:
        kin_parts.append(f"straightness: {float(metadata['straightness']):.2f}")
    if "dwell_time" in metadata:
        kin_parts.append(f"dwell: {float(metadata['dwell_time']):.1f}s")
    if "person_count" in metadata:
        kin_parts.append(f"count: {metadata['person_count']}")

    kin_str = f"Kinematics: {', '.join(kin_parts)}" if kin_parts else "Kinematics: Not available"
    movement_summary_str = f"Direction: {dir_str} | {kin_str}"

    # 6. WHY (Severity reason & explanation)
    sev_reason = metadata.get("severity_reason")
    if sev_reason:
        why_summary_str = str(sev_reason)
    else:
        reasons: list[str] = [f"Triggered by {event_type} event rule"]
        if is_night:
            reasons.append("night-time detection policy (+1 severity)")
        if zone_type == "RESTRICTED":
            reasons.append("restricted perimeter escalation (+1 severity)")
        why_summary_str = f"{'; '.join(reasons)}."

    # 7. EVIDENCE (Snapshot path / reason skipped)
    if snapshot_path:
        evidence_summary_str = f"Snapshot available ({snapshot_path})"
        snapshot_available = True
        skip_reason = None
    elif metadata.get("snapshot_skipped_low_disk"):
        evidence_summary_str = "Snapshot skipped — low disk threshold"
        snapshot_available = False
        skip_reason = "low_disk"
    else:
        evidence_summary_str = "Not available (no evidence registered for this event)"
        snapshot_available = False
        skip_reason = "none_registered"

    # Multi-clause narrative
    narrative = (
        f"At {ts}, {what_summary_str} was detected on {source_label}. "
        f"Who: {who_summary_str}. "
        f"Location: {zone_clause}, {coords_clause}, {geo_clause}. "
        f"Movement: {movement_summary_str}. "
        f"Assessment: {why_summary_str} "
        f"Evidence: {evidence_summary_str}."
    )

    return {
        "event_id": event_id,
        "session_id": session_id,
        "source_id": source_id,
        "what": what_summary_str,
        "who": who_summary_str,
        "where": where_summary_str,
        "when": when_summary_str,
        "movement": movement_summary_str,
        "why": why_summary_str,
        "evidence": evidence_summary_str,
        "narrative": narrative,
        "structured": {
            "what": {
                "type": event_type,
                "label": type_label,
                "severity": severity,
                "confidence": confidence,
                "is_night": is_night,
                "summary": what_summary_str,
            },
            "who": {
                "track_ids": track_ids,
                "primary_track": track_ids[0] if track_ids else None,
                "global_person_id": reid_pid,
                "class_name": class_names[0] if class_names else "target",
                "class_names": class_names,
                "identity": reid_pid,
                "identity_cameras": reid_cams,
            },
            "where": {
                "zone_id": zone_id,
                "zone_type": zone_type,
                "zone_name": zone_name,
                "zone_kind": zone_kind,
                "camera_id": source_id,
                "camera_label": source_label,
                "geo_sector": geo_sectors_matched[0] if geo_sectors_matched else None,
                "geo_sectors": geo_sectors_matched,
                "coordinates": {"latitude": lat, "longitude": lng} if (lat is not None and lng is not None) else None,
            },
            "when": {
                "ts": ts,
                "video_ts": video_ts,
                "video_time_formatted": vts_str,
                "clock_time": clock_time_str,
                "is_night": is_night,
            },
            "movement": {
                "direction": direction,
                "speed_px_s": speed_px_s,
                "trajectory_points": len(track_traj) if track_traj else None,
                "kinematics": metadata if kin_parts else None,
            },
            "why": {
                "rule": f"{event_type}_RULE",
                "description": why_summary_str,
                "trigger_condition": sev_reason or f"Triggered by {event_type} event rule with {severity} severity",
                "severity_reason": sev_reason,
                "summary": why_summary_str,
            },
            "evidence": {
                "snapshot_path": snapshot_path,
                "has_snapshot": snapshot_available,
                "snapshot_available": snapshot_available,
                "evidence_count": 1 if snapshot_available else 0,
                "skip_reason": skip_reason,
            },
        },
    }
