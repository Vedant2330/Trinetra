import Foundation
import AppKit

public final class MJPEGStreamer: @unchecked Sendable {
    private let url: URL
    private var task: URLSessionDataTask?
    private var isRunning = false
    private let onFrame: @Sendable (NSImage) -> Void
    private let onError: @Sendable (Error) -> Void

    public init(url: URL, onFrame: @escaping @Sendable (NSImage) -> Void, onError: @escaping @Sendable (Error) -> Void) {
        self.url = url
        self.onFrame = onFrame
        self.onError = onError
    }

    public func start() {
        guard !isRunning else { return }
        isRunning = true

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 60.0
        config.timeoutIntervalForResource = 3600.0
        let session = URLSession(configuration: config, delegate: StreamDelegate(onFrame: onFrame, onError: onError), delegateQueue: nil)
        var request = URLRequest(url: url)
        request.setValue("image/jpeg", forHTTPHeaderField: "Accept")
        let task = session.dataTask(with: request)
        self.task = task
        task.resume()
    }

    public func stop() {
        isRunning = false
        task?.cancel()
        task = nil
    }

    private final class StreamDelegate: NSObject, URLSessionDataDelegate, @unchecked Sendable {
        private var buffer = Data()
        private let onFrame: @Sendable (NSImage) -> Void
        private let onError: @Sendable (Error) -> Void

        private let soi = Data([0xFF, 0xD8]) // Start of JPEG
        private let eoi = Data([0xFF, 0xD9]) // End of JPEG

        init(onFrame: @escaping @Sendable (NSImage) -> Void, onError: @escaping @Sendable (Error) -> Void) {
            self.onFrame = onFrame
            self.onError = onError
        }

        func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
            buffer.append(data)

            while let startRange = buffer.range(of: soi) {
                let afterStart = buffer.subdata(in: startRange.lowerBound..<buffer.count)
                if let endRange = afterStart.range(of: eoi) {
                    let fullJpegData = afterStart.subdata(in: 0..<endRange.upperBound)
                    if let image = NSImage(data: fullJpegData) {
                        DispatchQueue.main.async {
                            self.onFrame(image)
                        }
                    }
                    // Advance buffer past this JPEG
                    let consumed = startRange.lowerBound + endRange.upperBound
                    if consumed <= buffer.count {
                        buffer.removeSubrange(0..<consumed)
                    } else {
                        buffer.removeAll()
                        break
                    }
                } else {
                    // Truncate garbage before SOI
                    if startRange.lowerBound > 0 {
                        buffer.removeSubrange(0..<startRange.lowerBound)
                    }
                    break
                }
            }

            // Cap buffer size if searching runs unbounded
            if buffer.count > 10 * 1024 * 1024 {
                buffer.removeAll()
            }
        }

        func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
            if let error = error {
                let nsError = error as NSError
                if nsError.code != NSURLErrorCancelled {
                    DispatchQueue.main.async {
                        self.onError(error)
                    }
                }
            }
        }
    }
}
