import SwiftUI
import AppKit

public struct InvestigationView: View {
    @Environment(AppState.self) private var state

    @State private var selectedTrack: SessionTrackRow? = nil
    @State private var forensicQuery: String = ""

    public init() {}

    public var body: some View {
        HSplitView {
            // Left Panel: Sessions & Events Explorer
            VStack(spacing: 0) {
                // Header
                HStack {
                    Image(systemName: "clock.arrow.circlepath")
                        .foregroundStyle(Color.accentColor)
                    Text("Sessions & Timeline")
                        .font(.system(size: 13, weight: .bold))
                    Spacer()
                    Button {
                        Task {
                            await state.refreshSessionHistory()
                            await state.refreshEvents()
                        }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.secondary)
                }
                .padding(12)
                .background(Color(NSColor.windowBackgroundColor))
                .overlay(Divider(), alignment: .bottom)

                // Session History List
                List(selection: Binding(
                    get: { state.selectedSessionId },
                    set: { newId in
                        if let id = newId {
                            state.selectSession(sessionId: id)
                        }
                    }
                )) {
                    Section("RECORDED SESSIONS") {
                        if state.sessionHistory.isEmpty {
                            Text("No recorded sessions found in database.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .padding(.vertical, 8)
                        } else {
                            ForEach(state.sessionHistory) { item in
                                SessionRowView(item: item, isSelected: state.selectedSessionId == item.id)
                                    .tag(item.id)
                            }
                        }
                    }

                    Section("SESSION EVENTS & ALERTS") {
                        let filteredEvents = state.events.filter { ev in
                            guard let sid = state.selectedSessionId else { return true }
                            return ev.session_id == sid || ev.source_id == sid
                        }

                        if filteredEvents.isEmpty {
                            Text("No events recorded for this session.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .padding(.vertical, 8)
                        } else {
                            ForEach(filteredEvents) { ev in
                                EventTimelineRow(event: ev, isSelected: state.selectedEvent?.id == ev.id) {
                                    state.selectEvent(ev)
                                }
                            }
                        }
                    }
                }
                .listStyle(.sidebar)
            }
            .frame(minWidth: 260, idealWidth: 300, maxWidth: 360)

            // Right Panel: 7-W Deep Investigation & Forensic Analysis
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Title Bar
                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            HStack(spacing: 8) {
                                Image(systemName: "magnifyingglass.circle.fill")
                                    .font(.title2)
                                    .foregroundStyle(Color.accentColor)
                                Text("7-W Incident Intelligence & Forensic Audit")
                                    .font(.title3.bold())
                            }
                            Text("Machine-verified deterministic fact synthesis derived directly from database telemetry.")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()

                        if state.isInvestigationLoading {
                            ProgressView()
                                .controlSize(.small)
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 16)

                    // Session Overview Metrics Bar
                    if let sessSummary = state.selectedSessionSummary {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("SESSION OVERVIEW")
                                .font(.system(size: 10, weight: .heavy, design: .monospaced))
                                .foregroundStyle(.secondary)

                            HStack(spacing: 12) {
                                InvestigationMetricCard(title: "TOTAL TRACKS", value: "\(sessSummary.tracks_summary?.total_tracks ?? 0)", icon: "person.2.fill", color: .blue)
                                InvestigationMetricCard(title: "PERSONS", value: "\(sessSummary.tracks_summary?.person_tracks ?? 0)", icon: "figure.walk", color: .green)
                                InvestigationMetricCard(title: "VEHICLES", value: "\(sessSummary.tracks_summary?.vehicle_tracks ?? 0)", icon: "car.fill", color: .orange)
                                InvestigationMetricCard(title: "CRITICAL ALERTS", value: "\(sessSummary.events_summary?.critical ?? 0)", icon: "exclamationmark.octagon.fill", color: .red)
                                InvestigationMetricCard(title: "PROCESSED FRAMES", value: "\(sessSummary.frames_processed ?? 0)", icon: "film.fill", color: .purple)
                            }

                            if let narrative = sessSummary.narrative, !narrative.isEmpty {
                                HStack(alignment: .top, spacing: 8) {
                                    Image(systemName: "doc.text.magnifyingglass")
                                        .foregroundStyle(Color.accentColor)
                                        .font(.system(size: 14))
                                    Text(narrative)
                                        .font(.system(size: 12))
                                        .foregroundStyle(.primary)
                                }
                                .padding(12)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(Color(NSColor.controlBackgroundColor))
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8)
                                        .stroke(Color.secondary.opacity(0.15), lineWidth: 1)
                                )
                            }
                        }
                        .padding(.horizontal, 20)
                    }

                    Divider()
                        .padding(.horizontal, 20)

                    // 7-W Framework Grid
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text("DETERMINISTIC 7-W INCIDENT AUDIT")
                                .font(.system(size: 11, weight: .bold, design: .monospaced))
                                .foregroundStyle(.secondary)
                            Spacer()
                            if let ev = state.selectedEvent {
                                Text("EVENT ID: \(ev.id)")
                                    .font(.system(size: 10, design: .monospaced))
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .padding(.horizontal, 20)

                        let sum = state.selectedEventSummary
                        let ev = state.selectedEvent

                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 14) {
                            // WHAT
                            WCard(
                                label: "WHAT (INCIDENT TYPE)",
                                value: sum?.what?.summary ?? (ev != nil ? "\(ev!.type) (\(Int(ev!.confidence * 100))% conf)" : "No incident selected"),
                                subtext: ev?.severity != nil ? "Severity: \(ev!.severity)" : "Awaiting selection",
                                icon: "exclamationmark.triangle.fill",
                                color: ev?.severity.uppercased() == "CRITICAL" ? .red : .orange
                            )

                            // WHO
                            let whoVal: String = {
                                if let w = sum?.who {
                                    if let p = w.primary_track {
                                        return "Track #\(p) (\(w.class_name ?? "Person"))"
                                    }
                                    if let g = w.global_person_id {
                                        return "Global Person \(g)"
                                    }
                                }
                                if let tid = ev?.track_id {
                                    return "Track #\(tid)"
                                }
                                return "Not available / No target track"
                            }()
                            WCard(
                                label: "WHO (SUBJECT SIGNATURE)",
                                value: whoVal,
                                subtext: sum?.who?.global_person_id != nil ? "Re-ID Global Binding: \(sum!.who!.global_person_id!)" : "Local Track Index",
                                icon: "person.crop.circle.badge.checkmark",
                                color: .blue
                            )

                            // WHERE
                            let whereVal: String = {
                                if let wh = sum?.where_loc {
                                    if let z = wh.zone_id { return "Zone: \(z) (\(wh.zone_type ?? "RESTRICTED"))" }
                                    if let c = wh.camera_label { return "Camera: \(c)" }
                                }
                                if let zid = ev?.zone_id, !zid.isEmpty { return "Zone: \(zid)" }
                                return "General Field of View"
                            }()
                            WCard(
                                label: "WHERE (CAMERA / SECTOR / ZONE)",
                                value: whereVal,
                                subtext: sum?.where_loc?.geo_sector != nil ? "Sector: \(sum!.where_loc!.geo_sector!)" : "Video Coordinate Plane",
                                icon: "mappin.and.ellipse",
                                color: .purple
                            )

                            // WHEN
                            let whenVal: String = {
                                if let w = sum?.when_time {
                                    if let vtf = w.video_time_formatted { return "Video Offset: \(vtf)" }
                                    if let ct = w.clock_time { return ct }
                                }
                                return ev?.formattedTime ?? "Not available"
                            }()
                            WCard(
                                label: "WHEN (TIMESTAMP & OFFSET)",
                                value: whenVal,
                                subtext: ev?.ts ?? "ISO Time Unavailable",
                                icon: "clock.fill",
                                color: .teal
                            )

                            // MOVEMENT
                            let movVal: String = {
                                if let m = sum?.movement {
                                    var parts: [String] = []
                                    if let d = m.direction, !d.isEmpty { parts.append("Heading \(d)") }
                                    if let sp = m.speed_px_s { parts.append("\(String(format: "%.1f", sp)) px/s") }
                                    if !parts.isEmpty { return parts.joined(separator: " • ") }
                                }
                                if let dir = ev?.direction, !dir.isEmpty { return "Direction: \(dir)" }
                                return "Kinematic vector stationary / not recorded"
                            }()
                            WCard(
                                label: "MOVEMENT (KINEMATICS & TRAJECTORY)",
                                value: movVal,
                                subtext: sum?.movement?.trajectory_points != nil ? "\(sum!.movement!.trajectory_points!) trajectory coordinates logged" : "Zero trajectory points",
                                icon: "location.north.line.fill",
                                color: .green
                            )

                            // WHY & EVIDENCE
                            let whyVal: String = {
                                if let y = sum?.why {
                                    return y.description ?? y.rule ?? "Rule condition satisfied"
                                }
                                return ev?.summary ?? "Deterministic rule trigger"
                            }()
                            WCard(
                                label: "WHY (ANOMALY TRIGGER / EVIDENCE)",
                                value: whyVal,
                                subtext: sum?.evidence?.has_snapshot == true ? "JPEG Evidence Snapshot on Disk" : "Telemetry log row",
                                icon: "brain.head.profile",
                                color: .pink
                            )
                        }
                        .padding(.horizontal, 20)
                    }

