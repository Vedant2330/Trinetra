import Foundation
import AppKit

// MARK: - Generic JSON Value Support

public enum JSONValue: Codable, Hashable, Sendable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case array([JSONValue])
    case object([String: JSONValue])
    case null

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let bool = try? container.decode(Bool.self) {
            self = .bool(bool)
        } else if let int = try? container.decode(Int.self) {
            self = .int(int)
        } else if let double = try? container.decode(Double.self) {
            self = .double(double)
        } else if let string = try? container.decode(String.self) {
            self = .string(string)
        } else if let array = try? container.decode([JSONValue].self) {
            self = .array(array)
        } else if let object = try? container.decode([String: JSONValue].self) {
            self = .object(object)
        } else {
            self = .null
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let str):
            try container.encode(str)
        case .int(let num):
            try container.encode(num)
        case .double(let num):
            try container.encode(num)
        case .bool(let b):
            try container.encode(b)
        case .array(let arr):
            try container.encode(arr)
        case .object(let obj):
            try container.encode(obj)
        case .null:
            try container.encodeNil()
        }
    }
}

// MARK: - Health & System Models

public struct ModelStatusInfo: Codable, Hashable, Sendable {
    public let file: String?
    public let present: Bool?
    public let size_mb: Double?
    public let mode: String?

    public init(file: String? = nil, present: Bool? = nil, size_mb: Double? = nil, mode: String? = nil) {
        self.file = file
        self.present = present
        self.size_mb = size_mb
        self.mode = mode
    }
}

public struct HealthModelsDict: Codable, Hashable, Sendable {
    public let detector: ModelStatusInfo?
    public let reid: ModelStatusInfo?
    public let face: ModelStatusInfo?
    public let pose: ModelStatusInfo?
    public let anpr: ModelStatusInfo?
}

public struct DBHealth: Codable, Hashable, Sendable {
    public let ok: Bool?
    public let wal_mode: Bool?
    public let size_bytes: Int64?
}

public struct WriterHealth: Codable, Hashable, Sendable {
    public let status: String?
    public let queue_size: Int?
    public let dropped_count: Int?
}

public struct DBInfo: Sendable {
    public let mode: String
    public let queue_depth: Int

    public init(mode: String = "wal", queue_depth: Int = 0) {
        self.mode = mode
        self.queue_depth = queue_depth
    }
}

public struct HealthResponse: Codable, Hashable, Sendable {
    public let ok: Bool
    public let app: String
    public let phase: String
    public let uptime_s: Double
    public let device_policy: String
    public let models: HealthModelsDict
    public let db: DBHealth?
    public let writer: WriterHealth?
    public let active_session: String?
    public let reid_enabled: Bool?
    public let face_enabled: Bool?
    public let pose_enabled: Bool?
    public let anpr_mode: String?

    public var device: String { device_policy }

    public var database: DBInfo {
        DBInfo(
            mode: (db?.wal_mode == true ? "wal" : "standard"),
            queue_depth: writer?.queue_size ?? 0
        )
    }
}

// MARK: - Session & Playback Models

public struct SessionPayload: Codable, Hashable, Sendable {
    public let source_id: String
    public let status: String
    public let error: String?
    public let frames_processed: Int
    public let pipeline_fps: Double
    public let source_fps: Double?
    public let playback_fps: Double?
    public let inference_fps: Double?
    public let latency_ms: Double?
    public let avg_latency_ms: Double?
    public let playback_speed: Double?
    public let is_paused: Bool?
    public let is_file: Bool?
    public let speed: Double?
    public let people_detected: Int?
    public let vehicles_detected: Int?
    public let active_people: Int?
    public let active_vehicles: Int?
    public let active_tracks: Int?
    public let total_tracks: Int?
    public let events_committed: Int?
    public let device: String?
    public let uptime_s: Double?

    public var session_id: String { source_id }

    public var effectiveSpeed: Double {
        playback_speed ?? speed ?? 1.0
    }

    public var effectiveLatencyMs: Double {
        latency_ms ?? avg_latency_ms ?? 0.0
    }

    public var effectiveSourceFps: Double {
        source_fps ?? 25.0
    }

    public var effectivePlaybackFps: Double {
        playback_fps ?? (is_file == true ? (source_fps ?? 30.0) : pipeline_fps)
    }

