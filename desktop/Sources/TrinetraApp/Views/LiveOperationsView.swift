import SwiftUI
import AppKit
import AVKit
import AVFoundation

public struct LiveOperationsView: View {
    @Environment(AppState.self) private var state

    public init() {}

    public var body: some View {
        VStack(spacing: 0) {
            // Top Toolbar: Layer Toggles & Stream Status
            HStack(spacing: 12) {
                // Layer Toggle Pills
                Group {
                    LayerTogglePill(title: "Boxes", icon: "square.dashed", isOn: state.layers.boxes) {
                        state.toggleLayer(\.boxes)
                    }
                    LayerTogglePill(title: "IDs", icon: "number", isOn: state.layers.labels) {
                        state.toggleLayer(\.labels)
                    }
                    LayerTogglePill(title: "Trajectories", icon: "point.topleft.down.curvedto.point.bottomright.up", isOn: state.layers.trajectories) {
                        state.toggleLayer(\.trajectories)
                    }
                    LayerTogglePill(title: "Zones", icon: "shield.lefthalf.filled", isOn: state.layers.zones) {
                        state.toggleLayer(\.zones)
                    }
                    LayerTogglePill(title: "FPS HUD", icon: "gauge.with.needle", isOn: state.layers.fps) {
                        state.toggleLayer(\.fps)
                    }
                    LayerTogglePill(title: "Faces", icon: "face.smiling", isOn: state.layers.faces) {
                        state.toggleLayer(\.faces)
                    }
                    LayerTogglePill(title: "Pose / Skeleton", icon: "figure.walk", isOn: state.layers.pose) {
                        state.toggleLayer(\.pose)
                    }
                }

                Spacer()

                // Source & Session Indicator
                if let sess = state.currentSession {
                    HStack(spacing: 6) {
                        Circle()
                            .fill(sess.status == "running" ? Color.green : Color.orange)
                            .frame(width: 8, height: 8)
                        Text(sess.source_id)
                            .font(.system(size: 11, weight: .medium, design: .monospaced))
                            .foregroundStyle(.secondary)
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color(NSColor.controlBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Color(NSColor.windowBackgroundColor))
            .overlay(Divider(), alignment: .bottom)

            // Main Video Viewport
            ZStack {
                Color.black

                if let frame = state.currentFrame {
                    Image(nsImage: frame)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if let player = state.avPlayer {
                    NativeVideoPlayerView(player: player)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    VStack(spacing: 16) {
                        if let errorMsg = state.sessionErrorMessage {
                            VStack(spacing: 12) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .font(.system(size: 44))
                                    .foregroundStyle(.red)

                                Text("Unable to Start Analysis")
                                    .font(.title3.bold())
                                    .foregroundStyle(.white)

                                Text(errorMsg)
                                    .font(.system(size: 13, design: .monospaced))
                                    .foregroundStyle(.red.opacity(0.9))
                                    .multilineTextAlignment(.center)
                                    .padding(.horizontal, 24)

                                HStack(spacing: 12) {
                                    Button {
                                        Task {
                                            await state.retryLastSession()
                                        }
                                    } label: {
                                        Label("Retry Session", systemImage: "arrow.clockwise")
                                    }
                                    .buttonStyle(.borderedProminent)

                                    Button {
                                        state.pickAndPlayVideoFile()
                                    } label: {
                                        Label("Choose Different Video", systemImage: "folder.badge.plus")
                                    }
                                    .buttonStyle(.bordered)
                                }
                                .padding(.top, 4)
                            }
                            .padding(24)
                            .background(Color.black.opacity(0.85))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Color.red.opacity(0.3), lineWidth: 1))
                        } else if state.isSessionStarting {
                            VStack(spacing: 12) {
                                ProgressView()
                                    .controlSize(.large)
                                Text("Uploading & Starting Video Pipeline...")
                                    .font(.headline)
                                    .foregroundStyle(.white)
                            }
                        } else if state.isSessionActive {
                            Text("Waiting for live video frames...")
                                .font(.headline)
                                .foregroundStyle(.secondary)
                            ProgressView()
                                .controlSize(.small)
                        } else {
                            Image(systemName: "video.slash")
                                .font(.system(size: 48))
                                .foregroundStyle(.secondary)

                            Text("No Active Video Stream")
                                .font(.headline)
                                .foregroundStyle(.secondary)

                            Button {
                                state.pickAndPlayVideoFile()
                            } label: {
                                Label("Select Video File to Analyze", systemImage: "folder.badge.plus")
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                            }
                            .buttonStyle(.borderedProminent)
                            .controlSize(.regular)
                        }
                    }
                }

                // Top-Right Live Telemetry HUD Overlay
                if let sess = state.currentSession, state.isSessionActive {
                    VStack(alignment: .trailing, spacing: 4) {
                        HStack(spacing: 8) {
                            Text("SRC: \(String(format: "%.1f", sess.effectiveSourceFps)) FPS")
                            Text("PLAY: \(String(format: "%.1f", sess.effectivePlaybackFps)) FPS")
                            Text("INF: \(String(format: "%.1f", sess.effectiveInferenceFps)) FPS")
                            Text("LAT: \(String(format: "%.1f", sess.effectiveLatencyMs)) ms")
                        }
                        .font(.system(size: 10, weight: .semibold, design: .monospaced))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.black.opacity(0.75))
                        .clipShape(RoundedRectangle(cornerRadius: 4))

                        HStack(spacing: 8) {
                            Text("PEOPLE: \(sess.people_detected ?? 0) (ACT: \(sess.active_people ?? 0))")
                            Text("VEHICLES: \(sess.vehicles_detected ?? 0) (ACT: \(sess.active_vehicles ?? 0))")
                        }
                        .font(.system(size: 10, weight: .semibold, design: .monospaced))
                        .foregroundStyle(Color.yellow)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.black.opacity(0.75))
                        .clipShape(RoundedRectangle(cornerRadius: 4))
                    }
                    .padding(12)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            // Compact Home Clip Intelligence Bar (V3.5 / Phase 2)
            if let summary = state.lastCompletedSessionSummary {
                HStack(spacing: 16) {
                    // Left Status Badge & Core Metrics
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 8) {
                            Label("CLIP INTELLIGENCE", systemImage: "sparkles")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundStyle(Color.accentColor)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.accentColor.opacity(0.15))
                                .clipShape(RoundedRectangle(cornerRadius: 4))

                            Text("Session: \(summary.source_id ?? summary.session_id)")
                                .font(.system(size: 11, weight: .semibold, design: .monospaced))
                                .foregroundStyle(.primary)

                            Text("•")
                                .foregroundStyle(.secondary)

                            Text("\(String(format: "%.1f", summary.duration_s ?? 0.0))s (\(summary.frames_processed ?? 0) frames @ \(String(format: "%.1f", summary.fps ?? 0.0)) fps)")
                                .font(.system(size: 11, design: .monospaced))
                                .foregroundStyle(.secondary)
                        }

                        HStack(spacing: 12) {
                            // People & Vehicles
                            HStack(spacing: 4) {
                                Image(systemName: "person.2.fill")
                                    .font(.system(size: 10))
                                    .foregroundStyle(.blue)
                                Text("\(summary.tracks_summary?.person_tracks ?? 0) People")
                                    .font(.system(size: 11, weight: .medium, design: .monospaced))
                            }

                            HStack(spacing: 4) {
                                Image(systemName: "car.fill")
                                    .font(.system(size: 10))
                                    .foregroundStyle(.orange)
                                Text("\(summary.tracks_summary?.vehicle_tracks ?? 0) Vehicles")
                                    .font(.system(size: 11, weight: .medium, design: .monospaced))
                            }

                            // Security Events
                            let crit = summary.events_summary?.critical ?? 0
                            let warn = summary.events_summary?.warning ?? 0
                            let tot = summary.events_summary?.total_events ?? 0

                            HStack(spacing: 4) {
                                Image(systemName: "exclamationmark.triangle.fill")
                                    .font(.system(size: 10))
                                    .foregroundStyle(crit > 0 ? .red : (warn > 0 ? .yellow : .green))
                                Text("\(tot) Events (\(crit) Crit, \(warn) Warn)")
                                    .font(.system(size: 11, weight: .semibold, design: .monospaced))
                                    .foregroundStyle(crit > 0 ? .red : .primary)
                            }
                        }
                    }

                    Spacer()

                    // Right Quick Action Buttons
                    HStack(spacing: 10) {
                        Button {
                            state.selectedSection = .investigation
                            state.selectSession(sessionId: summary.session_id)
                        } label: {
                            Label("View Investigation", systemImage: "magnifyingglass")
                                .font(.system(size: 12, weight: .medium))
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.regular)
                        .help("Open full 7-W intelligence investigation for this clip")

                        Button {
                            state.isHermesDrawerOpen = true
                            state.askHermes(
                                prompt: "Summarize this clip and provide tactical observations on detected entities and security alerts.",
                                sessionId: summary.session_id
                            )
                        } label: {
                            Label("Ask TRINETRACHAT", systemImage: "bubble.left.and.bubble.right.fill")
                                .font(.system(size: 12, weight: .semibold))
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.regular)
                        .help("Ask Hermes assistant to analyze this clip")
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(Color(NSColor.controlBackgroundColor).opacity(0.85))
                .overlay(Divider(), alignment: .top)
            }

            // Bottom Playback Control Toolbar
            HStack(spacing: 16) {
                // Open File Button
                Button {
                    state.pickAndPlayVideoFile()
                } label: {
                    Label("Open Video", systemImage: "folder.fill")
                }
                .buttonStyle(.bordered)
                .controlSize(.small)

                Divider()
                    .frame(height: 18)

                // Play / Pause Button
                Button {
                    Task {
                        if state.isPaused {
                            await state.resumeSession()
                        } else {
                            await state.pauseSession()
                        }
                    }
                } label: {
                    Image(systemName: state.isPaused ? "play.fill" : "pause.fill")
                        .font(.system(size: 14))
                }
                .disabled(!state.isSessionActive)
                .buttonStyle(.borderedProminent)
                .controlSize(.small)
                .help(state.isPaused ? "Resume Playback" : "Pause Playback")

                // Step Forward Button
                Button {
                    Task {
                        await state.stepFrame()
                    }
                } label: {
                    Image(systemName: "forward.frame.fill")
                        .font(.system(size: 12))
                }
                .disabled(!state.isSessionActive || !state.isPaused)
                .buttonStyle(.bordered)
                .controlSize(.small)
                .help("Step 1 Frame Forward (when paused)")

                // Stop Button
                Button(role: .destructive) {
                    Task {
                        await state.stopSession()
                    }
                } label: {
                    Image(systemName: "stop.fill")
                        .font(.system(size: 12))
                }
                .disabled(!state.isSessionActive)
                .buttonStyle(.bordered)
                .controlSize(.small)
                .help("Stop Processing Session")

                Divider()
                    .frame(height: 18)

                // Playback Speed Selector
                HStack(spacing: 6) {
                    Text("Speed:")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)

                    Picker("Speed", selection: Binding(
                        get: { state.playbackSpeed },
                        set: { newSpeed in
                            Task {
                                await state.setSpeed(newSpeed)
                            }
                        }
                    )) {
                        Text("0.25x").tag(0.25)
                        Text("0.5x").tag(0.5)
                        Text("1.0x").tag(1.0)
                        Text("1.5x").tag(1.5)
                        Text("2.0x").tag(2.0)
                        Text("4.0x").tag(4.0)
                    }
                    .pickerStyle(.menu)
                    .frame(width: 85)
                    .disabled(!state.isSessionActive)
                }

                Spacer()

                // Recent Alert Ticker
                if let latestAlert = state.liveAlerts.first {
                    HStack(spacing: 6) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.system(size: 11))
                            .foregroundStyle(Color(hex: latestAlert.severityColorHex))
                        Text("\(latestAlert.formattedTime) — \(latestAlert.type)")
                            .font(.system(size: 11, weight: .medium, design: .monospaced))
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color(NSColor.controlBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 10)
            .background(Color(NSColor.windowBackgroundColor))
            .overlay(Divider(), alignment: .top)
        }
    }
}

