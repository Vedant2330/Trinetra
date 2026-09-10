import SwiftUI
import AppKit

public struct SourcesView: View {
    @Environment(AppState.self) private var state

    @State private var rtspUrlInput: String = ""
    @State private var webcamIndex: Int = 0
    @State private var isAddCameraPresented: Bool = false
    @State private var isSeedingDemo: Bool = false
    @State private var seedMessage: String?

    public init() {}

    public var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                // Header Banner & Action Bar
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Image(systemName: "camera.fill")
                                .font(.title)
                                .foregroundStyle(Color.accentColor)
                            Text("Sources & Video Stream Feeds")
                                .font(.title2.bold())
                        }
                        Text("Ingest offline surveillance video files, live Webcams, RTSP / ONVIF IP cameras, and GIS-mapped perimeter sensor feeds.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    HStack(spacing: 12) {
                        Button {
                            Task {
                                isSeedingDemo = true
                                await state.seedDemoSources()
                                isSeedingDemo = false
                                seedMessage = "Seeded 8 demo cameras & 2 GIS sectors"
                                DispatchQueue.main.asyncAfter(deadline: .now() + 3.0) {
                                    seedMessage = nil
                                }
                            }
                        } label: {
                            HStack(spacing: 6) {
                                if isSeedingDemo {
                                    ProgressView().controlSize(.small)
                                } else {
                                    Image(systemName: "sparkles")
                                }
                                Text("Seed Demo Cameras")
                            }
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.regular)
                        .disabled(isSeedingDemo)
                        .help("Idempotently seed standard demo perimeter cameras (CAM-01..CAM-08) and defense sectors")

                        Button {
                            isAddCameraPresented = true
                        } label: {
                            Label("Add Camera", systemImage: "plus.circle.fill")
                        }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.regular)
                    }
                }
                .padding(.horizontal, 24)
                .padding(.top, 20)

                // Flash Notification
                if let msg = seedMessage {
                    HStack(spacing: 8) {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                        Text(msg)
                            .font(.system(size: 12, weight: .medium))
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 8)
                    .background(Color.green.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .padding(.horizontal, 24)
                }

                // Quick Launch Stream Cards
                VStack(alignment: .leading, spacing: 12) {
                    Text("LAUNCH NEW SURVEILLANCE FEED")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 24)

                    LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible()), GridItem(.flexible())], spacing: 16) {
                        // Card 1: Local Video File
                        SourceLaunchCard(
                            title: "Video File",
                            subtitle: "MP4, MOV, MKV, AVI",
                            icon: "film.fill",
                            color: .blue
                        ) {
                            state.pickAndPlayVideoFile()
                        }

                        // Card 2: Local Hardware Webcam
                        SourceLaunchCard(
                            title: "Built-in / USB Camera",
                            subtitle: "Index \(webcamIndex) (FaceTime HD)",
                            icon: "video.fill",
                            color: .green
                        ) {
                            Task {
                                await state.startWebcamSession(index: webcamIndex)
                            }
                        }

                        // Card 3: RTSP Network Stream
                        VStack(alignment: .leading, spacing: 10) {
                            HStack {
                                Image(systemName: "network")
                                    .foregroundStyle(Color.purple)
                                Text("RTSP Stream")
                                    .font(.system(size: 13, weight: .bold))
                            }

                            TextField("rtsp://admin:pass@ip:554/live", text: $rtspUrlInput)
                                .textFieldStyle(.roundedBorder)
                                .font(.system(size: 11, design: .monospaced))

                            Button {
                                guard !rtspUrlInput.isEmpty else { return }
                                Task {
                                    await state.startRtspSession(url: rtspUrlInput)
                                }
                            } label: {
                                Text("Connect Stream")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.borderedProminent)
                            .controlSize(.small)
                            .disabled(rtspUrlInput.isEmpty)
                        }
                        .padding(14)
                        .background(Color(NSColor.controlBackgroundColor))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(Color.secondary.opacity(0.15), lineWidth: 1)
                        )
                    }
                    .padding(.horizontal, 24)
                }

                Divider()
                    .padding(.horizontal, 24)

                // Active & Registered Sources List
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("REGISTERED CAMERA REGISTRY & GIS FEEDS (\(state.sources.count))")
                            .font(.system(size: 11, weight: .bold))
                            .foregroundStyle(.secondary)

                        Spacer()

                        Button {
                            Task {
                                await state.refreshSources()
                                await state.refreshMapData()
                            }
                        } label: {
                            Image(systemName: "arrow.clockwise")
                                .font(.system(size: 11))
                        }
                        .buttonStyle(.plain)
                        .help("Refresh Camera Registry")
                    }
                    .padding(.horizontal, 24)

                    if state.sources.isEmpty {
                        VStack(spacing: 12) {
                            Image(systemName: "video.slash")
                                .font(.system(size: 36))
                                .foregroundStyle(.secondary)
                            Text("No Camera Sources Registered")
                                .font(.headline)
                                .foregroundStyle(.secondary)
                            Text("Click 'Seed Demo Cameras' above to quickly populate 6 demo perimeter cameras, or '+ Add Camera' to register a custom feed.")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.center)
                                .frame(maxWidth: 400)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 32)
                    } else {
                        VStack(spacing: 10) {
                            ForEach(state.sources) { src in
                                HStack(spacing: 14) {
                                    // Status Circle Indicator
                                    Circle()
                                        .fill(src.isLiveActive ? Color.green : (src.isDemo ? Color.purple : Color.secondary.opacity(0.5)))
                                        .frame(width: 10, height: 10)

                                    // Main Camera Info
                                    VStack(alignment: .leading, spacing: 3) {
                                        HStack(spacing: 8) {
                                            Text(src.name ?? src.id)
                                                .font(.system(size: 13, weight: .semibold))

                                            Text(src.id)
                                                .font(.system(size: 11, weight: .bold, design: .monospaced))
                                                .padding(.horizontal, 6)
                                                .padding(.vertical, 1)
                                                .background(Color.secondary.opacity(0.12))
                                                .clipShape(RoundedRectangle(cornerRadius: 4))

                                            if src.isLiveActive {
                                                Text("LIVE")
                                                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                                                    .foregroundStyle(.green)
                                                    .padding(.horizontal, 6)
                                                    .padding(.vertical, 2)
                                                    .background(Color.green.opacity(0.15))
                                                    .clipShape(RoundedRectangle(cornerRadius: 4))
                                            } else if src.isDemo {
                                                Text("DEMO")
                                                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                                                    .foregroundStyle(.purple)
                                                    .padding(.horizontal, 6)
                                                    .padding(.vertical, 2)
                                                    .background(Color.purple.opacity(0.15))
                                                    .clipShape(RoundedRectangle(cornerRadius: 4))
                                            }
                                        }

                                        HStack(spacing: 12) {
                                            Label(src.type.uppercased(), systemImage: src.type == "rtsp" ? "network" : (src.type == "webcam" ? "video" : "film"))
                                                .font(.system(size: 10, design: .monospaced))
                                                .foregroundStyle(.secondary)

                                            if let lat = src.effectiveLat, let lng = src.effectiveLng {
                                                Label(String(format: "%.4f° N, %.4f° E", lat, lng), systemImage: "mappin.and.ellipse")
                                                    .font(.system(size: 10, design: .monospaced))
                                                    .foregroundStyle(.secondary)
                                            }

                                            if let label = src.label, !label.isEmpty {
                                                Text("• \(label)")
                                                    .font(.system(size: 10))
                                                    .foregroundStyle(.secondary)
                                            }
                                        }
                                    }

                                    Spacer()

                                    // Action Buttons
                                    HStack(spacing: 8) {
                                        if src.effectiveLat != nil && src.effectiveLng != nil {
                                            Button {
                                                state.navigateToCameraOnMap(sourceId: src.id)
                                            } label: {
                                                Label("Show on Map", systemImage: "map.fill")
                                                    .font(.system(size: 11))
                                            }
                                            .buttonStyle(.bordered)
                                            .controlSize(.small)
                                            .help("View this camera's location and sensor cone on the GIS Tactical Map")
                                        }

                                        if src.type == "rtsp", let uri = src.path, !uri.isEmpty {
                                            Button {
                                                Task {
                                                    await state.startRtspSession(url: uri)
                                                }
                                            } label: {
                                                Label("Connect", systemImage: "play.fill")
                                                    .font(.system(size: 11))
                                            }
                                            .buttonStyle(.borderedProminent)
                                            .controlSize(.small)
                                        }
                                    }
                                }
                                .padding(12)
                                .background(Color(NSColor.controlBackgroundColor))
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 8)
                                        .stroke(Color.secondary.opacity(0.12), lineWidth: 1)
                                )
                            }
                        }
                        .padding(.horizontal, 24)
                    }
                }

                Divider()
                    .padding(.horizontal, 24)

                // Defined Virtual Intrusion Zones List
                VStack(alignment: .leading, spacing: 12) {
                    Text("VIRTUAL INTRUSION ZONES & TRIPWIRES")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 24)

                    if state.zones.isEmpty {
                        VStack(spacing: 8) {
                            Image(systemName: "shield.slash")
                                .font(.system(size: 28))
                                .foregroundStyle(.secondary)
                            Text("No Virtual Zones Defined")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                    } else {
                        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                            ForEach(state.zones) { zone in
                                VStack(alignment: .leading, spacing: 6) {
                                    HStack {
                                        Image(systemName: "shield.lefthalf.filled")
                                            .foregroundStyle(Color.accentColor)
                                        Text(zone.name)
                                            .font(.system(size: 12, weight: .bold))
                                        Spacer()
                                        Text(zone.type.uppercased())
                                            .font(.system(size: 9, weight: .heavy, design: .monospaced))
                                            .foregroundStyle(.secondary)
                                    }
                                    Text("\(zone.polygon.count) Polygon Coordinate Vertices • Camera: \(zone.source_id)")
                                        .font(.system(size: 10))
                                        .foregroundStyle(.secondary)
                                }
                                .padding(12)
                                .background(Color(NSColor.controlBackgroundColor))
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                            }
                        }
                        .padding(.horizontal, 24)
                    }
                }
            }
            .padding(.bottom, 32)
        }
        .sheet(isPresented: $isAddCameraPresented) {
            AddCameraModalView(isPresented: $isAddCameraPresented)
        }
    }
}