    public var effectiveInferenceFps: Double {
        inference_fps ?? pipeline_fps
    }

    public init(
        source_id: String,
        status: String,
        error: String? = nil,
        frames_processed: Int = 0,
        pipeline_fps: Double = 0.0,
        source_fps: Double? = 25.0,
        playback_fps: Double? = 25.0,
        inference_fps: Double? = 0.0,
        latency_ms: Double? = 0.0,
        avg_latency_ms: Double? = 0.0,
        playback_speed: Double? = 1.0,
        is_paused: Bool? = false,
        is_file: Bool? = false,
        speed: Double? = 1.0,
        people_detected: Int? = 0,
        vehicles_detected: Int? = 0,
        active_people: Int? = 0,
        active_vehicles: Int? = 0,
        active_tracks: Int? = 0,
        total_tracks: Int? = 0,
        events_committed: Int? = 0,
        device: String? = "CPU",
        uptime_s: Double? = 0.0
    ) {
        self.source_id = source_id
        self.status = status
        self.error = error
        self.frames_processed = frames_processed
        self.pipeline_fps = pipeline_fps
        self.source_fps = source_fps
        self.playback_fps = playback_fps
        self.inference_fps = inference_fps
        self.latency_ms = latency_ms
        self.avg_latency_ms = avg_latency_ms
        self.playback_speed = playback_speed
        self.is_paused = is_paused
        self.is_file = is_file
        self.speed = speed
        self.people_detected = people_detected
        self.vehicles_detected = vehicles_detected
        self.active_people = active_people
        self.active_vehicles = active_vehicles
        self.active_tracks = active_tracks
        self.total_tracks = total_tracks
        self.events_committed = events_committed
        self.device = device
        self.uptime_s = uptime_s
    }
}

public struct SessionStatusResponse: Codable, Hashable, Sendable {
    public let active: Bool
    public let session: SessionPayload?
}

public struct StartSessionRequest: Codable, Sendable {
    public let type: String
    public let path: String?
    public let index: Int?
    public let uri: String?

    public init(type: String, path: String? = nil, index: Int? = nil, uri: String? = nil) {
        self.type = type
        self.path = path
        self.index = index
        self.uri = uri
    }
}

// MARK: - Layer Toggles

public struct LayerState: Codable, Hashable, Sendable {
    public var boxes: Bool
    public var labels: Bool
    public var fps: Bool
    public var trajectories: Bool
    public var zones: Bool
    public var faces: Bool
    public var pose: Bool

    public init(
        boxes: Bool = true,
        labels: Bool = true,
        fps: Bool = true,
        trajectories: Bool = false,
        zones: Bool = true,
        faces: Bool = false,
        pose: Bool = false
    ) {
        self.boxes = boxes
        self.labels = labels
        self.fps = fps
        self.trajectories = trajectories
        self.zones = zones
        self.faces = faces
        self.pose = pose
    }
}

public struct LayersResponse: Codable, Hashable, Sendable {
    public let layers: LayerState
}

// MARK: - Event & Alert Models

public struct EventRow: Codable, Identifiable, Hashable, Sendable {
    public let id: String
    public let session_id: String?
    public let source_id: String?
    public let ts: String?
    public let video_ts: Double?
    public let type: String
    public let severity: String
    public let confidence: Double
    public let track_ids: [Int]?
    public let zone_id: String?
    public let direction: String?
    public let is_night: Bool?
    public let snapshot_path: String?
    public let metadata: [String: JSONValue]?
    public let status: String?
    public let global_person_id: String?

    public var track_id: Int? {
        track_ids?.first
    }

    public var summary: String? {
        if let meta = metadata, let s = meta["summary"] {
            if case .string(let str) = s { return str }
        }
        let dirStr = direction != nil && !direction!.isEmpty ? " traveling \(direction!)" : ""
        let zStr = zone_id != nil && !zone_id!.isEmpty ? " at zone \(zone_id!)" : ""
        let tStr = track_id != nil ? "Track #\(track_id!)" : "Subject"
        let readableType = type.replacingOccurrences(of: "_", with: " ")
        return "\(severity) alert: \(readableType) detected for \(tStr)\(zStr)\(dirStr) (confidence: \(Int(confidence * 100))%)."
    }