                    // Visual Evidence & Track Trajectory Explorer
                    HStack(alignment: .top, spacing: 16) {
                        // Left: Visual Evidence Inspector
                        VStack(alignment: .leading, spacing: 10) {
                            Text("JPEG EVIDENCE & SENSOR FRAME")
                                .font(.system(size: 10, weight: .heavy, design: .monospaced))
                                .foregroundStyle(.secondary)

                            ZStack {
                                RoundedRectangle(cornerRadius: 8)
                                    .fill(Color.black.opacity(0.85))
                                    .frame(height: 260)

                                if state.isSnapshotLoading {
                                    ProgressView("Loading evidence snapshot...")
                                        .foregroundStyle(.white)
                                } else if let snapshot = state.selectedEventSnapshot {
                                    Image(nsImage: snapshot)
                                        .resizable()
                                        .aspectRatio(contentMode: .fit)
                                        .frame(maxHeight: 260)
                                        .clipShape(RoundedRectangle(cornerRadius: 8))
                                } else if let liveFrame = state.currentFrame {
                                    Image(nsImage: liveFrame)
                                        .resizable()
                                        .aspectRatio(contentMode: .fit)
                                        .frame(maxHeight: 260)
                                        .clipShape(RoundedRectangle(cornerRadius: 8))
                                } else {
                                    VStack(spacing: 8) {
                                        Image(systemName: "photo.on.rectangle.angled")
                                            .font(.system(size: 36))
                                            .foregroundStyle(.secondary)
                                        Text("No Evidence Snapshot Selected")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }

                            HStack {
                                if let ev = state.selectedEvent {
                                    Button {
                                        state.ackSelectedEvent()
                                    } label: {
                                        Label(ev.status == "acked" ? "Acknowledged" : "Acknowledge Incident", systemImage: "checkmark.seal.fill")
                                    }
                                    .buttonStyle(.bordered)
                                    .controlSize(.small)
                                    .disabled(ev.status == "acked")
                                }

                                Spacer()

                                Text(state.selectedEvent?.snapshot_path ?? "Evidence path: None")
                                    .font(.system(size: 9, design: .monospaced))
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                            }
                        }
                        .frame(maxWidth: .infinity)

                        // Right: Session Track Trajectories List
                        VStack(alignment: .leading, spacing: 10) {
                            Text("TRACK TRAJECTORIES (\(state.selectedSessionTracks.count))")
                                .font(.system(size: 10, weight: .heavy, design: .monospaced))
                                .foregroundStyle(.secondary)

                            ScrollView {
                                VStack(spacing: 6) {
                                    if state.selectedSessionTracks.isEmpty {
                                        Text("No tracks recorded for this session.")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                            .padding(.vertical, 20)
                                    } else {
                                        ForEach(state.selectedSessionTracks) { tr in
                                            TrackRowView(track: tr, isSelected: selectedTrack?.track_id == tr.track_id) {
                                                selectedTrack = tr
                                            }
                                        }
                                    }
                                }
                            }
                            .frame(height: 260)
                            .background(Color(NSColor.controlBackgroundColor))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(Color.secondary.opacity(0.15), lineWidth: 1)
                            )
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .padding(.horizontal, 20)

                    Divider()
                        .padding(.horizontal, 20)

                    // Hermes Grounded Forensic Inquiry (trinetraChat)
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Image(systemName: "sparkles")
                                .foregroundStyle(Color.accentColor)
                            Text("GROUNDED FORENSIC INQUIRY (trinetraChat)")
                                .font(.system(size: 11, weight: .bold, design: .monospaced))
                            Spacer()
                            Text("ZERO-FABRICATION HERMES 3 REASONING")
                                .font(.system(size: 9, weight: .bold, design: .monospaced))
                                .foregroundStyle(.secondary)
                        }

                        TextEditor(text: $forensicQuery)
                            .font(.system(size: 12))
                            .frame(height: 80)
                            .padding(8)
                            .background(Color(NSColor.controlBackgroundColor))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(Color.secondary.opacity(0.2), lineWidth: 1)
                            )

                        HStack(spacing: 8) {
                            Button("Loitering Audit") {
                                forensicQuery = "Analyze all subjects dwelling longer than 45 seconds in restricted zones."
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.small)

                            Button("Speed Spike Check") {
                                forensicQuery = "Identify tracks exhibiting rapid acceleration exceeding standard threshold."
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.small)

                            Button("Cross-Camera Correlation") {
                                forensicQuery = "List all potential re-identification matches across multi-camera sources."
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.small)

                            Spacer()

                            Button {
                                guard !forensicQuery.isEmpty else { return }
                                state.isHermesDrawerOpen = true
                                state.askHermes(
                                    prompt: forensicQuery,
                                    eventId: state.selectedEvent?.id,
                                    sessionId: state.selectedSessionId
                                )
                            } label: {
                                Label("Ask Hermes Copilot", systemImage: "arrow.up.circle.fill")
                            }
                            .buttonStyle(.borderedProminent)
                            .controlSize(.regular)
                            .disabled(forensicQuery.isEmpty)
                        }
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, 24)
                }
            }
        }
    }
}

