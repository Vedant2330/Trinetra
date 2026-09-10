import SwiftUI
import AppKit

public struct MainShellView: View {
    @Environment(AppState.self) private var state

    public init() {}

    public var body: some View {
        NavigationSplitView {
            // Sidebar Navigation
            List(NavSection.allCases, selection: Bindable(state).selectedSection) { section in
                NavigationLink(value: section) {
                    Label {
                        Text(section.rawValue)
                            .font(.system(size: 13, weight: .medium))
                    } icon: {
                        Image(systemName: section.icon)
                            .font(.system(size: 14))
                            .foregroundStyle(state.selectedSection == section ? Color.accentColor : Color.secondary)
                    }
                }
            }
            .navigationSplitViewColumnWidth(min: 200, ideal: 230, max: 280)
            .navigationTitle("TRINETRA")
            .safeAreaInset(edge: .bottom) {
                // Backend Status Strip in Sidebar Footer
                VStack(spacing: 8) {
                    Divider()
                    HStack(spacing: 8) {
                        Circle()
                            .fill(state.isBackendOnline ? Color.green : Color.red)
                            .frame(width: 9, height: 9)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(state.isBackendOnline ? "AI Engine Online" : "AI Engine Offline")
                                .font(.system(size: 11, weight: .semibold))
                            if let health = state.health {
                                Text("\(health.device.uppercased()) • \(health.database.mode) WAL")
                                    .font(.system(size: 9, design: .monospaced))
                                    .foregroundStyle(.secondary)
                            }
                        }
                        Spacer()
                    }
                    .padding(.horizontal, 12)
                    .padding(.bottom, 8)
                }
                .background(Color(NSColor.windowBackgroundColor))
            }
        } detail: {
            // Content Detail & Hermes AI Drawer Overlay
            HStack(spacing: 0) {
                // Main Content View based on Section
                Group {
                    switch state.selectedSection {
                    case .liveOperations:
                        LiveOperationsView()
                    case .events:
                        EventsView()
                    case .investigation:
                        InvestigationView()
                    case .analytics:
                        AnalyticsView()
                    case .geography:
                        GeographyView()
                    case .reidGallery:
                        ReIDGalleryView()
                    case .sources:
                        SourcesView()
                    case .diagnostics:
                        DiagnosticsView()
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)

                // Right-side Sliding Hermes Intelligence Drawer
                if state.isHermesDrawerOpen {
                    Divider()
                    HermesDrawerView()
                        .frame(width: 380)
                        .transition(.move(edge: .trailing))
                }
            }
            .toolbar {
                // Top Global Status & Action Toolbar
                ToolbarItemGroup(placement: .navigation) {
                    if let sess = state.currentSession, state.isSessionActive {
                        HStack(spacing: 6) {
                            Text("ACTIVE SESSION:")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundStyle(.secondary)
                            Text(sess.session_id)
                                .font(.system(size: 11, weight: .medium, design: .monospaced))
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.accentColor.opacity(0.15))
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                        }
                    }
                }

                ToolbarItemGroup(placement: .primaryAction) {
                    // Quick Video Open Button
                    Button {
                        state.pickAndPlayVideoFile()
                    } label: {
                        Label("Open Video File", systemImage: "plus.rectangle.on.folder")
                    }
                    .help("Open and analyze a video file with TRINETRA AI engine")

                    // Toggle Hermes AI Drawer
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            state.isHermesDrawerOpen.toggle()
                        }
                    } label: {
                        Label(
                            "Hermes Assistant",
                            systemImage: state.isHermesDrawerOpen ? "bubble.left.and.bubble.right.fill" : "bubble.left.and.bubble.right"
                        )
                    }
                    .help("Toggle Hermes 3 AI Intelligence Assistant")
                }
            }
        }
    }
}