    public var formattedTime: String {
        if let vts = video_ts {
            let mins = Int(vts) / 60
            let secs = Int(vts) % 60
            let ms = Int((vts.truncatingRemainder(dividingBy: 1)) * 100)
            return String(format: "%02d:%02d.%02d", mins, secs, ms)
        }
        if let tStr = ts {
            return tStr.count > 19 ? String(tStr.prefix(19)).replacingOccurrences(of: "T", with: " ") : tStr
        }
        return "Live"
    }

    public var severityColorHex: String {
        switch severity.uppercased() {
        case "CRITICAL": return "#EF4444" // Red
        case "WARNING": return "#F59E0B"  // Amber
        case "INFO": return "#3B82F6"     // Blue
        default: return "#9CA3AF"
        }
    }

    enum CodingKeys: String, CodingKey {
        case id, session_id, source_id, ts, timestamp, video_ts, type, severity, confidence
        case track_ids, zone_id, direction, is_night, snapshot_path, metadata, status, global_person_id
    }

    public init(
        id: String,
        session_id: String? = nil,
        source_id: String? = nil,
        ts: String? = nil,
        video_ts: Double? = nil,
        type: String,
        severity: String,
        confidence: Double = 1.0,
        track_ids: [Int]? = nil,
        zone_id: String? = nil,
        direction: String? = nil,
        is_night: Bool? = false,
        snapshot_path: String? = nil,
        metadata: [String: JSONValue]? = nil,
        status: String? = nil,
        global_person_id: String? = nil
    ) {
        self.id = id
        self.session_id = session_id
        self.source_id = source_id
        self.ts = ts
        self.video_ts = video_ts
        self.type = type
        self.severity = severity
        self.confidence = confidence
        self.track_ids = track_ids
        self.zone_id = zone_id
        self.direction = direction
        self.is_night = is_night
        self.snapshot_path = snapshot_path
        self.metadata = metadata
        self.status = status
        self.global_person_id = global_person_id
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encodeIfPresent(session_id, forKey: .session_id)
        try container.encodeIfPresent(source_id, forKey: .source_id)
        try container.encodeIfPresent(ts, forKey: .ts)
        try container.encodeIfPresent(video_ts, forKey: .video_ts)
        try container.encode(type, forKey: .type)
        try container.encode(severity, forKey: .severity)
        try container.encode(confidence, forKey: .confidence)
        try container.encodeIfPresent(track_ids, forKey: .track_ids)
        try container.encodeIfPresent(zone_id, forKey: .zone_id)
        try container.encodeIfPresent(direction, forKey: .direction)
        try container.encodeIfPresent(is_night, forKey: .is_night)
        try container.encodeIfPresent(snapshot_path, forKey: .snapshot_path)
        try container.encodeIfPresent(metadata, forKey: .metadata)
        try container.encodeIfPresent(status, forKey: .status)
        try container.encodeIfPresent(global_person_id, forKey: .global_person_id)
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        // Resilient ID decoding
        if let strId = try? container.decode(String.self, forKey: .id) {
            self.id = strId
        } else if let intId = try? container.decode(Int.self, forKey: .id) {
            self.id = "\(intId)"
        } else {
            self.id = UUID().uuidString
        }

        self.session_id = try? container.decode(String.self, forKey: .session_id)
        self.source_id = try? container.decode(String.self, forKey: .source_id)

        // Timestamp decoding
        if let tsStr = try? container.decode(String.self, forKey: .ts) {
            self.ts = tsStr
        } else if let tsNum = try? container.decode(Double.self, forKey: .timestamp) {
            self.ts = "\(tsNum)"
        } else {
            self.ts = nil
        }

        self.video_ts = try? container.decode(Double.self, forKey: .video_ts)
        self.type = (try? container.decode(String.self, forKey: .type)) ?? "UNKNOWN"
        self.severity = (try? container.decode(String.self, forKey: .severity)) ?? "INFO"
        self.confidence = (try? container.decode(Double.self, forKey: .confidence)) ?? 1.0
        self.track_ids = try? container.decode([Int].self, forKey: .track_ids)
        self.zone_id = try? container.decode(String.self, forKey: .zone_id)
        self.direction = try? container.decode(String.self, forKey: .direction)
        self.is_night = try? container.decode(Bool.self, forKey: .is_night)
        self.snapshot_path = try? container.decode(String.self, forKey: .snapshot_path)
        self.metadata = try? container.decode([String: JSONValue].self, forKey: .metadata)
        self.status = try? container.decode(String.self, forKey: .status)
        self.global_person_id = try? container.decode(String.self, forKey: .global_person_id)
    }
}

