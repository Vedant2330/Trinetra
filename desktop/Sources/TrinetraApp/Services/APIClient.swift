import Foundation
import AppKit

public final class APIClient: Sendable {
    public let baseURL: URL
    private let session: URLSession

    public init(baseURL: URL = URL(string: "http://127.0.0.1:8000")!) {
        self.baseURL = baseURL
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 90.0
        config.timeoutIntervalForResource = 120.0
        self.session = URLSession(configuration: config)
    }

    private func parseErrorMessage(data: Data, fallback: String) -> String {
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let detail = json["detail"] as? String {
                return detail
            } else if let detailList = json["detail"] as? [[String: Any]] {
                let messages = detailList.compactMap { d -> String? in
                    let msg = d["msg"] as? String ?? ""
                    let loc = (d["loc"] as? [Any])?.map { "\($0)" }.joined(separator: ".") ?? ""
                    return loc.isEmpty ? msg : "\(loc): \(msg)"
                }
                if !messages.isEmpty {
                    return messages.joined(separator: ", ")
                }
            } else if let error = json["error"] as? String {
                return error
            }
        }
        return String(data: data, encoding: .utf8) ?? fallback
    }

    // MARK: - Health & Diagnostics

    public func fetchHealth() async throws -> HealthResponse {
        let url = baseURL.appendingPathComponent("api/health")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(HealthResponse.self, from: data)
    }

    // MARK: - Session Management

    public func fetchSessionStatus() async throws -> SessionStatusResponse {
        let url = baseURL.appendingPathComponent("api/session/status")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(SessionStatusResponse.self, from: data)
    }

    public func startSession(request: StartSessionRequest) async throws -> SessionPayload {
        let url = baseURL.appendingPathComponent("api/session/start")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(request)

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        if !(200...299).contains(http.statusCode) {
            let errorMsg = parseErrorMessage(data: data, fallback: "Session start failed with HTTP \(http.statusCode)")
            throw NSError(domain: "TrinetraAPI", code: http.statusCode, userInfo: [NSLocalizedDescriptionKey: errorMsg])
        }

        struct StartResp: Codable {
            let status: String
            let session: SessionPayload
        }
        let resp = try JSONDecoder().decode(StartResp.self, from: data)
        return resp.session
    }

    public func stopSession() async throws {
        let url = baseURL.appendingPathComponent("api/session/stop")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        _ = try await session.data(for: req)
    }

    public func pauseSession() async throws {
        let url = baseURL.appendingPathComponent("api/session/pause")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        _ = try await session.data(for: req)
    }

    public func resumeSession() async throws {
        let url = baseURL.appendingPathComponent("api/session/resume")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        _ = try await session.data(for: req)
    }

    public func setSpeed(speed: Double) async throws {
        let url = baseURL.appendingPathComponent("api/session/speed")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = ["speed": speed]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        _ = try await session.data(for: req)
    }

    public func stepFrame() async throws {
        let url = baseURL.appendingPathComponent("api/session/step")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        _ = try await session.data(for: req)
    }

    public func seekSession(timestamp: Double) async throws {
        let url = baseURL.appendingPathComponent("api/session/seek")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = ["timestamp": timestamp, "video_ts": timestamp]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        _ = try await session.data(for: req)
    }

    // MARK: - Layer Toggles

    public func fetchLayers() async throws -> LayerState {
        let url = baseURL.appendingPathComponent("api/session/layers")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        let resp = try JSONDecoder().decode(LayersResponse.self, from: data)
        return resp.layers
    }

    public func updateLayers(_ layers: LayerState) async throws -> LayerState {
        let url = baseURL.appendingPathComponent("api/session/layers")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(layers)

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        let resp = try JSONDecoder().decode(LayersResponse.self, from: data)
        return resp.layers
    }

    // MARK: - Events & Alerts (Keyset Cursor)

    public func fetchEvents(
        sessionId: String? = nil,
        type: String? = nil,
        severity: String? = nil,
        limit: Int = 100,
        before: String? = nil,
        beforeId: String? = nil
    ) async throws -> EventsListResponse {
        var components = URLComponents(url: baseURL.appendingPathComponent("api/events"), resolvingAgainstBaseURL: true)!
        var queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]
        if let sid = sessionId, !sid.isEmpty { queryItems.append(URLQueryItem(name: "session_id", value: sid)) }
        if let type = type, !type.isEmpty { queryItems.append(URLQueryItem(name: "type", value: type)) }
        if let sev = severity, !sev.isEmpty { queryItems.append(URLQueryItem(name: "severity", value: sev)) }
        if let before = before, !before.isEmpty, let beforeId = beforeId, !beforeId.isEmpty {
            queryItems.append(URLQueryItem(name: "before", value: before))
            queryItems.append(URLQueryItem(name: "before_id", value: beforeId))
        }
        components.queryItems = queryItems

        guard let requestURL = components.url else { throw URLError(.badURL) }
        let (data, response) = try await session.data(from: requestURL)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(EventsListResponse.self, from: data)
    }

    public func ackEvent(eventId: String) async throws {
        let url = baseURL.appendingPathComponent("api/events/\(eventId)/ack")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        _ = try await session.data(for: req)
    }

    public func fetchEventSummary(eventId: String) async throws -> EventSummaryResponse {
        let url = baseURL.appendingPathComponent("api/events/\(eventId)/summary")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(EventSummaryResponse.self, from: data)
    }

    public func fetchEventSnapshot(eventId: String) async throws -> Data {
        let url = baseURL.appendingPathComponent("api/events/\(eventId)/snapshot")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return data
    }

    // MARK: - Session History & Investigation

    public func fetchSessions(limit: Int = 20) async throws -> [SessionHistoryItem] {
        var components = URLComponents(url: baseURL.appendingPathComponent("api/sessions"), resolvingAgainstBaseURL: true)!
        components.queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]
        guard let requestURL = components.url else { throw URLError(.badURL) }
        let (data, response) = try await session.data(from: requestURL)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            return []
        }
        let resp = try JSONDecoder().decode(SessionsListResponse.self, from: data)
        return resp.sessions
    }

    public func fetchSessionSummary(sessionId: String) async throws -> SessionSummaryResponse {
        let url = baseURL.appendingPathComponent("api/sessions/\(sessionId)/summary")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(SessionSummaryResponse.self, from: data)
    }

    public func fetchSessionTracks(sessionId: String) async throws -> SessionTracksResponse {
        let url = baseURL.appendingPathComponent("api/sessions/\(sessionId)/tracks")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(SessionTracksResponse.self, from: data)
    }

    // MARK: - Virtual Zones

    public func fetchZones() async throws -> [ZoneModel] {
        let url = baseURL.appendingPathComponent("api/zones")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        let resp = try JSONDecoder().decode(ZonesListResponse.self, from: data)
        return resp.zones
    }

    // MARK: - Sources & File Upload

    public func fetchSources() async throws -> [SourceItem] {
        let url = baseURL.appendingPathComponent("api/sources")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        let resp = try JSONDecoder().decode(SourcesListResponse.self, from: data)
        return resp.sources
    }

    public func registerSource(request: SourceCreateRequest) async throws {
        let url = baseURL.appendingPathComponent("api/sources")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(request)
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let msg = String(data: data, encoding: .utf8) ?? "Failed to register camera source"
            throw NSError(domain: "TrinetraAPI", code: (response as? HTTPURLResponse)?.statusCode ?? 400, userInfo: [NSLocalizedDescriptionKey: msg])
        }
    }

    public func seedDemoSources() async throws -> SeedDemoResponse {
        let url = baseURL.appendingPathComponent("api/sources/seed-demo")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let msg = String(data: data, encoding: .utf8) ?? "Failed to seed demo sources"
            throw NSError(domain: "TrinetraAPI", code: (response as? HTTPURLResponse)?.statusCode ?? 500, userInfo: [NSLocalizedDescriptionKey: msg])
        }
        return try JSONDecoder().decode(SeedDemoResponse.self, from: data)
    }

    public func uploadVideoFile(fileURL: URL) async throws -> UploadResponse {
        let url = baseURL.appendingPathComponent("api/sources/upload")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        let boundary = "Boundary-\(UUID().uuidString)"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let fileData = try Data(contentsOf: fileURL)
        let filename = fileURL.lastPathComponent

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: video/mp4\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        let (data, response) = try await session.upload(for: req, from: body)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let errorMsg = String(data: data, encoding: .utf8) ?? "Upload failed"
            throw NSError(domain: "TrinetraAPI", code: 400, userInfo: [NSLocalizedDescriptionKey: errorMsg])
        }
        return try JSONDecoder().decode(UploadResponse.self, from: data)
    }

    // MARK: - Re-ID Gallery

    public func fetchReIDPersons() async throws -> [ReIDPersonSummary] {
        let url = baseURL.appendingPathComponent("api/reid/persons")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            return []
        }
        let resp = try JSONDecoder().decode(ReIDPersonsResponse.self, from: data)
        return resp.persons
    }

    // MARK: - Hermes AI Copilot

    public func askHermes(query: String, eventId: String? = nil, sessionId: String? = nil, model: String? = nil) async throws -> HermesAskResponse {
        let url = baseURL.appendingPathComponent("api/hermes/ask")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.timeoutInterval = 90.0
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let payload = HermesAskRequest(question: query, event_id: eventId, session_id: sessionId, model: model)
        req.httpBody = try JSONEncoder().encode(payload)

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        if http.statusCode == 503 {
            let errorMsg = parseErrorMessage(data: data, fallback: "Hermes LLM model unavailable or offline (honest 503 status)")
            throw NSError(
                domain: "HermesAI",
                code: 503,
                userInfo: [NSLocalizedDescriptionKey: errorMsg]
            )
        }
        if !(200...299).contains(http.statusCode) {
            let msg = parseErrorMessage(data: data, fallback: "HTTP \(http.statusCode)")
            throw NSError(domain: "HermesAI", code: http.statusCode, userInfo: [NSLocalizedDescriptionKey: msg])
        }
        return try JSONDecoder().decode(HermesAskResponse.self, from: data)
    }

    public func fetchHermesStatus() async throws -> HermesStatusResponse {
        let url = baseURL.appendingPathComponent("api/hermes/status")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            return HermesStatusResponse(connected: false, enabled: false, model: "Hermes-3-Llama-3.1-8B", gateway: "", checked_at: nil, error: "Service unreachable")
        }
        return try JSONDecoder().decode(HermesStatusResponse.self, from: data)
    }

    // MARK: - Map & GIS

    public func fetchMapConfig() async throws -> MapConfigResponse {
        let url = baseURL.appendingPathComponent("api/map/config")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(MapConfigResponse.self, from: data)
    }

    public func fetchMapSectors() async throws -> [GeoSector] {
        let url = baseURL.appendingPathComponent("api/map/sectors")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            return []
        }
        let resp = try JSONDecoder().decode(MapSectorsResponse.self, from: data)
        return resp.sectors
    }

    public func fetchMapCameras() async throws -> [MapCameraItem] {
        let url = baseURL.appendingPathComponent("api/map/cameras")
        let (data, response) = try await session.data(from: url)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            return []
        }
        let resp = try JSONDecoder().decode(MapCamerasResponse.self, from: data)
        return resp.cameras
    }

    public func updateCameraGeo(sourceId: String, latitude: Double, longitude: Double, label: String = "") async throws {
        let url = baseURL.appendingPathComponent("api/map/cameras/\(sourceId)/geo")
        var req = URLRequest(url: url)
        req.httpMethod = "PUT"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = [
            "latitude": latitude,
            "longitude": longitude,
            "label": label
        ]
        req.httpBody = try JSONSerialization.data(withJSONObject: body)
        let (_, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
    }
}