// MARK: - Add Camera Modal Sheet

struct AddCameraModalView: View {
    @Environment(AppState.self) private var state
    @Binding var isPresented: Bool

    @State private var cameraId: String = ""
    @State private var cameraName: String = ""
    @State private var streamType: String = "rtsp"
    @State private var streamUri: String = ""
    @State private var latitudeStr: String = "28.6139"
    @State private var longitudeStr: String = "77.2090"
    @State private var labelText: String = ""
    @State private var isSaving: Bool = false
    @State private var errorMessage: String?

    var parsedLat: Double? {
        Double(latitudeStr.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    var parsedLng: Double? {
        Double(longitudeStr.trimmingCharacters(in: .whitespacesAndNewlines))
    }

    var isCoordinatesValid: Bool {
        guard let lat = parsedLat, let lng = parsedLng else { return false }
        return lat >= -90.0 && lat <= 90.0 && lng >= -180.0 && lng <= 180.0
    }

    var isFormValid: Bool {
        !cameraId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && isCoordinatesValid
    }

    var body: some View {
        VStack(spacing: 0) {
            // Modal Header
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Register New Camera Source")
                        .font(.headline)
                    Text("Enter camera stream details and GIS latitude/longitude coordinates")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button {
                    isPresented = false
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
            }
            .padding(16)
            .background(Color(NSColor.windowBackgroundColor))
            .overlay(Divider(), alignment: .bottom)

            // Form Content
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let err = errorMessage {
                        HStack(spacing: 8) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundStyle(.red)
                            Text(err)
                                .font(.system(size: 11))
                                .foregroundStyle(.red)
                        }
                        .padding(10)
                        .background(Color.red.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                    }

                    // Identification Group
                    VStack(alignment: .leading, spacing: 8) {
                        Text("IDENTIFICATION")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundStyle(.secondary)

                        HStack(spacing: 12) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Camera ID *")
                                    .font(.system(size: 11, weight: .medium))
                                TextField("e.g. CAM-07", text: $cameraId)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                            }

                            VStack(alignment: .leading, spacing: 4) {
                                Text("Display Name")
                                    .font(.system(size: 11, weight: .medium))
                                TextField("e.g. East Perimeter Gate", text: $cameraName)
                                    .textFieldStyle(.roundedBorder)
                            }
                        }
                    }

                    Divider()

                    // Stream Configuration
                    VStack(alignment: .leading, spacing: 8) {
                        Text("STREAM CONFIGURATION")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundStyle(.secondary)

                        Picker("Stream Type", selection: $streamType) {
                            Text("RTSP / IP Stream").tag("rtsp")
                            Text("Local Hardware Webcam").tag("webcam")
                            Text("Surveillance Video File").tag("file")
                            Text("Demo Simulated Feed").tag("demo")
                        }
                        .pickerStyle(.segmented)

                        if streamType == "rtsp" {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("RTSP Stream URI")
                                    .font(.system(size: 11, weight: .medium))
                                TextField("rtsp://admin:password@192.168.1.100:554/live", text: $streamUri)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                            }
                        } else if streamType == "file" {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Local Video File Path")
                                    .font(.system(size: 11, weight: .medium))
                                TextField("/path/to/video.mp4", text: $streamUri)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                            }
                        }
                    }