public struct EventsListResponse: Codable, Sendable {
    public let events: [EventRow]
    public let count: Int
    public let next_before: String?
    public let next_before_id: String?
}

// MARK: - 7-W Structured Event Summary Models

public struct EventWhatSummary: Codable, Hashable, Sendable {
    public let type: String
    public let severity: String
    public let confidence: Double
    public let is_night: Bool?
    public let summary: String?

    public init(
        type: String = "UNKNOWN",
        severity: String = "INFO",
        confidence: Double = 1.0,
        is_night: Bool? = nil,
        summary: String? = nil
    ) {
        self.type = type
        self.severity = severity
        self.confidence = confidence
        self.is_night = is_night
        self.summary = summary
    }
}

public struct EventWhoSummary: Codable, Hashable, Sendable {
    public let track_ids: [Int]?
    public let primary_track: Int?
    public let global_person_id: String?
    public let class_name: String?

    public init(
        track_ids: [Int]? = nil,
        primary_track: Int? = nil,
        global_person_id: String? = nil,
        class_name: String? = nil
    ) {
        self.track_ids = track_ids
        self.primary_track = primary_track
        self.global_person_id = global_person_id
        self.class_name = class_name
    }
}

public struct EventWhereSummary: Codable, Hashable, Sendable {
    public let zone_id: String?
    public let zone_type: String?
    public let camera_id: String?
    public let camera_label: String?
    public let geo_sector: String?

    public init(
        zone_id: String? = nil,
        zone_type: String? = nil,
        camera_id: String? = nil,
        camera_label: String? = nil,
        geo_sector: String? = nil
    ) {
        self.zone_id = zone_id
        self.zone_type = zone_type
        self.camera_id = camera_id
        self.camera_label = camera_label
        self.geo_sector = geo_sector
    }
}

public struct EventWhenSummary: Codable, Hashable, Sendable {
    public let ts: String?
    public let video_ts: Double?
    public let video_time_formatted: String?
    public let clock_time: String?

    public init(
        ts: String? = nil,
        video_ts: Double? = nil,
        video_time_formatted: String? = nil,
        clock_time: String? = nil
    ) {
        self.ts = ts
        self.video_ts = video_ts
        self.video_time_formatted = video_time_formatted
        self.clock_time = clock_time
    }
}

public struct EventMovementSummary: Codable, Hashable, Sendable {
    public let direction: String?
    public let speed_px_s: Double?
    public let trajectory_points: Int?

    public init(
        direction: String? = nil,
        speed_px_s: Double? = nil,
        trajectory_points: Int? = nil
    ) {
        self.direction = direction
        self.speed_px_s = speed_px_s
        self.trajectory_points = trajectory_points
    }
}

public struct EventWhySummary: Codable, Hashable, Sendable {
    public let rule: String?
    public let description: String?
    public let trigger_condition: String?

    public init(
        rule: String? = nil,
        description: String? = nil,
        trigger_condition: String? = nil
    ) {
        self.rule = rule
        self.description = description
        self.trigger_condition = trigger_condition
    }
}

public struct EventEvidenceSummary: Codable, Hashable, Sendable {
    public let snapshot_path: String?
    public let has_snapshot: Bool
    public let evidence_count: Int

    public init(
        snapshot_path: String? = nil,
        has_snapshot: Bool = false,
        evidence_count: Int = 0
    ) {
        self.snapshot_path = snapshot_path
        self.has_snapshot = has_snapshot
        self.evidence_count = evidence_count
    }
}

public struct EventSummaryResponse: Codable, Hashable, Sendable {
    public let event_id: String
    public let session_id: String?
    public let source_id: String?
    public let what: EventWhatSummary?
    public let who: EventWhoSummary?
    public let where_loc: EventWhereSummary?
    public let when_time: EventWhenSummary?
    public let movement: EventMovementSummary?
    public let why: EventWhySummary?
    public let evidence: EventEvidenceSummary?
    public let narrative: String?
    public let structured: [String: JSONValue]?

