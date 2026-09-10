import SwiftUI
import AppKit
import WebKit

public struct GeographyView: View {
    @Environment(AppState.self) private var state

    @State private var selectedSector: GeoSector? = nil
    @State private var selectedCamera: MapCameraItem? = nil
    @State private var viewMode: MapViewMode = .satellite
    @State private var editingCameraId: String? = nil
    @State private var editLat: String = "28.6139"
    @State private var editLng: String = "77.2090"
    @State private var editLabel: String = ""

    public enum MapViewMode: String, CaseIterable, Identifiable {
        case satellite = "Satellite (Google)"
        case roadmap = "Roadmap (Google)"
        case localSiteMap = "Local Site Map (Demo)"
        case radar = "Tactical Radar (Offline)"

        public var id: String { rawValue }
    }

    public init() {}

    public var body: some View {
        HSplitView {
            // Main Map / Radar Viewport
            VStack(spacing: 0) {
                // Header Bar with Mode Selector & Indicators
                HStack(spacing: 12) {
                    HStack(spacing: 6) {
                        Image(systemName: "globe.asia.australia.fill")
                            .foregroundStyle(Color.accentColor)
                        Text("Geographic Information System (GIS)")
                            .font(.system(size: 13, weight: .bold))
                    }

                    Spacer()

                    Picker("Mode", selection: $viewMode) {
                        ForEach(MapViewMode.allCases) { mode in
                            Text(mode.rawValue).tag(mode)
                        }
                    }
                    .pickerStyle(.segmented)
                    .frame(width: 440)

                    // Engine Badge
                    HStack(spacing: 4) {
                        Circle()
                            .fill(viewMode == .localSiteMap ? Color.purple : ((state.mapConfig?.has_key == true || viewMode == .radar) ? Color.green : Color.orange))
                            .frame(width: 6, height: 6)
                        Text(viewMode == .radar ? "RADAR SCHEMATIC" : (viewMode == .localSiteMap ? "LOCAL SITE MAP (DEMO)" : "GOOGLE SATELLITE ENGINE"))
                            .font(.system(size: 9, weight: .bold, design: .monospaced))
                            .foregroundStyle(.secondary)
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color(NSColor.controlBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 4))

                    Button {
                        Task {
                            await state.refreshMapData()
                        }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.secondary)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(Color(NSColor.windowBackgroundColor))
                .overlay(Divider(), alignment: .bottom)

                // Map Content Canvas
                ZStack {
                    switch viewMode {
                    case .localSiteMap:
                        let allCams: [MapCameraItem] = state.mapCameras.isEmpty ? state.sources.map { s in
                            MapCameraItem(source_id: s.id, label: s.label ?? s.name ?? s.id, latitude: s.effectiveLat, longitude: s.effectiveLng, status: s.isLiveActive ? "live" : (s.isDemo ? "demo" : "idle"), type: s.type)
                        } : state.mapCameras

                        // Filter to stable demo cameras (CAM-01..CAM-08) without overlapping transient session records
                        let stableCams: [MapCameraItem] = {
                            var seen = Set<String>()
                            var result: [MapCameraItem] = []
                            // Priority 1: Standard demo cameras CAM-01..CAM-08
                            for cam in allCams {
                                let key = cam.source_id.uppercased()
                                if (key.hasPrefix("CAM-0") || key == "CAM-1" || key == "CAM-2" || key == "CAM-3" || key == "CAM-4" || key == "CAM-5" || key == "CAM-6" || key == "CAM-7" || key == "CAM-8") && !seen.contains(key) {
                                    seen.insert(key)
                                    result.append(cam)
                                }
                            }
                            // Priority 2: Active live sources
                            for cam in allCams where cam.status == "live" && !seen.contains(cam.source_id.uppercased()) {
                                seen.insert(cam.source_id.uppercased())
                                result.append(cam)
                            }
                            // Fallback if none matched: up to 8 unique cameras
                            if result.isEmpty {
                                for cam in allCams where !seen.contains(cam.source_id.uppercased()) {
                                    seen.insert(cam.source_id.uppercased())
                                    result.append(cam)
                                    if result.count >= 8 { break }
                                }
                            }
                            return result.sorted { $0.id < $1.id }
                        }()

                        LocalSiteMapCanvasView(
                            cameras: stableCams,
                            selectedCamera: selectedCamera,
                            onSelectCamera: { c in selectedCamera = c }
                        )
                    case .radar:
                        TacticalRadarSchematicView(
                            sectors: state.mapSectors,
                            cameras: state.mapCameras,
                            selectedSector: selectedSector,
                            selectedCamera: selectedCamera,
                            onSelectSector: { s in selectedSector = s },
                            onSelectCamera: { c in selectedCamera = c }
                        )
                    case .satellite, .roadmap:
                        if (state.mapConfig?.google_maps_key ?? "").isEmpty {
                            TacticalRadarSchematicView(
                                sectors: state.mapSectors,
                                cameras: state.mapCameras,
                                selectedSector: selectedSector,
                                selectedCamera: selectedCamera,
                                onSelectSector: { s in selectedSector = s },
                                onSelectCamera: { c in selectedCamera = c }
                            )
                        } else {
                            GoogleMapsWebView(
                                apiKey: state.mapConfig?.google_maps_key ?? "",
                                sectors: state.mapSectors,
                                cameras: state.mapCameras,
                                mapType: viewMode == .roadmap ? "roadmap" : "satellite",
                                selectedCamera: $selectedCamera,
                                selectedSector: $selectedSector
                            )
                        }
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .frame(minWidth: 480, maxWidth: .infinity)

            // Right Panel: Geographic Registry & Telemetry Inspector
            VStack(spacing: 0) {
                HStack {
                    Image(systemName: "antenna.radiowaves.left.and.right")
                        .foregroundStyle(Color.accentColor)
                    Text("GIS Telemetry & Registry")
                        .font(.system(size: 12, weight: .bold))
                    Spacer()
                }
                .padding(12)
                .background(Color(NSColor.windowBackgroundColor))
                .overlay(Divider(), alignment: .bottom)

                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        // Operational Labeling
                        if let label = state.mapConfig?.label {
                            HStack(alignment: .top, spacing: 8) {
                                Image(systemName: "shield.lefthalf.filled")
                                    .foregroundStyle(Color.accentColor)
                                    .font(.system(size: 12))
                                Text(label)
                                    .font(.system(size: 11, weight: .semibold))
                                    .foregroundStyle(.primary)
                            }
                            .padding(10)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color(NSColor.controlBackgroundColor))
                            .clipShape(RoundedRectangle(cornerRadius: 6))
                        }

                        // Geographic Sectors Section
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text("OPERATIONAL SECTORS (\(state.mapSectors.count))")
                                    .font(.system(size: 10, weight: .heavy, design: .monospaced))
                                    .foregroundStyle(.secondary)
                                Spacer()
                            }

                            if state.mapSectors.isEmpty {
                                Text("No geographic sectors defined in database.")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .padding(.vertical, 8)
                            } else {
                                ForEach(state.mapSectors) { sector in
                                    SectorItemCard(sector: sector, isSelected: selectedSector?.id == sector.id) {
                                        selectedSector = sector
                                    }
                                }
                            }
                        }

                        Divider()

                        // Surveillance Cameras Section
                        VStack(alignment: .leading, spacing: 8) {
                            HStack {
                                Text("SURVEILLANCE CAMERAS (\(state.mapCameras.count))")
                                    .font(.system(size: 10, weight: .heavy, design: .monospaced))
                                    .foregroundStyle(.secondary)
                                Spacer()
                            }

                            if state.mapCameras.isEmpty {
                                Text("No cameras connected or registered.")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                                    .padding(.vertical, 8)
                            } else {
                                ForEach(state.mapCameras) { cam in
                                    CameraGeoCard(
                                        camera: cam,
                                        isSelected: selectedCamera?.id == cam.id,
                                        isEditing: editingCameraId == cam.id,
                                        editLat: $editLat,
                                        editLng: $editLng,
                                        editLabel: $editLabel,
                                        onSelect: {
                                            selectedCamera = cam
                                        },
                                        onStartEdit: {
                                            editingCameraId = cam.id
                                            editLat = cam.latitude != nil ? "\(cam.latitude!)" : "28.6139"
                                            editLng = cam.longitude != nil ? "\(cam.longitude!)" : "77.2090"
                                            editLabel = cam.label
                                        },
                                        onCancelEdit: {
                                            editingCameraId = nil
                                        },
                                        onSaveGeo: {
                                            guard let lat = Double(editLat), let lng = Double(editLng) else { return }
                                            Task {
                                                await state.updateCameraGeo(sourceId: cam.source_id, lat: lat, lng: lng, label: editLabel)
                                                editingCameraId = nil
                                            }
                                        }
                                    )
                                }
                            }
                        }
                    }
                    .padding(16)
                }
            }
            .frame(minWidth: 300, idealWidth: 340, maxWidth: 420)
            .background(Color(NSColor.windowBackgroundColor))
        }
        .onAppear {
            syncSelectedCameraFromState()
        }
        .onChange(of: state.selectedMapCameraId) { _, _ in
            syncSelectedCameraFromState()
        }
    }

    private func syncSelectedCameraFromState() {
        guard let targetId = state.selectedMapCameraId else { return }
        if let match = state.mapCameras.first(where: { $0.source_id == targetId || $0.id == targetId }) {
            selectedCamera = match
        } else if let src = state.sources.first(where: { $0.id == targetId }) {
            selectedCamera = MapCameraItem(
                source_id: src.id,
                label: src.label ?? src.name ?? src.id,
                latitude: src.effectiveLat,
                longitude: src.effectiveLng,
                status: src.isLiveActive ? "live" : (src.isDemo ? "demo" : "idle"),
                type: src.type
            )
        }
    }
}