// MARK: - Subcomponents

struct SessionRowView: View {
    let item: SessionHistoryItem
    let isSelected: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(item.source_id ?? item.id)
                    .font(.system(size: 12, weight: .bold))
                    .lineLimit(1)
                Spacer()
                Text(item.status?.uppercased() ?? "RECORDED")
                    .font(.system(size: 9, weight: .bold, design: .monospaced))
                    .foregroundStyle(item.status == "active" ? .green : .secondary)
            }
            Text("Session: \(String(item.id.prefix(12)))...")
                .font(.system(size: 10, design: .monospaced))
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }
}

struct EventTimelineRow: View {
    let event: EventRow
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            HStack(spacing: 8) {
                Circle()
                    .fill(Color(hex: event.severityColorHex))
                    .frame(width: 8, height: 8)

                VStack(alignment: .leading, spacing: 2) {
                    Text(event.type)
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(.primary)

                    HStack(spacing: 6) {
                        Text(event.formattedTime)
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundStyle(.secondary)
                        if let tid = event.track_id {
                            Text("Track #\(tid)")
                                .font(.system(size: 9, design: .monospaced))
                                .foregroundStyle(Color.accentColor)
                        }
                    }
                }
                Spacer()

                if event.status == "acked" {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 10))
                        .foregroundStyle(.green)
                }
            }
            .padding(6)
            .background(isSelected ? Color.accentColor.opacity(0.15) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
    }
}

