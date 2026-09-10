import SwiftUI
import AppKit

public struct EventsView: View {
    @Environment(AppState.self) private var state

    @State private var selectedSeverity: String? = nil
    @State private var searchText: String = ""

    public init() {}

    private var filteredEvents: [EventRow] {
        state.events.filter { ev in
            let matchesSeverity = (selectedSeverity == nil || ev.severity.uppercased() == selectedSeverity)
            let matchesSearch = searchText.isEmpty ||
                ev.type.localizedCaseInsensitiveContains(searchText) ||
                (ev.summary?.localizedCaseInsensitiveContains(searchText) ?? false) ||
                "\(ev.track_id ?? -1)".contains(searchText)
            return matchesSeverity && matchesSearch
        }
    }

    private var criticalCount: Int {
        state.events.filter { $0.severity.uppercased() == "CRITICAL" }.count
    }

    private var warningCount: Int {
        state.events.filter { $0.severity.uppercased() == "WARNING" }.count
    }

    private var infoCount: Int {
        state.events.filter { $0.severity.uppercased() == "INFO" }.count
    }

    public var body: some View {
        HSplitView {
            // Left Column: Case Header + Filters & Events Table
            VStack(spacing: 0) {
                // Case & Investigation Header
                VStack(alignment: .leading, spacing: 6) {
                    HStack(alignment: .center, spacing: 10) {
                        Image(systemName: "shield.lefthalf.filled")
                            .font(.system(size: 18, weight: .bold))
                            .foregroundStyle(Color.accentColor)

                        VStack(alignment: .leading, spacing: 2) {
                            Text("INCIDENT & FORENSIC EVENT LOG")
                                .font(.system(size: 13, weight: .bold, design: .monospaced))
                            Text(state.currentSession != nil
                                 ? "Active Session: \(state.currentSession?.source_id ?? "Live Pipeline")"
                                 : "All Recorded Telemetry Events")
                                .font(.system(size: 10))
                                .foregroundStyle(.secondary)
                        }

                        Spacer()

                        // Metrics Badges
                        HStack(spacing: 6) {
                            MetricChip(label: "TOTAL", count: state.events.count, color: .secondary)
                            MetricChip(label: "CRIT", count: criticalCount, color: .red)
                            MetricChip(label: "WARN", count: warningCount, color: .orange)
                            MetricChip(label: "INFO", count: infoCount, color: .blue)
                        }
                    }
                }
                .padding(12)
                .background(Color(NSColor.controlBackgroundColor).opacity(0.6))
                .overlay(Divider(), alignment: .bottom)

                // Filter Header Bar
                HStack(spacing: 8) {
                    // Search Bar
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundStyle(.secondary)
                        TextField("Search events, types, tracks...", text: $searchText)
                            .textFieldStyle(.plain)
                    }
                    .padding(6)
                    .background(Color(NSColor.controlBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 6))

                    // Severity Filter Buttons
                    HStack(spacing: 4) {
                        SeverityFilterButton(title: "ALL", isSelected: selectedSeverity == nil) {
                            selectedSeverity = nil
                        }
                        SeverityFilterButton(title: "CRIT", isSelected: selectedSeverity == "CRITICAL", color: .red) {
                            selectedSeverity = selectedSeverity == "CRITICAL" ? nil : "CRITICAL"
                        }
                        SeverityFilterButton(title: "WARN", isSelected: selectedSeverity == "WARNING", color: .orange) {
                            selectedSeverity = selectedSeverity == "WARNING" ? nil : "WARNING"
                        }
                        SeverityFilterButton(title: "INFO", isSelected: selectedSeverity == "INFO", color: .blue) {
                            selectedSeverity = selectedSeverity == "INFO" ? nil : "INFO"
                        }
                    }

                    Spacer()

                    // Refresh Button
                    Button {
                        Task {
                            await state.refreshEvents()
                        }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }
                .padding(12)
                .background(Color(NSColor.windowBackgroundColor))
                .overlay(Divider(), alignment: .bottom)

                // Events List Table
                if filteredEvents.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "tray.fill")
                            .font(.system(size: 36))
                            .foregroundStyle(.secondary)
                        Text("No Events Recorded")
                            .font(.headline)
                            .foregroundStyle(.secondary)
                        Text("Real-time detections, zone breaches, and crowd alerts will appear here.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    List(filteredEvents, selection: Binding(
                        get: { state.selectedEvent },
                        set: { newEv in
                            if let ev = newEv {
                                state.selectEvent(ev)
                            } else {
                                state.selectedEvent = nil
                            }
                        }
                    )) { event in
                        EventRowCard(event: event, isSelected: state.selectedEvent?.id == event.id)
                            .tag(event)
                    }
                    .listStyle(.inset(alternatesRowBackgrounds: true))
                }
            }
            .frame(minWidth: 420, maxWidth: .infinity)

            // Right Column: Event Detail & Evidence Inspector
            EventDetailInspector()
                .frame(minWidth: 380, idealWidth: 440, maxWidth: 540)
        }
    }
}