// MARK: - Native Hardware Video Player (AVKit / AVFoundation)

struct NativeVideoPlayerView: NSViewRepresentable {
    let player: AVPlayer

    func makeNSView(context: Context) -> AVPlayerView {
        let view = AVPlayerView()
        view.player = player
        view.controlsStyle = .none
        view.showsFrameSteppingButtons = false
        view.showsSharingServiceButton = false
        view.showsFullScreenToggleButton = false
        view.videoGravity = .resizeAspect
        return view
    }

    func updateNSView(_ nsView: AVPlayerView, context: Context) {
        if nsView.player !== player {
            nsView.player = player
        }
    }
}

// MARK: - Layer Toggle Pill Subview

struct LayerTogglePill: View {
    let title: String
    let icon: String
    let isOn: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 5) {
                Image(systemName: icon)
                    .font(.system(size: 11))
                Text(title)
                    .font(.system(size: 11, weight: .medium))
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(isOn ? Color.accentColor.opacity(0.18) : Color(NSColor.controlBackgroundColor))
            .foregroundStyle(isOn ? Color.accentColor : Color.secondary)
            .overlay(
                RoundedRectangle(cornerRadius: 6)
                    .stroke(isOn ? Color.accentColor.opacity(0.5) : Color.clear, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 6))
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Color Hex Extension

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (1, 1, 1, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue:  Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