                    Divider()

                    // Geographic Coordinates
                    VStack(alignment: .leading, spacing: 8) {
                        HStack {
                            Text("GIS GEOLOCATION COORDINATES")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundStyle(.secondary)
                            Spacer()
                            Button("Reset to Command Center") {
                                latitudeStr = "28.6139"
                                longitudeStr = "77.2090"
                            }
                            .buttonStyle(.plain)
                            .font(.system(size: 10, weight: .medium))
                            .foregroundStyle(Color.accentColor)
                        }

                        HStack(spacing: 12) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Latitude (-90.0 to 90.0)")
                                    .font(.system(size: 11, weight: .medium))
                                TextField("28.6139", text: $latitudeStr)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                            }

                            VStack(alignment: .leading, spacing: 4) {
                                Text("Longitude (-180.0 to 180.0)")
                                    .font(.system(size: 11, weight: .medium))
                                TextField("77.2090", text: $longitudeStr)
                                    .textFieldStyle(.roundedBorder)
                                    .font(.system(size: 11, design: .monospaced))
                            }
                        }

                        if !isCoordinatesValid {
                            Text("Coordinates must be valid numbers: Latitude between -90 and 90, Longitude between -180 and 180.")
                                .font(.system(size: 10))
                                .foregroundStyle(.red)
                        }

                        VStack(alignment: .leading, spacing: 4) {
                            Text("Tactical Sector / Location Label")
                                .font(.system(size: 11, weight: .medium))
                            TextField("e.g. Sector Charlie — Outer Perimeter", text: $labelText)
                                .textFieldStyle(.roundedBorder)
                        }
                    }
                }
                .padding(16)
            }

            // Modal Footer Actions
            HStack {
                Button("Cancel") {
                    isPresented = false
                }
                .buttonStyle(.bordered)
                .controlSize(.regular)

                Spacer()

                Button {
                    Task {
                        await saveCamera()
                    }
                } label: {
                    if isSaving {
                        ProgressView().controlSize(.small)
                    } else {
                        Text("Register Camera")
                    }
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.regular)
                .disabled(!isFormValid || isSaving)
            }
            .padding(16)
            .background(Color(NSColor.windowBackgroundColor))
            .overlay(Divider(), alignment: .top)
        }
        .frame(width: 480, height: 460)
    }

    private func saveCamera() async {
        guard isFormValid else { return }
        isSaving = true
        errorMessage = nil

        do {
            try await state.registerCameraSource(
                id: cameraId.trimmingCharacters(in: .whitespacesAndNewlines),
                name: cameraName.isEmpty ? nil : cameraName,
                type: streamType,
                uri: streamUri.isEmpty ? nil : streamUri,
                latitude: parsedLat,
                longitude: parsedLng,
                label: labelText.isEmpty ? nil : labelText,
                status: streamType == "demo" ? "demo" : "idle"
            )
            isSaving = false
            isPresented = false
        } catch {
            isSaving = false
            errorMessage = error.localizedDescription
        }
    }
}

// MARK: - Source Launch Card

struct SourceLaunchCard: View {
    let title: String
    let subtitle: String
    let icon: String
    let color: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: icon)
                        .font(.system(size: 20))
                        .foregroundStyle(color)
                    Spacer()
                    Image(systemName: "play.circle.fill")
                        .font(.system(size: 16))
                        .foregroundStyle(Color.accentColor)
                }
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.system(size: 13, weight: .bold))
                    Text(subtitle)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(NSColor.controlBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(Color.secondary.opacity(0.15), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}