// MARK: - Metric Chip

struct MetricChip: View {
    let label: String
    let count: Int
    let color: Color

    var body: some View {
        HStack(spacing: 3) {
            Text(label)
                .font(.system(size: 8, weight: .bold, design: .monospaced))
                .foregroundStyle(color)
            Text("\(count)")
                .font(.system(size: 9, weight: .heavy, design: .monospaced))
                .foregroundStyle(color)
        }
        .padding(.horizontal, 5)
        .padding(.vertical, 2.5)
        .background(color.opacity(0.12))
        .clipShape(RoundedRectangle(cornerRadius: 3))
    }
}

// MARK: - Severity Filter Button

struct SeverityFilterButton: View {
    let title: String
    let isSelected: Bool
    var color: Color = .primary
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 10, weight: .bold))
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(isSelected ? color.opacity(0.2) : Color.clear)
                .foregroundStyle(isSelected ? color : .secondary)
                .overlay(
                    RoundedRectangle(cornerRadius: 4)
                        .stroke(isSelected ? color : Color.secondary.opacity(0.3), lineWidth: 1)
                )
                .clipShape(RoundedRectangle(cornerRadius: 4))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Event Row Card

struct EventRowCard: View {
    let event: EventRow
    let isSelected: Bool

    private var displayType: String {
        if event.type == "SESSION_COMPLETED" {
            return "ANALYSIS COMPLETE"
        }
        return event.type
    }

    private var displaySeverity: String {
        if event.type == "SESSION_COMPLETED" {
            return "INFO"
        }
        return event.severity.uppercased()
    }

    private var displayColorHex: String {
        if event.type == "SESSION_COMPLETED" {
            return "#3B82F6" // blue info
        }
        return event.severityColorHex
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                // Severity Badge
                Text(displaySeverity)
                    .font(.system(size: 9, weight: .heavy, design: .monospaced))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Color(hex: displayColorHex))
                    .clipShape(RoundedRectangle(cornerRadius: 4))

                // Event Type
                Text(displayType)
                    .font(.system(size: 12, weight: .semibold))

                Spacer()