    enum CodingKeys: String, CodingKey {
        case event_id, session_id, source_id, what, who, movement, why, evidence, narrative, structured
        case where_loc = "where"
        case when_time = "when"
    }

    public init(
        event_id: String,
        session_id: String? = nil,
        source_id: String? = nil,
        what: EventWhatSummary? = nil,
        who: EventWhoSummary? = nil,
        where_loc: EventWhereSummary? = nil,
        when_time: EventWhenSummary? = nil,
        movement: EventMovementSummary? = nil,
        why: EventWhySummary? = nil,
        evidence: EventEvidenceSummary? = nil,
        narrative: String? = nil,
        structured: [String: JSONValue]? = nil
    ) {
        self.event_id = event_id
        self.session_id = session_id
        self.source_id = source_id
        self.what = what
        self.who = who
        self.where_loc = where_loc
        self.when_time = when_time
        self.movement = movement
        self.why = why
        self.evidence = evidence
        self.narrative = narrative
        self.structured = structured
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.event_id = (try? container.decode(String.self, forKey: .event_id)) ?? ""
        self.session_id = try? container.decode(String.self, forKey: .session_id)
        self.source_id = try? container.decode(String.self, forKey: .source_id)
        self.narrative = try? container.decode(String.self, forKey: .narrative)
        self.structured = try? container.decode([String: JSONValue].self, forKey: .structured)

        var structuredContainer: KeyedDecodingContainer<CodingKeys>? = nil
        if container.contains(.structured) {
            structuredContainer = try? container.nestedContainer(keyedBy: CodingKeys.self, forKey: .structured)
        }

        // WHAT
        if let whatObj = try? container.decode(EventWhatSummary.self, forKey: .what) {
            self.what = whatObj
        } else if let whatObj = try? structuredContainer?.decode(EventWhatSummary.self, forKey: .what) {
            self.what = whatObj
        } else if let whatStr = try? container.decode(String.self, forKey: .what) {
            self.what = EventWhatSummary(summary: whatStr)
        } else {
            self.what = nil
        }

        // WHO
        if let whoObj = try? container.decode(EventWhoSummary.self, forKey: .who) {
            self.who = whoObj
        } else if let whoObj = try? structuredContainer?.decode(EventWhoSummary.self, forKey: .who) {
            self.who = whoObj
        } else {
            self.who = nil
        }

        // WHERE
        if let whereObj = try? container.decode(EventWhereSummary.self, forKey: .where_loc) {
            self.where_loc = whereObj
        } else if let whereObj = try? structuredContainer?.decode(EventWhereSummary.self, forKey: .where_loc) {
            self.where_loc = whereObj
        } else {
            self.where_loc = nil
        }

        // WHEN
        if let whenObj = try? container.decode(EventWhenSummary.self, forKey: .when_time) {
            self.when_time = whenObj
        } else if let whenObj = try? structuredContainer?.decode(EventWhenSummary.self, forKey: .when_time) {
            self.when_time = whenObj
        } else {
            self.when_time = nil
        }

        // MOVEMENT
        if let movObj = try? container.decode(EventMovementSummary.self, forKey: .movement) {
            self.movement = movObj
        } else if let movObj = try? structuredContainer?.decode(EventMovementSummary.self, forKey: .movement) {
            self.movement = movObj
        } else {
            self.movement = nil
        }

        // WHY
        if let whyObj = try? container.decode(EventWhySummary.self, forKey: .why) {
            self.why = whyObj
        } else if let whyObj = try? structuredContainer?.decode(EventWhySummary.self, forKey: .why) {
            self.why = whyObj
        } else if let whyStr = try? container.decode(String.self, forKey: .why) {
            self.why = EventWhySummary(description: whyStr)
        } else {
            self.why = nil
        }

        // EVIDENCE
        if let evObj = try? container.decode(EventEvidenceSummary.self, forKey: .evidence) {
            self.evidence = evObj
        } else if let evObj = try? structuredContainer?.decode(EventEvidenceSummary.self, forKey: .evidence) {
            self.evidence = evObj
        } else {
            self.evidence = nil
        }
    }
}

// MARK: - Session Summary & History Models