// MARK: - Native WebKit Google Maps View

struct GoogleMapsWebView: NSViewRepresentable {
    let apiKey: String
    let sectors: [GeoSector]
    let cameras: [MapCameraItem]
    let mapType: String
    @Binding var selectedCamera: MapCameraItem?
    @Binding var selectedSector: GeoSector?

    func makeNSView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        let webView = WKWebView(frame: .zero, configuration: config)
        webView.setValue(false, forKey: "drawsBackground") // Transparent background
        loadMapHTML(in: webView)
        return webView
    }

    func updateNSView(_ nsView: WKWebView, context: Context) {
        // Update map type or markers dynamically if needed
        let escapedMapType = mapType
        let js = "if (window.setMapType) { window.setMapType('\(escapedMapType)'); }"
        nsView.evaluateJavaScript(js, completionHandler: nil)
    }

    private func loadMapHTML(in webView: WKWebView) {
        // Encode sectors and cameras into JSON for Google Maps JavaScript
        let sectorsJSON: String = {
            let list = sectors.map { s in
                [
                    "id": s.id,
                    "name": s.name,
                    "color": s.colorHex,
                    "coords": s.polygon.map { ["lat": $0[0], "lng": $0[1]] }
                ] as [String : Any]
            }
            if let data = try? JSONSerialization.data(withJSONObject: list),
               let str = String(data: data, encoding: .utf8) {
                return str
            }
            return "[]"
        }()

        let camerasJSON: String = {
            let list = cameras.compactMap { c -> [String: Any]? in
                guard let lat = c.latitude, let lng = c.longitude else { return nil }
                return [
                    "id": c.id,
                    "label": c.label,
                    "lat": lat,
                    "lng": lng,
                    "status": c.status,
                    "type": c.type
                ]
            }
            if let data = try? JSONSerialization.data(withJSONObject: list),
               let str = String(data: data, encoding: .utf8) {
                return str
            }
            return "[]"
        }()

        let html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta name="viewport" content="initial-scale=1.0, user-scalable=no" />
            <style>
                html, body, #map { height: 100%; margin: 0; padding: 0; background: #111827; }
                .hud-badge {
                    position: absolute; top: 12px; left: 12px; z-index: 10;
                    background: rgba(17, 24, 39, 0.85); backdrop-filter: blur(8px);
                    color: #10B981; font-family: monospace; font-size: 11px;
                    padding: 6px 10px; border-radius: 6px; border: 1px solid rgba(16, 185, 129, 0.3);
                }
            </style>
            <script src="https://maps.googleapis.com/maps/api/js?key=\(apiKey)&callback=initMap" async defer></script>
        </head>
        <body>
            <div class="hud-badge">● SATELLITE TELEMETRY LIVE | WGS-84 ACTIVE</div>
            <div id="map"></div>
            <script>
                var map;
                var sectors = \(sectorsJSON);
                var cameras = \(camerasJSON);

                function initMap() {
                    var defaultCenter = { lat: 28.6139, lng: 77.2090 };
                    if (cameras.length > 0) {
                        defaultCenter = { lat: cameras[0].lat, lng: cameras[0].lng };
                    } else if (sectors.length > 0 && sectors[0].coords.length > 0) {
                        defaultCenter = sectors[0].coords[0];
                    }

                    map = new google.maps.Map(document.getElementById('map'), {
                        center: defaultCenter,
                        zoom: 14,
                        mapTypeId: '\(mapType)',
                        disableDefaultUI: false,
                        zoomControl: true,
                        mapTypeControl: false,
                        scaleControl: true,
                        streetViewControl: false,
                        rotateControl: true,
                        fullscreenControl: false
                    });

                    // Draw Sectors
                    sectors.forEach(function(sec) {
                        var poly = new google.maps.Polygon({
                            paths: sec.coords,
                            strokeColor: sec.color,
                            strokeOpacity: 0.8,
                            strokeWeight: 2,
                            fillColor: sec.color,
                            fillOpacity: 0.25
                        });
                        poly.setMap(map);
                    });

                    // Draw Cameras
                    cameras.forEach(function(cam) {
                        var markerColor = cam.status === 'live' ? '#10B981' : (cam.status === 'error' ? '#EF4444' : '#F59E0B');
                        var marker = new google.maps.Marker({
                            position: { lat: cam.lat, lng: cam.lng },
                            map: map,
                            title: cam.label + " (" + cam.status.toUpperCase() + ")",
                            icon: {
                                path: google.maps.SymbolPath.CIRCLE,
                                scale: 8,
                                fillColor: markerColor,
                                fillOpacity: 1,
                                strokeColor: '#ffffff',
                                strokeWeight: 2
                            }
                        });

                        var infoWindow = new google.maps.InfoWindow({
                            content: '<div style="color:#000;padding:4px;"><b>' + cam.label + '</b><br>Status: ' + cam.status.toUpperCase() + '<br>Lat: ' + cam.lat + '<br>Lng: ' + cam.lng + '</div>'
                        });

                        marker.addListener('click', function() {
                            infoWindow.open(map, marker);
                        });
                    });
                }

                window.setMapType = function(type) {
                    if (map) {
                        map.setMapTypeId(type);
                    }
                };
            </script>
        </body>
        </html>
        """

        webView.loadHTMLString(html, baseURL: URL(string: "https://maps.googleapis.com"))
    }
}

// MARK: - Tactical Radar Schematic View (Offline Fallback)

struct TacticalRadarSchematicView: View {
    let sectors: [GeoSector]
    let cameras: [MapCameraItem]
    let selectedSector: GeoSector?
    let selectedCamera: MapCameraItem?
    let onSelectSector: (GeoSector) -> Void
    let onSelectCamera: (MapCameraItem) -> Void

    var body: some View {
        ZStack {
            Color(hex: "#0B0F17")

            // Radar concentric rings
            GeometryReader { geo in
                let center = CGPoint(x: geo.size.width / 2, y: geo.size.height / 2)
                let maxRadius = min(geo.size.width, geo.size.height) * 0.45

                Path { path in
                    // Grid Lines
                    path.move(to: CGPoint(x: 0, y: center.y))
                    path.addLine(to: CGPoint(x: geo.size.width, y: center.y))
                    path.move(to: CGPoint(x: center.x, y: 0))
                    path.addLine(to: CGPoint(x: center.x, y: geo.size.height))

                    // Diagonal lines
                    path.move(to: CGPoint(x: center.x - maxRadius, y: center.y - maxRadius))
                    path.addLine(to: CGPoint(x: center.x + maxRadius, y: center.y + maxRadius))
                    path.move(to: CGPoint(x: center.x - maxRadius, y: center.y + maxRadius))
                    path.addLine(to: CGPoint(x: center.x + maxRadius, y: center.y - maxRadius))
                }
                .stroke(Color.green.opacity(0.15), lineWidth: 1)

                // Circles
                ForEach(1...4, id: \.self) { i in
                    Circle()
                        .stroke(Color.green.opacity(0.2), lineWidth: 1)
                        .frame(width: maxRadius * 2 * CGFloat(i) / 4, height: maxRadius * 2 * CGFloat(i) / 4)
                        .position(center)
                }

                // Sectors plotted schematically
                ForEach(sectors) { sector in
                    let offset = CGFloat(abs(sector.id.hashValue) % 180) - 90
                    let secCenter = CGPoint(x: center.x + offset, y: center.y - offset * 0.8)

                    Button {
                        onSelectSector(sector)
                    } label: {
                        VStack(spacing: 4) {
                            ZStack {
                                Circle()
                                    .fill(Color(hex: sector.colorHex).opacity(selectedSector?.id == sector.id ? 0.4 : 0.15))
                                    .frame(width: 60, height: 60)
                                Circle()
                                    .stroke(Color(hex: sector.colorHex), lineWidth: selectedSector?.id == sector.id ? 2 : 1)
                                    .frame(width: 60, height: 60)
                                Image(systemName: "shield.lefthalf.filled")
                                    .foregroundStyle(Color(hex: sector.colorHex))
                            }
                            Text(sector.name)
                                .font(.system(size: 9, weight: .bold, design: .monospaced))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 4)
                                .padding(.vertical, 2)
                                .background(Color.black.opacity(0.8))
                                .clipShape(RoundedRectangle(cornerRadius: 3))
                        }
                    }
                    .buttonStyle(.plain)
                    .position(secCenter)
                }

                // Cameras plotted schematically
                ForEach(cameras) { cam in
                    let offset = CGFloat(abs(cam.id.hashValue) % 160) - 80
                    let camPos = CGPoint(x: center.x + offset * 1.5, y: center.y + offset)

                    Button {
                        onSelectCamera(cam)
                    } label: {
                        VStack(spacing: 2) {
                            ZStack {
                                Circle()
                                    .fill(cam.status == "live" ? Color.green : Color.orange)
                                    .frame(width: 14, height: 14)
                                Circle()
                                    .stroke(Color.white, lineWidth: 1.5)
                                    .frame(width: 14, height: 14)
                            }
                            Text(cam.label)
                                .font(.system(size: 8, weight: .semibold, design: .monospaced))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 4)
                                .background(Color.black.opacity(0.8))
                                .clipShape(RoundedRectangle(cornerRadius: 3))
                        }
                    }
                    .buttonStyle(.plain)
                    .position(camPos)
                }
            }

            // HUD Badges
            VStack {
                HStack {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("RADAR SCHEMATIC OPERATIONAL")
                            .font(.system(size: 10, weight: .bold, design: .monospaced))
                            .foregroundStyle(.green)
                        Text("LAT: 28.6139° N • LNG: 77.2090° E")
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundStyle(.green.opacity(0.7))
                    }
                    .padding(8)
                    .background(Color.black.opacity(0.75))
                    .clipShape(RoundedRectangle(cornerRadius: 4))
                    .overlay(RoundedRectangle(cornerRadius: 4).stroke(Color.green.opacity(0.3), lineWidth: 1))

                    Spacer()
                }
                Spacer()
            }
            .padding(16)
        }
    }
}

// MARK: - Sector & Camera Cards

struct SectorItemCard: View {
    let sector: GeoSector
    let isSelected: Bool
    let onSelect: () -> Void

    var body: some View {
        Button(action: onSelect) {
            VStack(alignment: .leading, spacing: 6) {
                HStack {
                    Circle()
                        .fill(Color(hex: sector.colorHex))
                        .frame(width: 8, height: 8)
                    Text(sector.name)
                        .font(.system(size: 12, weight: .bold))
                    Spacer()
                    Text(sector.threat_level ?? "NORMAL")
                        .font(.system(size: 9, weight: .bold, design: .monospaced))
                        .foregroundStyle(Color(hex: sector.colorHex))
                }
                Text("Polygon: \(sector.polygon.count) geo-points configured")
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(isSelected ? Color.accentColor.opacity(0.15) : Color(NSColor.controlBackgroundColor))
            .clipShape(RoundedRectangle(cornerRadius: 6))
            .overlay(
                RoundedRectangle(cornerRadius: 6)
                    .stroke(isSelected ? Color.accentColor : Color.secondary.opacity(0.15), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }
}

struct CameraGeoCard: View {
    let camera: MapCameraItem
    let isSelected: Bool
    let isEditing: Bool
    @Binding var editLat: String
    @Binding var editLng: String
    @Binding var editLabel: String
    let onSelect: () -> Void
    let onStartEdit: () -> Void
    let onCancelEdit: () -> Void
    let onSaveGeo: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Circle()
                    .fill(camera.status == "live" ? Color.green : (camera.status == "error" ? Color.red : Color.orange))
                    .frame(width: 7, height: 7)
                Text(camera.label)
                    .font(.system(size: 11, weight: .bold))
                Spacer()
                Text(camera.status.uppercased())
                    .font(.system(size: 9, weight: .bold, design: .monospaced))
                    .foregroundStyle(camera.status == "live" ? .green : .secondary)
            }

            if isEditing {
                VStack(spacing: 6) {
                    TextField("Label", text: $editLabel)
                        .textFieldStyle(.roundedBorder)
                        .controlSize(.small)
                    HStack(spacing: 6) {
                        TextField("Latitude", text: $editLat)
                            .textFieldStyle(.roundedBorder)
                            .controlSize(.small)
                        TextField("Longitude", text: $editLng)
                            .textFieldStyle(.roundedBorder)
                            .controlSize(.small)
                    }
                    HStack {
                        Button("Cancel", action: onCancelEdit)
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                        Spacer()
                        Button("Save Coordinates", action: onSaveGeo)
                            .buttonStyle(.borderedProminent)
                            .controlSize(.small)
                    }
                }
                .padding(.top, 4)
            } else {
                HStack {
                    if let lat = camera.latitude, let lng = camera.longitude {
                        Text(String(format: "%.4f° N, %.4f° E", lat, lng))
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(.secondary)
                    } else {
                        Text("No GPS coordinates attached")
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    Button("Edit Geo", action: onStartEdit)
                        .buttonStyle(.bordered)
                        .controlSize(.mini)
                }
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(isSelected ? Color.accentColor.opacity(0.15) : Color(NSColor.controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 6))
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .stroke(isSelected ? Color.accentColor : Color.secondary.opacity(0.15), lineWidth: 1)
        )
        .onTapGesture(perform: onSelect)
    }
}

// MARK: - Local Site Map Canvas View (Demo Fallback)

struct LocalSiteMapCanvasView: View {
    let cameras: [MapCameraItem]
    let selectedCamera: MapCameraItem?
    let onSelectCamera: (MapCameraItem) -> Void

    @State private var scale: CGFloat = 1.0
    @State private var lastScale: CGFloat = 1.0
    @State private var offset: CGSize = .zero
    @State private var lastOffset: CGSize = .zero
    @State private var mapImage: NSImage? = nil

    // Preset normalized coordinates (0.0 ... 1.0) on the 3420x1472 facility visual layout
    private let defaultPositions: [String: CGPoint] = [
        "CAM-01": CGPoint(x: 0.22, y: 0.68),
        "CAM-02": CGPoint(x: 0.35, y: 0.28),
        "CAM-03": CGPoint(x: 0.50, y: 0.45),
        "CAM-04": CGPoint(x: 0.68, y: 0.32),
        "CAM-05": CGPoint(x: 0.82, y: 0.58),
        "CAM-06": CGPoint(x: 0.48, y: 0.85),
        "CAM-07": CGPoint(x: 0.76, y: 0.22),
        "CAM-08": CGPoint(x: 0.18, y: 0.38)
    ]

    private func positionFor(camera: MapCameraItem, index: Int, total: Int) -> CGPoint {
        if let pos = defaultPositions[camera.id] ?? defaultPositions[camera.source_id] {
            return pos
        }
        let angle = Double(index) / Double(max(1, total)) * 2.0 * .pi
        let u = 0.5 + 0.3 * cos(angle)
        let v = 0.5 + 0.3 * sin(angle)
        return CGPoint(x: u, y: v)
    }

    var body: some View {
        GeometryReader { outerGeo in
            ZStack {
                Color(hex: "#0B0F17") // Tactical dark canvas background

                if let img = mapImage {
                    let imgRatio = img.size.width / max(1, img.size.height)
                    let viewRatio = outerGeo.size.width / max(1, outerGeo.size.height)
                    let baseSize: CGSize = {
                        if viewRatio > imgRatio {
                            let h = outerGeo.size.height
                            let w = h * imgRatio
                            return CGSize(width: w, height: h)
                        } else {
                            let w = outerGeo.size.width
                            let h = w / imgRatio
                            return CGSize(width: w, height: h)
                        }
                    }()

                    ZStack {
                        // Map Image
                        Image(nsImage: img)
                            .resizable()
                            .interpolation(.high)
                            .aspectRatio(contentMode: .fit)
                            .frame(width: baseSize.width, height: baseSize.height)

                        // Camera Markers Layer
                        ForEach(Array(cameras.enumerated()), id: \.element.id) { index, cam in
                            let normPos = positionFor(camera: cam, index: index, total: cameras.count)
                            let xPos = normPos.x * baseSize.width
                            let yPos = normPos.y * baseSize.height
                            let isSelected = selectedCamera?.id == cam.id || selectedCamera?.source_id == cam.source_id

                            SiteMapCameraMarker(
                                camera: cam,
                                isSelected: isSelected,
                                onTap: { onSelectCamera(cam) }
                            )
                            .position(x: xPos, y: yPos)
                        }
                    }
                    .frame(width: baseSize.width, height: baseSize.height)
                    .scaleEffect(scale)
                    .offset(offset)
                    .gesture(
                        DragGesture()
                            .onChanged { val in
                                offset = CGSize(
                                    width: lastOffset.width + val.translation.width,
                                    height: lastOffset.height + val.translation.height
                                )
                            }
                            .onEnded { _ in
                                lastOffset = offset
                            }
                    )
                    .gesture(
                        MagnificationGesture()
                            .onChanged { val in
                                let newScale = lastScale * val
                                scale = min(max(newScale, 0.4), 8.0)
                            }
                            .onEnded { _ in
                                lastScale = scale
                            }
                    )
                } else {
                    VStack(spacing: 12) {
                        ProgressView()
                        Text("Loading Local Site Map...")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                // Top-Left HUD Badge
                VStack {
                    HStack {
                        HStack(spacing: 6) {
                            Circle()
                                .fill(Color.purple)
                                .frame(width: 8, height: 8)
                            Text("LOCAL SITE MAP")
                                .font(.system(size: 11, weight: .black, design: .monospaced))
                                .foregroundStyle(.white)
                            Text("DEMO")
                                .font(.system(size: 9, weight: .heavy, design: .monospaced))
                                .foregroundStyle(.black)
                                .padding(.horizontal, 4)
                                .padding(.vertical, 1)
                                .background(Color.purple)
                                .clipShape(RoundedRectangle(cornerRadius: 3))
                            Text("| HIGH-RES TACTICAL SCHEMATIC")
                                .font(.system(size: 10, design: .monospaced))
                                .foregroundStyle(.secondary)
                        }
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(Color(hex: "#111827").opacity(0.85))
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                        .overlay(
                            RoundedRectangle(cornerRadius: 6)
                                .stroke(Color.purple.opacity(0.4), lineWidth: 1)
                        )
                        Spacer()
                    }
                    Spacer()
                }
                .padding(12)

                // Bottom-Right Controls (Zoom In, Zoom Out, Reset Fit-To-Map)
                VStack {
                    Spacer()
                    HStack {
                        Spacer()
                        HStack(spacing: 6) {
                            Button {
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    let newScale = min(scale * 1.3, 8.0)
                                    scale = newScale
                                    lastScale = newScale
                                }
                            } label: {
                                Image(systemName: "plus.magnifyingglass")
                                    .font(.system(size: 13, weight: .bold))
                            }
                            .buttonStyle(.plain)
                            .frame(width: 28, height: 28)
                            .background(Color(hex: "#1F2937").opacity(0.9))
                            .clipShape(RoundedRectangle(cornerRadius: 6))

                            Button {
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    let newScale = max(scale / 1.3, 0.4)
                                    scale = newScale
                                    lastScale = newScale
                                }
                            } label: {
                                Image(systemName: "minus.magnifyingglass")
                                    .font(.system(size: 13, weight: .bold))
                            }
                            .buttonStyle(.plain)
                            .frame(width: 28, height: 28)
                            .background(Color(hex: "#1F2937").opacity(0.9))
                            .clipShape(RoundedRectangle(cornerRadius: 6))

                            Button {
                                withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                                    scale = 1.0
                                    lastScale = 1.0
                                    offset = .zero
                                    lastOffset = .zero
                                }
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: "arrow.counterclockwise")
                                    Text("Fit Map")
                                }
                                .font(.system(size: 11, weight: .bold))
                                .padding(.horizontal, 8)
                                .frame(height: 28)
                                .background(Color(hex: "#1F2937").opacity(0.9))
                                .clipShape(RoundedRectangle(cornerRadius: 6))
                            }
                            .buttonStyle(.plain)

                            Text("\(Int(scale * 100))%")
                                .font(.system(size: 10, weight: .bold, design: .monospaced))
                                .foregroundStyle(.secondary)
                                .frame(width: 44)
                        }
                        .padding(6)
                        .background(Color(hex: "#111827").opacity(0.85))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(Color.secondary.opacity(0.25), lineWidth: 1)
                        )
                    }
                }
                .padding(16)
            }
        }
        .onAppear {
            loadImage()
        }
    }

    private func loadImage() {
        #if SWIFT_PACKAGE
        if let imgPath = Bundle.module.path(forResource: "MapSample", ofType: "png"),
           let img = NSImage(contentsOfFile: imgPath) {
            self.mapImage = img
            return
        }
        #endif

        if let imgPath = Bundle.main.path(forResource: "MapSample", ofType: "png"),
           let img = NSImage(contentsOfFile: imgPath) {
            self.mapImage = img
            return
        }

        if let img = NSImage(named: "MapSample") {
            self.mapImage = img
            return
        }

        let fallbackPath = "/Volumes/Vedant/vedantsecondary/Projects/SIH26/Trinetra/desktop/Sources/TrinetraApp/Resources/MapSample.png"
        if let img = NSImage(contentsOfFile: fallbackPath) {
            self.mapImage = img
            return
        }

        let rootPath = "/Volumes/Vedant/vedantsecondary/Projects/SIH26/Trinetra/MapSample.png"
        if let img = NSImage(contentsOfFile: rootPath) {
            self.mapImage = img
            return
        }
    }
}

// MARK: - Site Map Camera Marker

struct SiteMapCameraMarker: View {
    let camera: MapCameraItem
    let isSelected: Bool
    let onTap: () -> Void

    private var statusColor: Color {
        switch camera.status.lowercased() {
        case "live": return .green
        case "demo": return .purple
        case "error": return .red
        default: return .orange
        }
    }

    var body: some View {
        Button(action: onTap) {
            VStack(spacing: 3) {
                ZStack {
                    if isSelected {
                        Circle()
                            .stroke(statusColor, lineWidth: 2)
                            .frame(width: 28, height: 28)
                            .scaleEffect(1.2)
                    }

                    Circle()
                        .fill(statusColor)
                        .frame(width: 16, height: 16)
                        .shadow(color: statusColor.opacity(0.6), radius: 5)

                    Image(systemName: "video.fill")
                        .font(.system(size: 8, weight: .bold))
                        .foregroundStyle(.white)
                }

                HStack(spacing: 2) {
                    Text(camera.id)
                        .font(.system(size: 9, weight: .heavy, design: .monospaced))
                        .foregroundStyle(.white)
                    if camera.status.lowercased() == "live" {
                        Text("●")
                            .font(.system(size: 6))
                            .foregroundStyle(.green)
                    }
                }
                .padding(.horizontal, 4)
                .padding(.vertical, 1)
                .background(Color.black.opacity(0.85))
                .clipShape(RoundedRectangle(cornerRadius: 3))
                .overlay(
                    RoundedRectangle(cornerRadius: 3)
                        .stroke(isSelected ? statusColor : Color.secondary.opacity(0.4), lineWidth: 1)
                )
            }
        }
        .buttonStyle(.plain)
    }
}