struct InvestigationMetricCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .foregroundStyle(color)
                    .font(.system(size: 11))
                Text(title)
                    .font(.system(size: 9, weight: .heavy, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
            Text(value)
                .font(.system(size: 16, weight: .bold, design: .monospaced))
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(NSColor.controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color.secondary.opacity(0.15), lineWidth: 1)
        )
    }
}

struct WCard: View {
    let label: String
    let value: String
    let subtext: String
    let icon: String
    let color: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .foregroundStyle(color)
                    .font(.system(size: 11))
                Text(label)
                    .font(.system(size: 9, weight: .heavy, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
            Text(value)
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(.primary)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
            Text(subtext)
                .font(.system(size: 9, design: .monospaced))
                .foregroundStyle(.secondary)
                .lineLimit(1)
        }
        .padding(10)
        .frame(maxWidth: .infinity, minHeight: 88, alignment: .topLeading)
        .background(Color(NSColor.controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(color.opacity(0.3), lineWidth: 1)
        )
    }
}

struct TrackRowView: View {
    let track: SessionTrackRow
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            HStack(spacing: 8) {
                Image(systemName: track.class_name.lowercased() == "person" ? "figure.walk" : "car.fill")
                    .foregroundStyle(Color.accentColor)
                    .font(.system(size: 12))

                VStack(alignment: .leading, spacing: 2) {
                    Text("Track #\(track.track_id) • \(track.class_name)")
                        .font(.system(size: 11, weight: .bold))
                    Text("\(track.frames ?? 0) frames seen • Max conf: \(Int((track.max_conf ?? 1.0) * 100))%")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
                Spacer()

                if let traj = track.trajectory, !traj.isEmpty {
                    Text("\(traj.count) pts")
                        .font(.system(size: 9, design: .monospaced))
                        .foregroundStyle(.green)
                }
            }
            .padding(8)
            .background(isSelected ? Color.accentColor.opacity(0.2) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
    }
}