public struct SessionTracksSummary: Codable, Hashable, Sendable {
    public let total_tracks: Int
    public let person_tracks: Int
    public let vehicle_tracks: Int
    public let other_tracks: Int
    public let max_concurrent_persons: Int
    public let max_concurrent_vehicles: Int
}

public struct SessionEventsSummary: Codable, Hashable, Sendable {
    public let total_events: Int
    public let critical: Int
    public let warning: Int
    public let info: Int
    public let by_type: [String: Int]?
}

public struct SessionGeoSummary: Codable, Hashable, Sendable {
    public let source_id: String?
    public let latitude: Double?
    public let longitude: Double?
    public let sector: String?
    public let threat_level: String?
}

public struct SessionSummaryResponse: Codable, Hashable, Sendable {
    public let session_id: String
    public let source_id: String?
    public let source_name: String?
    public let status: String?
    public let started_at: String?
    public let ended_at: String?
    public let duration_s: Double?
    public let frames_processed: Int?
    public let fps: Double?
    public let tracks_summary: SessionTracksSummary?
    public let events_summary: SessionEventsSummary?
    public let geographic: SessionGeoSummary?
    public let narrative: String?
    public let structured: [String: JSONValue]?
}

public struct SessionHistoryItem: Codable, Identifiable, Hashable, Sendable {
    public let id: String
    public let source_id: String?
    public let status: String?
    public let started_at: String?
    public let ended_at: String?
    public let stats: [String: JSONValue]?
}

public struct SessionsListResponse: Codable, Sendable {
    public let sessions: [SessionHistoryItem]
    public let count: Int
}

public struct SessionTrackRow: Codable, Identifiable, Hashable, Sendable {
    public var id: Int { track_id }
    public let track_id: Int
    public let class_name: String
    public let first_seen: String?
    public let last_seen: String?
    public let frames: Int?
    public let max_conf: Double?
    public let trajectory: [[Double]]?
}

public struct SessionTracksResponse: Codable, Sendable {
    public let session_id: String
    public let tracks: [SessionTrackRow]
    public let count: Int
}

// MARK: - Virtual Zones & Fences

public struct ZoneGeometry: Codable, Hashable, Sendable {
    public let points: [[Double]]?
    public let p1: [Double]?
    public let p2: [Double]?
}

public struct ZoneModel: Codable, Identifiable, Hashable, Sendable {
    public let id: String
    public let source_id: String
    public let name: String
    public let type: String              // RESTRICTED, WATCH, TRIPWIRE
    public let kind: String              // polygon, line
    public let geometry: ZoneGeometry
    public let active: Bool

    public var polygon: [[Double]] {
        geometry.points ?? []
    }
}

public struct ZonesListResponse: Codable, Sendable {
    public let zones: [ZoneModel]
    public let count: Int
}

// MARK: - Sources & Cameras

public struct SourceItem: Codable, Identifiable, Hashable, Sendable {
    public let id: String
    public let type: String              // file, webcam, rtsp, demo
    public let name: String?
    public let path: String?
    public let is_active: Bool?
    public let live: Bool?
    public let fps: Double?
    public let lat: Double?
    public let lng: Double?
    public let latitude: Double?
    public let longitude: Double?
    public let label: String?
    public let status: String?
    public let sector: String?

    public var effectiveLat: Double? {
        latitude ?? lat
    }

    public var effectiveLng: Double? {
        longitude ?? lng
    }

    public var isLiveActive: Bool {
        (is_active == true) || (live == true)
    }

    public var isDemo: Bool {
        type.lowercased() == "demo" || status?.lowercased() == "demo"
    }
}

public struct SourceCreateRequest: Codable, Sendable {
    public let id: String
    public let name: String?
    public let type: String
    public let uri: String?
    public let latitude: Double?
    public let longitude: Double?
    public let label: String?
    public let status: String?

    public init(
        id: String,
        name: String? = nil,
        type: String = "rtsp",
        uri: String? = nil,
        latitude: Double? = nil,
        longitude: Double? = nil,
        label: String? = nil,
        status: String? = "idle"
    ) {
        self.id = id
        self.name = name
        self.type = type
        self.uri = uri
        self.latitude = latitude
        self.longitude = longitude
        self.label = label
        self.status = status
    }
}

public struct SeedDemoResponse: Codable, Sendable {
    public let status: String
    public let seeded_cameras: [String]
    public let count: Int
}

