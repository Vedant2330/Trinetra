import Foundation
import SwiftUI
import AppKit
import Combine
import AVFoundation
import AVKit

public enum NavSection: String, CaseIterable, Identifiable {
    case liveOperations = "Live Operations"
    case events = "Events & Alerts"
    case investigation = "Investigation"
    case analytics = "Analytics"
    case geography = "Geography / GIS"
    case reidGallery = "Re-ID Gallery"
    case sources = "Sources & Cameras"
    case diagnostics = "System Diagnostics"

    public var id: String { rawValue }

    public var icon: String {
        switch self {
        case .liveOperations: return "video.fill"
        case .events: return "exclamationmark.triangle.fill"
        case .investigation: return "magnifyingglass"
        case .analytics: return "chart.xyaxis.line"
        case .geography: return "map.fill"
        case .reidGallery: return "person.2.badge.gearshape.fill"
        case .sources: return "camera.fill"
        case .diagnostics: return "waveform.path.ecg"
        }
    }
}

public struct HermesChatMessage: Identifiable, Hashable, Sendable {
    public let id: UUID
    public let isUser: Bool
    public let text: String
    public let timestamp: Date
    public let latencyMs: Double?
    public let isError: Bool
    public let eventId: String?
    public let sessionId: String?

    public var taxonomyCounts: [String: Int] {
        var counts: [String: Int] = [:]
        let observedCount = text.components(separatedBy: "[OBSERVED]").count - 1
        let derivedCount = text.components(separatedBy: "[DERIVED]").count - 1
        let inferredCount = text.components(separatedBy: "[INFERRED]").count - 1
        if observedCount > 0 { counts["OBSERVED"] = observedCount }
        if derivedCount > 0 { counts["DERIVED"] = derivedCount }
        if inferredCount > 0 { counts["INFERRED"] = inferredCount }
        return counts
    }

    public init(
        id: UUID = UUID(),
        isUser: Bool,
        text: String,
        timestamp: Date = Date(),
        latencyMs: Double? = nil,
        isError: Bool = false,
        eventId: String? = nil,
        sessionId: String? = nil
    ) {
        self.id = id
        self.isUser = isUser
        self.text = text
        self.timestamp = timestamp
        self.latencyMs = latencyMs
        self.isError = isError
        self.eventId = eventId
        self.sessionId = sessionId
    }
}

@Observable
@MainActor
public final class AppState {
    public var selectedSection: NavSection = .liveOperations
    public var isHermesDrawerOpen: Bool = false

    // Backend Connection & Health
    public var isBackendOnline: Bool = false
    public var health: HealthResponse?
    public var lastHealthCheck: Date?

    // Session State
    public var isSessionActive: Bool = false
    public var isSessionStarting: Bool = false
    public var sessionErrorMessage: String?
    public var lastSelectedFileURL: URL?
    public var currentSession: SessionPayload?
    public var lastCompletedSessionSummary: SessionSummaryResponse?
    public var currentFrame: NSImage?
    public var avPlayer: AVPlayer?
    public var isPaused: Bool = false
    public var playbackSpeed: Double = 1.0

    // Render Layers
    public var layers: LayerState = LayerState()

    // Events & Real-time Alerts
    public var events: [EventRow] = []
    public var liveAlerts: [EventRow] = []
    public var selectedEvent: EventRow?
    public var selectedEventSummary: EventSummaryResponse?
    public var selectedEventSnapshot: NSImage?
    public var isSnapshotLoading: Bool = false
    public var isEventSummaryLoading: Bool = false

    // Historical Investigation & 7-W Incident Intelligence
    public var sessionHistory: [SessionHistoryItem] = []
    public var selectedSessionId: String?
    public var selectedSessionSummary: SessionSummaryResponse?
    public var selectedSessionTracks: [SessionTrackRow] = []
    public var isInvestigationLoading: Bool = false

    // Sources & Zones
    public var sources: [SourceItem] = []
    public var zones: [ZoneModel] = []
    public var selectedSourceId: String?

    // Re-ID Gallery
    public var reidPersons: [ReIDPersonSummary] = []
    public var selectedPerson: ReIDPersonSummary?

