import SwiftUI
import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        for window in NSApp.windows {
            window.makeKeyAndOrderFront(nil)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}

@main
struct TrinetraApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @State private var appState = AppState()

    init() {
        NSApplication.shared.setActivationPolicy(.regular)
        NSApplication.shared.activate(ignoringOtherApps: true)
    }

    var body: some Scene {
        WindowGroup {
            MainShellView()
                .environment(appState)
                .frame(minWidth: 1050, minHeight: 680)
                .onAppear {
                    NSApp.setActivationPolicy(.regular)
                    NSApp.activate(ignoringOtherApps: true)
                }
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified(showsTitle: true))
        .commands {
            // File Menu Commands
            CommandGroup(replacing: .newItem) {
                Button("Open Video File...") {
                    appState.pickAndPlayVideoFile()
                }
                .keyboardShortcut("o", modifiers: .command)

                Divider()

                Button("Stop Session") {
                    Task {
                        await appState.stopSession()
                    }
                }
                .keyboardShortcut(".", modifiers: .command)
                .disabled(!appState.isSessionActive)
            }

            // Playback Menu Commands
            CommandMenu("Playback") {
                Button(appState.isPaused ? "Resume Playback" : "Pause Playback") {
                    Task {
                        if appState.isPaused {
                            await appState.resumeSession()
                        } else {
                            await appState.pauseSession()
                        }
                    }
                }
                .keyboardShortcut(.space, modifiers: [])
                .disabled(!appState.isSessionActive)

                Button("Step 1 Frame Forward") {
                    Task {
                        await appState.stepFrame()
                    }
                }
                .keyboardShortcut(.rightArrow, modifiers: [.command])
                .disabled(!appState.isSessionActive || !appState.isPaused)

                Divider()

                Menu("Playback Speed") {
                    Button("0.25x") { Task { await appState.setSpeed(0.25) } }
                    Button("0.5x")  { Task { await appState.setSpeed(0.5) } }
                    Button("1.0x (Normal)") { Task { await appState.setSpeed(1.0) } }
                    Button("1.5x")  { Task { await appState.setSpeed(1.5) } }
                    Button("2.0x")  { Task { await appState.setSpeed(2.0) } }
                    Button("4.0x")  { Task { await appState.setSpeed(4.0) } }
                }
                .disabled(!appState.isSessionActive)
            }

            // View Menu Commands
            CommandGroup(after: .sidebar) {
                Button("Toggle Hermes Assistant") {
                    withAnimation {
                        appState.isHermesDrawerOpen.toggle()
                    }
                }
                .keyboardShortcut("k", modifiers: [.command])

                Divider()

                Button("Toggle Bounding Boxes") {
                    appState.toggleLayer(\.boxes)
                }
                .keyboardShortcut("1", modifiers: [.command])

                Button("Toggle Track IDs") {
                    appState.toggleLayer(\.labels)
                }
                .keyboardShortcut("2", modifiers: [.command])

                Button("Toggle Trajectories") {
                    appState.toggleLayer(\.trajectories)
                }
                .keyboardShortcut("3", modifiers: [.command])

                Button("Toggle Virtual Zones") {
                    appState.toggleLayer(\.zones)
                }
                .keyboardShortcut("4", modifiers: [.command])

                Button("Toggle Pose / Skeleton") {
                    appState.toggleLayer(\.pose)
                }
                .keyboardShortcut("5", modifiers: [.command])

                Button("Toggle Faces") {
                    appState.toggleLayer(\.faces)
                }
                .keyboardShortcut("6", modifiers: [.command])
            }
        }
    }
}