public struct SourcesListResponse: Codable, Sendable {
    public let sources: [SourceItem]
    public let count: Int?
}

public struct UploadResponse: Codable, Sendable {
    public let status: String
    public let filename: String
    public let path: String
    public let size_bytes: Int64
    public let probe: [String: JSONValue]?
}

// MARK: - Re-ID Gallery Models

public struct ReIDPersonSummary: Codable, Identifiable, Hashable, Sendable {
    public var id: String { global_id }
    public let global_id: String
    public let first_seen_ts: Double?
    public let last_seen_ts: Double?
    public let observation_count: Int
    public let cameras: [String]
    public let track_ids: [Int]?
    public let confidence: Double?
    public let thumbnail_b64: String?

    public var person_id: String { global_id }
    public var cameras_seen: [String] { cameras }

    public var first_seen: String {
        guard let ts = first_seen_ts, ts > 0 else { return "N/A" }
        let date = Date(timeIntervalSince1970: ts)
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        return formatter.string(from: date)
    }

    public var last_seen: String {
        guard let ts = last_seen_ts, ts > 0 else { return "N/A" }
        let date = Date(timeIntervalSince1970: ts)
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"
        return formatter.string(from: date)
    }

    public init(
        global_id: String,
        first_seen_ts: Double? = nil,
        last_seen_ts: Double? = nil,
        observation_count: Int = 1,
        cameras: [String] = [],
        track_ids: [Int]? = nil,
        confidence: Double? = nil,
        thumbnail_b64: String? = nil
    ) {
        self.global_id = global_id
        self.first_seen_ts = first_seen_ts
        self.last_seen_ts = last_seen_ts
        self.observation_count = observation_count
        self.cameras = cameras
        self.track_ids = track_ids
        self.confidence = confidence
        self.thumbnail_b64 = thumbnail_b64
    }

    enum CodingKeys: String, CodingKey {
        case global_id, global_person_id, person_id, id
        case first_seen_ts, first_seen
        case last_seen_ts, last_seen
        case observation_count, observations
        case cameras, cameras_visited, cameras_seen
        case track_ids, track_bindings
        case confidence
        case thumbnail_b64
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        if let gid = try? container.decode(String.self, forKey: .global_id) {
            self.global_id = gid
        } else if let gpid = try? container.decode(String.self, forKey: .global_person_id) {
            self.global_id = gpid
        } else if let pid = try? container.decode(String.self, forKey: .person_id) {
            self.global_id = pid
        } else if let id = try? container.decode(String.self, forKey: .id) {
            self.global_id = id
        } else {
            self.global_id = "unknown"
        }

        if let fts = try? container.decode(Double.self, forKey: .first_seen_ts) {
            self.first_seen_ts = fts
        } else if let fts = try? container.decode(Double.self, forKey: .first_seen) {
            self.first_seen_ts = fts
        } else {
            self.first_seen_ts = nil
        }

        if let lts = try? container.decode(Double.self, forKey: .last_seen_ts) {
            self.last_seen_ts = lts
        } else if let lts = try? container.decode(Double.self, forKey: .last_seen) {
            self.last_seen_ts = lts
        } else {
            self.last_seen_ts = nil
        }

        if let obs = try? container.decode(Int.self, forKey: .observation_count) {
            self.observation_count = obs
        } else if let obs = try? container.decode(Int.self, forKey: .observations) {
            self.observation_count = obs
        } else {
            self.observation_count = 1
        }

        if let cams = try? container.decode([String].self, forKey: .cameras) {
            self.cameras = cams
        } else if let cams = try? container.decode([String].self, forKey: .cameras_visited) {
            self.cameras = cams
        } else if let cams = try? container.decode([String].self, forKey: .cameras_seen) {
            self.cameras = cams
        } else {
            self.cameras = []
        }

        self.track_ids = try? container.decode([Int].self, forKey: .track_ids)
        self.confidence = try? container.decode(Double.self, forKey: .confidence)
        self.thumbnail_b64 = try? container.decode(String.self, forKey: .thumbnail_b64)
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(global_id, forKey: .global_id)
        try container.encodeIfPresent(first_seen_ts, forKey: .first_seen_ts)
        try container.encodeIfPresent(last_seen_ts, forKey: .last_seen_ts)
        try container.encode(observation_count, forKey: .observation_count)
        try container.encode(cameras, forKey: .cameras)
        try container.encodeIfPresent(track_ids, forKey: .track_ids)
        try container.encodeIfPresent(confidence, forKey: .confidence)
        try container.encodeIfPresent(thumbnail_b64, forKey: .thumbnail_b64)
    }
}