    // GIS Map
    public var mapConfig: MapConfigResponse?
    public var mapSectors: [GeoSector] = []
    public var mapCameras: [MapCameraItem] = []
    public var selectedMapCameraId: String?

    // Hermes Assistant (trinetraChat)
    public var hermesMessages: [HermesChatMessage] = []
    public var isHermesThinking: Bool = false
    public var hermesStatus: HermesStatusResponse?

    // Services
    public let apiClient: APIClient
    private var mjpegStreamer: MJPEGStreamer?
    private var sseClient: SSEClient?
    private var pollTimer: Timer?

    public init(apiClient: APIClient = APIClient()) {
        self.apiClient = apiClient
        startPolling()
        startSSE()
        refreshAll()
    }

    // MARK: - Health & Status Polling

    public func refreshAll() {
        Task {
            await refreshHealth()
            await refreshSessionStatus()
            await refreshSources()
            await refreshZones()
            await refreshEvents()
            await refreshSessionHistory()
            await refreshReIDPersons()
            await refreshMapData()
            await refreshHermesStatus()
        }
    }

    private func startPolling() {
        pollTimer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.refreshHealth()
                await self?.refreshSessionStatus()
            }
        }
    }

    public func refreshHealth() async {
        do {
            let h = try await apiClient.fetchHealth()
            self.health = h
            self.isBackendOnline = true
            self.lastHealthCheck = Date()
        } catch {
            self.isBackendOnline = false
        }
    }

    public func refreshSessionStatus() async {
        let wasActive = self.isSessionActive
        do {
            let statusResp = try await apiClient.fetchSessionStatus()
            self.isSessionActive = statusResp.active
            self.currentSession = statusResp.session
            if let sess = statusResp.session {
                self.isPaused = sess.is_paused ?? false
                self.playbackSpeed = sess.speed ?? 1.0
                if mjpegStreamer == nil && statusResp.active {
                    startMJPEGStream()
                }
            } else {
                if mjpegStreamer != nil {
                    stopMJPEGStream()
                }
                if self.avPlayer != nil {
                    self.avPlayer?.pause()
                    self.avPlayer = nil
                }
                if wasActive && !statusResp.active {
                    // Session just completed — refresh history and load clip intelligence
                    await refreshSessionHistory()
                    if let first = sessionHistory.first {
                        do {
                            self.lastCompletedSessionSummary = try await apiClient.fetchSessionSummary(sessionId: first.id)
                        } catch {}
                    }
                }
            }
        } catch {}
    }

    public func refreshSources() async {
        do {
            self.sources = try await apiClient.fetchSources()
        } catch {}
    }

    public func refreshZones() async {
        do {
            self.zones = try await apiClient.fetchZones()
        } catch {}
    }

    public func refreshEvents() async {
        do {
            let res = try await apiClient.fetchEvents(limit: 100)
            self.events = res.events
        } catch {}
    }

    public func refreshSessionHistory() async {
        do {
            self.sessionHistory = try await apiClient.fetchSessions(limit: 30)
            if let first = sessionHistory.first {
                if selectedSessionId == nil {
                    selectSession(sessionId: first.id)
                }
                if lastCompletedSessionSummary == nil {
                    do {
                        self.lastCompletedSessionSummary = try await apiClient.fetchSessionSummary(sessionId: first.id)
                    } catch {}
                }
            }
        } catch {}
    }

    public func refreshReIDPersons() async {
        do {
            self.reidPersons = try await apiClient.fetchReIDPersons()
        } catch {}
    }

    public func refreshMapData() async {
        do {
            self.mapConfig = try await apiClient.fetchMapConfig()
            self.mapSectors = try await apiClient.fetchMapSectors()
            self.mapCameras = try await apiClient.fetchMapCameras()
        } catch {}
    }

    public func updateCameraGeo(sourceId: String, lat: Double, lng: Double, label: String = "") async {
        do {
            try await apiClient.updateCameraGeo(sourceId: sourceId, latitude: lat, longitude: lng, label: label)
            await refreshMapData()
        } catch {
            print("Failed to update camera geo: \(error.localizedDescription)")
        }
    }

    public func seedDemoSources() async {
        do {
            _ = try await apiClient.seedDemoSources()
            await refreshSources()
            await refreshMapData()
        } catch {
            print("Failed to seed demo sources: \(error.localizedDescription)")
        }
    }

    public func registerCameraSource(
        id: String,
        name: String?,
        type: String,
        uri: String?,
        latitude: Double?,
        longitude: Double?,
        label: String?,
        status: String?
    ) async throws {
        let req = SourceCreateRequest(
            id: id,
            name: name,
            type: type,
            uri: uri,
            latitude: latitude,
            longitude: longitude,
            label: label,
            status: status
        )
        try await apiClient.registerSource(request: req)
        await refreshSources()
        await refreshMapData()
    }

    public func navigateToCameraOnMap(sourceId: String) {
        self.selectedMapCameraId = sourceId
        self.selectedSection = .geography
    }

    public func refreshHermesStatus() async {
        do {
            self.hermesStatus = try await apiClient.fetchHermesStatus()
        } catch {}
    }

    // MARK: - Streaming & Real-Time Alerts

    public func startMJPEGStream() {
        stopMJPEGStream()
        let url = apiClient.baseURL.appendingPathComponent("api/stream.mjpg")
        let streamer = MJPEGStreamer(
            url: url,
            onFrame: { [weak self] image in
                Task { @MainActor in
                    self?.currentFrame = image
                }
            },
            onError: { error in
                print("MJPEG Stream Error: \(error.localizedDescription)")
            }
        )
        self.mjpegStreamer = streamer
        streamer.start()
    }

    public func stopMJPEGStream() {
        mjpegStreamer?.stop()
        mjpegStreamer = nil
        currentFrame = nil
    }

    private func startSSE() {
        let url = apiClient.baseURL.appendingPathComponent("api/events/stream")
        let sse = SSEClient(
            url: url,
            onEvent: { [weak self] event in
                Task { @MainActor in
                    self?.handleNewEvent(event)
                }
            },
            onError: { error in
                print("SSE Error: \(error.localizedDescription)")
            }
        )
        self.sseClient = sse
        sse.start()
    }

    private func handleNewEvent(_ event: EventRow) {
        events.insert(event, at: 0)
        liveAlerts.insert(event, at: 0)
        if liveAlerts.count > 30 {
            liveAlerts.removeLast()
        }
    }

    // MARK: - Playback Actions

    public func pickAndPlayVideoFile() {
        let panel = NSOpenPanel()
        panel.title = "Select Video Source for TRINETRA"
        panel.allowedContentTypes = [.movie, .quickTimeMovie, .mpeg4Movie]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.canChooseFiles = true

        if panel.runModal() == .OK, let selectedURL = panel.url {
            Task {
                await startVideoFileSession(fileURL: selectedURL)
            }
        }
    }

    public func startVideoFileSession(fileURL: URL) async {
        self.sessionErrorMessage = nil
        self.isSessionStarting = true
        self.lastSelectedFileURL = fileURL
        do {
            let uploadResp = try await apiClient.uploadVideoFile(fileURL: fileURL)
            let req = StartSessionRequest(type: "file", path: uploadResp.path)
            let sess = try await apiClient.startSession(request: req)
            self.currentSession = sess
            self.isSessionActive = true
            self.isPaused = false
            self.isSessionStarting = false

            // Configure hardware-accelerated AVPlayer on real media clock
            self.avPlayer?.pause()
            let player = AVPlayer(url: fileURL)
            player.actionAtItemEnd = .pause
            self.avPlayer = player
            player.playImmediately(atRate: Float(self.playbackSpeed))

            startMJPEGStream()
            await refreshLayers()
            await refreshSessionHistory()
        } catch {
            print("Failed to start session with file: \(error.localizedDescription)")
            self.sessionErrorMessage = error.localizedDescription
            self.isSessionActive = false
            self.isSessionStarting = false
            self.avPlayer?.pause()
            self.avPlayer = nil
            stopMJPEGStream()
        }
    }

    public func retryLastSession() async {
        if let url = lastSelectedFileURL {
            await startVideoFileSession(fileURL: url)
        }
    }

    public func startLocalFileSessionDirect(path: String) async {
        self.sessionErrorMessage = nil
        self.isSessionStarting = true
        let fileURL = URL(fileURLWithPath: path)
        self.lastSelectedFileURL = fileURL
        do {
            let req = StartSessionRequest(type: "file", path: path)
            let sess = try await apiClient.startSession(request: req)
            self.currentSession = sess
            self.isSessionActive = true
            self.isPaused = false
            self.isSessionStarting = false

            // Configure hardware-accelerated AVPlayer on real media clock
            self.avPlayer?.pause()
            let player = AVPlayer(url: fileURL)
            player.actionAtItemEnd = .pause
            self.avPlayer = player
            player.playImmediately(atRate: Float(self.playbackSpeed))

            startMJPEGStream()
            await refreshLayers()
            await refreshSessionHistory()
        } catch {
            print("Failed to start direct file session: \(error.localizedDescription)")
            self.sessionErrorMessage = error.localizedDescription
            self.isSessionActive = false
            self.isSessionStarting = false
            self.avPlayer?.pause()
            self.avPlayer = nil
            stopMJPEGStream()
        }
    }

    public func startWebcamSession(index: Int = 0) async {
        self.sessionErrorMessage = nil
        self.isSessionStarting = true
        self.avPlayer?.pause()
        self.avPlayer = nil
        do {
            let req = StartSessionRequest(type: "webcam", index: index)
            let sess = try await apiClient.startSession(request: req)
            self.currentSession = sess
            self.isSessionActive = true
            self.isPaused = false
            self.isSessionStarting = false
            startMJPEGStream()
            await refreshLayers()
        } catch {
            print("Webcam session start failed: \(error.localizedDescription)")
            self.sessionErrorMessage = error.localizedDescription
            self.isSessionActive = false
            self.isSessionStarting = false
            stopMJPEGStream()
        }
    }

    public func startRtspSession(url: String) async {
        self.sessionErrorMessage = nil
        self.isSessionStarting = true
        self.avPlayer?.pause()
        self.avPlayer = nil
        do {
            let req = StartSessionRequest(type: "rtsp", uri: url)
            let sess = try await apiClient.startSession(request: req)
            self.currentSession = sess
            self.isSessionActive = true
            self.isPaused = false
            self.isSessionStarting = false
            startMJPEGStream()
            await refreshLayers()
        } catch {
            print("RTSP session start failed: \(error.localizedDescription)")
            self.sessionErrorMessage = error.localizedDescription
            self.isSessionActive = false
            self.isSessionStarting = false
            stopMJPEGStream()
        }
    }

    public func stopSession() async {
        do {
            try await apiClient.stopSession()
            self.isSessionActive = false
            self.currentSession = nil
            self.avPlayer?.pause()
            self.avPlayer = nil
            stopMJPEGStream()
            await refreshSessionHistory()
            if let first = sessionHistory.first {
                do {
                    self.lastCompletedSessionSummary = try await apiClient.fetchSessionSummary(sessionId: first.id)
                } catch {}
            }
        } catch {
            self.avPlayer?.pause()
            self.avPlayer = nil
        }
    }

    public func pauseSession() async {
        self.avPlayer?.pause()
        self.isPaused = true
        do {
            try await apiClient.pauseSession()
        } catch {}
    }

    public func resumeSession() async {
        self.avPlayer?.playImmediately(atRate: Float(self.playbackSpeed))
        self.isPaused = false
        do {
            try await apiClient.resumeSession()
        } catch {}
    }

    public func stepFrame() async {
        if let player = avPlayer, let item = player.currentItem {
            let stepSeconds = 1.0 / (currentSession?.effectiveSourceFps ?? 25.0)
            let newTime = CMTimeAdd(item.currentTime(), CMTime(seconds: stepSeconds, preferredTimescale: 600))
            await player.seek(to: newTime, toleranceBefore: .zero, toleranceAfter: .zero)
        }
        do {
            try await apiClient.stepFrame()
        } catch {}
    }

    public func setSpeed(_ speed: Double) async {
        self.playbackSpeed = speed
        if !self.isPaused {
            self.avPlayer?.rate = Float(speed)
        }
        do {
            try await apiClient.setSpeed(speed: speed)
        } catch {}
    }

    public func seekTo(timestamp: Double) async {
        let targetTime = CMTime(seconds: timestamp, preferredTimescale: 600)
        await self.avPlayer?.seek(to: targetTime, toleranceBefore: .zero, toleranceAfter: .zero)
        do {
            try await apiClient.seekSession(timestamp: timestamp)
        } catch {
            print("Seek failed: \(error.localizedDescription)")
        }
    }

    // MARK: - Layer Toggles

    public func refreshLayers() async {
        do {
            self.layers = try await apiClient.fetchLayers()
        } catch {}
    }

    public func toggleLayer(_ keyPath: WritableKeyPath<LayerState, Bool>) {
        layers[keyPath: keyPath].toggle()
        Task {
            do {
                self.layers = try await apiClient.updateLayers(layers)
            } catch {
                print("Failed to update layer: \(error.localizedDescription)")
            }
        }
    }

    // MARK: - Event Selection, Summary & Snapshot

    public func selectEvent(_ event: EventRow) {
        self.selectedEvent = event
        self.selectedEventSummary = nil
        self.selectedEventSnapshot = nil
        self.isSnapshotLoading = true
        self.isEventSummaryLoading = true

        Task {
            // Seek playback to event canonical video timestamp
            if let vts = event.video_ts {
                await self.seekTo(timestamp: vts)
            }

            // Fetch deterministic 7-W structured summary
            do {
                let summary = try await apiClient.fetchEventSummary(eventId: event.id)
                self.selectedEventSummary = summary
            } catch {
                print("Failed to load event summary: \(error.localizedDescription)")
            }
            self.isEventSummaryLoading = false

            // Fetch snapshot image if available
            do {
                let data = try await apiClient.fetchEventSnapshot(eventId: event.id)
                if let img = NSImage(data: data) {
                    self.selectedEventSnapshot = img
                }
            } catch {
                print("Failed to load event snapshot: \(error.localizedDescription)")
            }
            self.isSnapshotLoading = false
        }
    }

    public func ackSelectedEvent() {
        guard let ev = selectedEvent else { return }
        Task {
            do {
                try await apiClient.ackEvent(eventId: ev.id)
                await refreshEvents()
            } catch {}
        }
    }

    // MARK: - Investigation & Session Analysis

    public func selectSession(sessionId: String) {
        self.selectedSessionId = sessionId
        self.selectedSessionSummary = nil
        self.selectedSessionTracks = []
        self.isInvestigationLoading = true

        Task {
            do {
                let summary = try await apiClient.fetchSessionSummary(sessionId: sessionId)
                self.selectedSessionSummary = summary
            } catch {
                print("Failed to fetch session summary: \(error.localizedDescription)")
            }

            do {
                let tracksResp = try await apiClient.fetchSessionTracks(sessionId: sessionId)
                self.selectedSessionTracks = tracksResp.tracks
            } catch {
                print("Failed to fetch session tracks: \(error.localizedDescription)")
            }

            self.isInvestigationLoading = false
        }
    }

    // MARK: - Hermes Copilot (trinetraChat)

    public func clearHermesChat() {
        hermesMessages.removeAll()
    }

    public func askHermes(prompt: String, eventId: String? = nil, sessionId: String? = nil) {
        let activeEventId = eventId ?? selectedEvent?.id
        let activeSessionId = sessionId ?? selectedSessionId ?? currentSession?.source_id

        let userMsg = HermesChatMessage(
            isUser: true,
            text: prompt,
            eventId: activeEventId,
            sessionId: activeSessionId
        )
        hermesMessages.append(userMsg)
        isHermesThinking = true

        Task {
            do {
                let resp = try await apiClient.askHermes(
                    query: prompt,
                    eventId: activeEventId,
                    sessionId: activeSessionId
                )
                let botMsg = HermesChatMessage(
                    isUser: false,
                    text: resp.answer,
                    latencyMs: resp.elapsed_ms,
                    eventId: resp.grounded_event_id,
                    sessionId: resp.grounded_session_id
                )
                self.hermesMessages.append(botMsg)
            } catch {
                let errorMsg = HermesChatMessage(
                    isUser: false,
                    text: error.localizedDescription,
                    isError: true,
                    eventId: activeEventId,
                    sessionId: activeSessionId
                )
                self.hermesMessages.append(errorMsg)
            }
            self.isHermesThinking = false
        }
    }
}
