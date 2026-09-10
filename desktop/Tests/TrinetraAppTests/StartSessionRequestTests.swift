#if canImport(Testing)
import Testing
import Foundation
@testable import TrinetraApp

@Suite("StartSessionRequest Schema Tests")
struct StartSessionRequestTests {
    @Test("File Session Request Schema matches backend")
    func testFileSessionRequestSchema() throws {
        let req = StartSessionRequest(type: "file", path: "/tmp/sample.mp4")
        let data = try JSONEncoder().encode(req)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        #expect(json != nil)
        #expect(json?["type"] as? String == "file")
        #expect(json?["path"] as? String == "/tmp/sample.mp4")
        #expect(json?["source_type"] == nil)
        #expect(json?["source_path"] == nil)
    }

    @Test("Webcam Session Request Schema matches backend")
    func testWebcamSessionRequestSchema() throws {
        let req = StartSessionRequest(type: "webcam", index: 0)
        let data = try JSONEncoder().encode(req)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        #expect(json != nil)
        #expect(json?["type"] as? String == "webcam")
        #expect(json?["index"] as? Int == 0)
        #expect(json?["source_type"] == nil)
        #expect(json?["camera_index"] == nil)
    }

    @Test("RTSP Session Request Schema matches backend")
    func testRtspSessionRequestSchema() throws {
        let req = StartSessionRequest(type: "rtsp", uri: "rtsp://10.0.0.1/live")
        let data = try JSONEncoder().encode(req)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        #expect(json != nil)
        #expect(json?["type"] as? String == "rtsp")
        #expect(json?["uri"] as? String == "rtsp://10.0.0.1/live")
        #expect(json?["source_type"] == nil)
        #expect(json?["rtsp_url"] == nil)
    }

    @Test("LayerState Keys match canonical layer dictionary")
    func testLayerStateKeys() throws {
        let layers = LayerState()
        let data = try JSONEncoder().encode(layers)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        #expect(json != nil)
        let keys = Set(json?.keys ?? Dictionary<String, Any>().keys)
        let validKeys: Set<String> = ["boxes", "labels", "fps", "trajectories", "zones", "faces", "pose"]
        #expect(keys.isSubset(of: validKeys))
    }
}
#elseif canImport(XCTest)
import XCTest
@testable import TrinetraApp

final class StartSessionRequestTests: XCTestCase {
    func testFileSessionRequestSchema() throws {
        let req = StartSessionRequest(type: "file", path: "/tmp/sample.mp4")
        let data = try JSONEncoder().encode(req)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertNotNil(json)
        XCTAssertEqual(json?["type"] as? String, "file")
        XCTAssertEqual(json?["path"] as? String, "/tmp/sample.mp4")
        XCTAssertNil(json?["source_type"], "Must not send source_type key - canonical FastAPI backend contract requires 'type'")
        XCTAssertNil(json?["source_path"], "Must not send source_path key - canonical FastAPI backend contract requires 'path'")
    }

    func testWebcamSessionRequestSchema() throws {
        let req = StartSessionRequest(type: "webcam", index: 0)
        let data = try JSONEncoder().encode(req)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertNotNil(json)
        XCTAssertEqual(json?["type"] as? String, "webcam")
        XCTAssertEqual(json?["index"] as? Int, 0)
        XCTAssertNil(json?["source_type"])
        XCTAssertNil(json?["camera_index"])
    }

    func testRtspSessionRequestSchema() throws {
        let req = StartSessionRequest(type: "rtsp", uri: "rtsp://10.0.0.1/live")
        let data = try JSONEncoder().encode(req)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertNotNil(json)
        XCTAssertEqual(json?["type"] as? String, "rtsp")
        XCTAssertEqual(json?["uri"] as? String, "rtsp://10.0.0.1/live")
        XCTAssertNil(json?["source_type"])
        XCTAssertNil(json?["rtsp_url"])
    }

    func testLayerStateKeys() throws {
        let layers = LayerState()
        let data = try JSONEncoder().encode(layers)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]

        XCTAssertNotNil(json)
        let keys = Set(json?.keys ?? Dictionary<String, Any>().keys)
        let validKeys: Set<String> = ["boxes", "labels", "fps", "trajectories", "zones", "faces", "pose"]
        XCTAssertTrue(keys.isSubset(of: validKeys), "LayerState keys must match backend allowed layer set: \(keys)")
    }
}
#endif