                // Timestamp
                Text(event.formattedTime)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(.secondary)
            }

            // Summary Text
            if let summary = event.summary, !summary.isEmpty {
                Text(summary)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            // Metadata Chips
            HStack(spacing: 8) {
                if let srcId = event.source_id, !srcId.isEmpty {
                    Label(srcId, systemImage: "camera.fill")
                        .font(.system(size: 10, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Color.accentColor)
                }

                if let trackId = event.track_id {
                    Label("Track #\(trackId)", systemImage: "person.crop.circle")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(.secondary)
                }

                if let vts = event.video_ts {
                    Label(String(format: "%.1fs", vts), systemImage: "play.circle")
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundStyle(Color.accentColor)
                }

                Label("\(Int(event.confidence * 100))% conf", systemImage: "target")
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(.secondary)

                if let zoneId = event.zone_id {
                    Label(zoneId, systemImage: "shield.lefthalf.filled")
                        .font(.system(size: 10))
                        .foregroundStyle(.secondary)
                }

                Spacer()

                if event.snapshot_path != nil {
                    Image(systemName: "photo.fill")
                        .font(.system(size: 10))
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Event Detail Inspector

struct EventDetailInspector: View {
    @Environment(AppState.self) private var state

    var body: some View {
        VStack(spacing: 0) {
            if let ev = state.selectedEvent {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        // Header
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(ev.type == "SESSION_COMPLETED" ? "ANALYSIS COMPLETE" : ev.type)
                                    .font(.title3.bold())
                                Text("Event ID #\(ev.id) • \(ev.formattedTime)")
                                    .font(.caption.monospaced())
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            Text(ev.type == "SESSION_COMPLETED" ? "INFO" : ev.severity.uppercased())
                                .font(.system(size: 11, weight: .bold, design: .monospaced))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color(hex: ev.type == "SESSION_COMPLETED" ? "#3B82F6" : ev.severityColorHex))
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                        }

                        // Video Seeking Action Banner
                        if let vts = ev.video_ts {
                            Button {
                                Task {
                                    await state.seekTo(timestamp: vts)
                                }
                            } label: {
                                HStack {
                                    Image(systemName: "play.circle.fill")
                                        .font(.system(size: 14))
                                    Text("Seek Video to \(String(format: "%.2f", vts))s")
                                        .font(.system(size: 11, weight: .bold))
                                    Spacer()
                                    Image(systemName: "chevron.right")
                                        .font(.system(size: 10))
                                }
                                .padding(10)
                                .background(Color.accentColor.opacity(0.12))
                                .foregroundStyle(Color.accentColor)
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                            }
                            .buttonStyle(.plain)
                        }

                        // Snapshot Evidence View
                        VStack(alignment: .leading, spacing: 6) {
                            Text("EVIDENCE SNAPSHOT")
                                .font(.system(size: 11, weight: .bold, design: .monospaced))
                                .foregroundStyle(.secondary)

                            ZStack {
                                RoundedRectangle(cornerRadius: 8)
                                    .fill(Color.black.opacity(0.8))
                                    .frame(height: 220)

                                if state.isSnapshotLoading {
                                    ProgressView("Loading Snapshot...")
                                        .controlSize(.small)
                                } else if let snapshot = state.selectedEventSnapshot {
                                    Image(nsImage: snapshot)
                                        .resizable()
                                        .aspectRatio(contentMode: .fit)
                                        .frame(maxHeight: 220)
                                        .clipShape(RoundedRectangle(cornerRadius: 8))
                                } else {
                                    VStack(spacing: 6) {
                                        Image(systemName: "photo.badge.exclamationmark")
                                            .font(.system(size: 28))
                                            .foregroundStyle(.secondary)
                                        Text("No Evidence Image Available")
                                            .font(.caption)
                                            .foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }

                        // Summary & 7-W Breakdown
                        if let summary = ev.summary {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("DETERMINISTIC SUMMARY")
                                    .font(.system(size: 11, weight: .bold, design: .monospaced))
                                    .foregroundStyle(.secondary)
                                Text(summary)
                                    .font(.system(size: 12))
                                    .padding(10)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .background(Color(NSColor.controlBackgroundColor))
                                    .clipShape(RoundedRectangle(cornerRadius: 6))
                            }
                        }

                        // Structured Metadata Grid
                        VStack(alignment: .leading, spacing: 6) {
                            Text("TELEMETRY & ATTRIBUTES")
                                .font(.system(size: 11, weight: .bold, design: .monospaced))
                                .foregroundStyle(.secondary)

                            Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 8) {
                                if let srcId = ev.source_id ?? state.currentSession?.source_id, !srcId.isEmpty {
                                    GridRow {
                                        Text("Camera Feed:").foregroundStyle(.secondary)
                                        HStack(spacing: 8) {
                                            Text(srcId)
                                                .font(.system(size: 11, weight: .bold, design: .monospaced))
                                                .padding(.horizontal, 6)
                                                .padding(.vertical, 1)
                                                .background(Color.secondary.opacity(0.12))
                                                .clipShape(RoundedRectangle(cornerRadius: 4))

                                            if let cam = state.mapCameras.first(where: { $0.source_id == srcId }), cam.latitude != nil {
                                                Button {
                                                    state.navigateToCameraOnMap(sourceId: srcId)
                                                } label: {
                                                    HStack(spacing: 3) {
                                                        Image(systemName: "map.fill")
                                                        Text("Show on Map")
                                                    }
                                                    .font(.system(size: 10, weight: .medium))
                                                }
                                                .buttonStyle(.bordered)
                                                .controlSize(.mini)
                                                .help("Jump to camera coordinates on GIS Tactical Map")
                                            }
                                        }
                                    }
                                }

                                GridRow {
                                    Text("Track ID:").foregroundStyle(.secondary)
                                    Text(ev.track_id != nil ? "#\(ev.track_id!)" : "N/A").font(.system(size: 11, design: .monospaced))
                                }
                                GridRow {
                                    Text("Confidence:").foregroundStyle(.secondary)
                                    Text("\(String(format: "%.2f", ev.confidence))").font(.system(size: 11, design: .monospaced))
                                }
                                GridRow {
                                    Text("Virtual Zone:").foregroundStyle(.secondary)
                                    Text(ev.zone_id ?? "Default / None")
                                }
                                GridRow {
                                    Text("Video Timestamp:").foregroundStyle(.secondary)
                                    Text(ev.video_ts != nil ? "\(String(format: "%.3f", ev.video_ts!)) s" : "N/A").font(.system(size: 11, design: .monospaced))
                                }
                                GridRow {
                                    Text("System Timestamp:").foregroundStyle(.secondary)
                                    Text(ev.ts ?? "N/A").font(.system(size: 11, design: .monospaced))
                                }
                            }
                            .font(.system(size: 12))
                            .padding(10)
                            .background(Color(NSColor.controlBackgroundColor))
                            .clipShape(RoundedRectangle(cornerRadius: 6))
                        }

                        // Geographic Location & Sensor Correlation
                        if let srcId = ev.source_id ?? state.currentSession?.source_id,
                           let cam = state.mapCameras.first(where: { $0.source_id == srcId }) ?? state.sources.first(where: { $0.id == srcId }).flatMap({ s in s.effectiveLat != nil ? MapCameraItem(source_id: s.id, label: s.label ?? s.name ?? s.id, latitude: s.effectiveLat, longitude: s.effectiveLng, status: s.isLiveActive ? "live" : (s.isDemo ? "demo" : "idle"), type: s.type) : nil }) {
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Image(systemName: "mappin.and.ellipse")
                                        .foregroundStyle(Color.accentColor)
                                    Text("GEOGRAPHIC LOCATION & SENSOR")
                                        .font(.system(size: 11, weight: .bold, design: .monospaced))
                                        .foregroundStyle(.secondary)
                                    Spacer()
                                }
                                HStack {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(cam.label.isEmpty ? cam.source_id : cam.label)
                                            .font(.system(size: 12, weight: .bold))
                                        if let lat = cam.latitude, let lng = cam.longitude {
                                            Text(String(format: "%.4f° N, %.4f° E", lat, lng))
                                                .font(.system(size: 10, design: .monospaced))
                                                .foregroundStyle(.secondary)
                                        }
                                    }
                                    Spacer()
                                    Button {
                                        state.navigateToCameraOnMap(sourceId: cam.source_id)
                                    } label: {
                                        Label("Show on Map", systemImage: "map.fill")
                                            .font(.system(size: 11))
                                    }
                                    .buttonStyle(.borderedProminent)
                                    .controlSize(.small)
                                    .help("Jump to GIS Map view and focus on this camera's sector")
                                }
                                .padding(10)
                                .background(Color(NSColor.controlBackgroundColor))
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                            }
                        }

                        // Action: Ask TRINETRACHAT about this event
                        Button {
                            state.isHermesDrawerOpen = true
                            state.askHermes(prompt: "Provide an in-depth tactical briefing for Event #\(ev.id) (\(ev.type)) on Track \(ev.track_id ?? -1).")
                        } label: {
                            Label("Ask TRINETRACHAT AI Analysis", systemImage: "sparkles")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.regular)
                    }
                    .padding(16)
                }
            } else {
                VStack(spacing: 12) {
                    Image(systemName: "cursorarrow.click.2")
                        .font(.system(size: 36))
                        .foregroundStyle(.secondary)
                    Text("No Event Selected")
                        .font(.headline)
                        .foregroundStyle(.secondary)
                    Text("Select an event row from the left panel to inspect evidence and jump video timestamp.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 24)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(Color(NSColor.windowBackgroundColor))
    }
}