public struct ReIDPersonsResponse: Codable, Sendable {
    public let persons: [ReIDPersonSummary]
    public let count: Int
    public let note: String?
}

// MARK: - Hermes AI Models

public struct HermesAskRequest: Codable, Sendable {
    public let question: String
    public let event_id: String?
    public let session_id: String?
    public let model: String?

    public init(question: String, event_id: String? = nil, session_id: String? = nil, model: String? = nil) {
        self.question = question
        self.event_id = event_id
        self.session_id = session_id
        self.model = model
    }
}

public struct GroundedFact: Codable, Identifiable, Hashable, Sendable {
    public var id: String { "\(fact_type)_\(timestamp)_\(source_id)" }
    public let fact_type: String         // OBSERVED, DERIVED, INFERRED
    public let statement: String
    public let timestamp: Double
    public let source_id: String
    public let confidence: Double
    public let event_id: String?
}

public struct HermesAskResponse: Codable, Sendable {
    public let answer: String
    public let model: String?
    public let elapsed_ms: Double?
    public let grounded_event_id: String?
    public let grounded_session_id: String?
    public let context: [String: JSONValue]?
}

public struct HermesStatusResponse: Codable, Sendable {
    public let connected: Bool?
    public let enabled: Bool?
    public let model: String?
    public let gateway: String?
    public let checked_at: String?
    public let error: String?

    public var available: Bool {
        connected == true
    }
    public var model_name: String {
        model ?? "Hermes-3-Llama-3.1-8B"
    }
    public var base_url: String {
        gateway ?? "https://gateway.ai.cloudflare.com"
    }
}

// MARK: - GIS & Map Models

public struct GeoSector: Codable, Identifiable, Hashable, Sendable {
    public let id: String
    public let name: String
    public let polygon: [[Double]]       // [[lat, lng], ...]
    public let threat_level: String?     // LOW, ELEVATED, HIGH, SEVERE
    public let kind: String?
    public let description: String?
    public let active: Bool?
    public let active_cameras: [String]?

    public var colorHex: String {
        switch (threat_level ?? "LOW").uppercased() {
        case "SEVERE", "CRITICAL": return "#EF4444"
        case "HIGH": return "#F97316"
        case "ELEVATED", "WARNING": return "#F59E0B"
        default: return "#10B981"
        }
    }
}

public struct MapCameraItem: Codable, Identifiable, Hashable, Sendable {
    public var id: String { camera_id }
    public let camera_id: String
    public let source_id: String
    public let label: String
    public let latitude: Double?
    public let longitude: Double?
    public let has_coordinates: Bool
    public let status: String
    public let type: String

    public init(
        camera_id: String? = nil,
        source_id: String,
        label: String = "",
        latitude: Double? = nil,
        longitude: Double? = nil,
        has_coordinates: Bool? = nil,
        status: String = "idle",
        type: String = "camera"
    ) {
        self.camera_id = camera_id ?? source_id
        self.source_id = source_id
        self.label = label
        self.latitude = latitude
        self.longitude = longitude
        self.has_coordinates = has_coordinates ?? (latitude != nil && longitude != nil)
        self.status = status
        self.type = type
    }
}

public struct MapCamerasResponse: Codable, Sendable {
    public let cameras: [MapCameraItem]
}

public struct MapSectorsResponse: Codable, Sendable {
    public let sectors: [GeoSector]
}

public struct MapConfigResponse: Codable, Sendable {
    public let google_maps_key: String?
    public let has_key: Bool?
    public let has_tiles: Bool?
    public let fallback: String?
    public let simulated: Bool?
    public let label: String?
    public let default_center: [Double]?
    public let default_zoom: Double?
    public let sectors: [GeoSector]?

    public var engine: String {
        if has_key == true && !(google_maps_key ?? "").isEmpty {
            return "Google Maps Satellite"
        }
        return "Tactical Radar (Schematic)"
    }
}
