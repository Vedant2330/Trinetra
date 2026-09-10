import SwiftUI
import AppKit

public struct ReIDGalleryView: View {
    @Environment(AppState.self) private var state

    @State private var searchQuery: String = ""

    public init() {}

    private var filteredPersons: [ReIDPersonSummary] {
        if searchQuery.isEmpty {
            return state.reidPersons
        }
        return state.reidPersons.filter { p in
            p.person_id.localizedCaseInsensitiveContains(searchQuery) ||
            p.cameras_seen.joined(separator: " ").localizedCaseInsensitiveContains(searchQuery)
        }
    }

    public var body: some View {
        HSplitView {
            // Gallery Grid
            VStack(spacing: 0) {
                // Header Search & Refresh
                HStack(spacing: 8) {
                    HStack {
                        Image(systemName: "magnifyingglass")
                            .foregroundStyle(.secondary)
                        TextField("Search person ID, camera...", text: $searchQuery)
                            .textFieldStyle(.plain)
                    }
                    .padding(6)
                    .background(Color(NSColor.controlBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 6))

                    Spacer()

                    Button {
                        Task {
                            await state.refreshReIDPersons()
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

                if filteredPersons.isEmpty {
                    VStack(spacing: 12) {
                        Image(systemName: "person.crop.rectangle.badge.plus")
                            .font(.system(size: 36))
                            .foregroundStyle(.secondary)
                        Text("No Re-ID Identities Indexed")
                            .font(.headline)
                            .foregroundStyle(.secondary)
                        Text("As pedestrians are observed across camera streams, their Fast-ReID embeddings will populate this gallery.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 32)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    ScrollView {
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 180, maximum: 240))], spacing: 14) {
                            ForEach(filteredPersons) { person in
                                ReIDPersonCard(
                                    person: person,
                                    isSelected: state.selectedPerson?.id == person.id
                                ) {
                                    state.selectedPerson = person
                                }
                            }
                        }
                        .padding(16)
                    }
                }
            }
            .frame(minWidth: 400, maxWidth: .infinity)

            // Right Panel: Person Identity Inspector
            ReIDPersonInspector()
                .frame(minWidth: 300, idealWidth: 360, maxWidth: 440)
        }
    }
}

// MARK: - Person Card

struct ReIDPersonCard: View {
    let person: ReIDPersonSummary
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            VStack(alignment: .leading, spacing: 8) {
                // Avatar / Thumbnail placeholder
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color(NSColor.windowBackgroundColor))
                        .frame(height: 120)

                    Image(systemName: "person.fill")
                        .font(.system(size: 40))
                        .foregroundStyle(Color.accentColor.opacity(0.8))
                }

                // ID & Observation Count
                HStack {
                    Text(person.person_id)
                        .font(.system(size: 13, weight: .bold, design: .monospaced))
                    Spacer()
                    Text("\(person.observation_count) views")
                        .font(.system(size: 10, weight: .medium))
                        .foregroundStyle(.secondary)
                }

                // Cameras Seen List
                HStack(spacing: 4) {
                    Image(systemName: "camera.fill")
                        .font(.system(size: 9))
                        .foregroundStyle(.secondary)
                    Text(person.cameras_seen.joined(separator: ", "))
                        .font(.system(size: 10))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
            .padding(10)
            .background(isSelected ? Color.accentColor.opacity(0.12) : Color(NSColor.controlBackgroundColor))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(isSelected ? Color.accentColor : Color.secondary.opacity(0.15), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 8))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Person Inspector

struct ReIDPersonInspector: View {
    @Environment(AppState.self) private var state

    var body: some View {
        VStack(spacing: 0) {
            if let p = state.selectedPerson {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(p.person_id)
                                    .font(.title3.bold().monospaced())
                                Text("Cross-Camera Track Identity")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                        }

                        // Attributes
                        VStack(alignment: .leading, spacing: 8) {
                            Text("IDENTITY TELEMETRY")
                                .font(.system(size: 11, weight: .bold))
                                .foregroundStyle(.secondary)

                            Grid(alignment: .leading, horizontalSpacing: 12, verticalSpacing: 8) {
                                GridRow {
                                    Text("Observation Count:").foregroundStyle(.secondary)
                                    Text("\(p.observation_count)").font(.system(size: 11, design: .monospaced))
                                }
                                GridRow {
                                    Text("First Sighting:").foregroundStyle(.secondary)
                                    Text(p.first_seen).font(.system(size: 11, design: .monospaced))
                                }
                                GridRow {
                                    Text("Last Sighting:").foregroundStyle(.secondary)
                                    Text(p.last_seen).font(.system(size: 11, design: .monospaced))
                                }
                                GridRow {
                                    Text("Feature Embedding:").foregroundStyle(.secondary)
                                    Text("512-d Fast-ReID (L2 Normed)").font(.system(size: 11))
                                }
                            }
                            .font(.system(size: 12))
                            .padding(12)
                            .background(Color(NSColor.controlBackgroundColor))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        }

                        // Cameras List
                        VStack(alignment: .leading, spacing: 8) {
                            Text("OBSERVED CAMERA LOCATIONS")
                                .font(.system(size: 11, weight: .bold))
                                .foregroundStyle(.secondary)

                            ForEach(p.cameras_seen, id: \.self) { cam in
                                HStack {
                                    Image(systemName: "camera.fill")
                                        .foregroundStyle(Color.accentColor)
                                    Text(cam)
                                        .font(.system(size: 12, weight: .medium, design: .monospaced))
                                    Spacer()
                                }
                                .padding(8)
                                .background(Color(NSColor.controlBackgroundColor))
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                            }
                        }

                        // Ask Hermes Query Button
                        Button {
                            state.isHermesDrawerOpen = true
                            state.askHermes(prompt: "Provide a cross-camera movement analysis for Person \(p.person_id). List all sightings and time intervals.")
                        } label: {
                            Label("Analyze Movements with Hermes AI", systemImage: "sparkles")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.regular)
                    }
                    .padding(16)
                }
            } else {
                VStack(spacing: 12) {
                    Image(systemName: "person.fill.questionmark")
                        .font(.system(size: 36))
                        .foregroundStyle(.secondary)
                    Text("No Person Selected")
                        .font(.headline)
                        .foregroundStyle(.secondary)
                    Text("Select an identity profile from the gallery to inspect cross-camera sightings.")
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
