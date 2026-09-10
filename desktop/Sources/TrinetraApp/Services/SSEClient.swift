import Foundation

public final class SSEClient: @unchecked Sendable {
    private let url: URL
    private var task: URLSessionDataTask?
    private var isRunning = false
    private let onEvent: @Sendable (EventRow) -> Void
    private let onError: @Sendable (Error) -> Void

    public init(url: URL, onEvent: @escaping @Sendable (EventRow) -> Void, onError: @escaping @Sendable (Error) -> Void) {
        self.url = url
        self.onEvent = onEvent
        self.onError = onError
    }

    public func start() {
        guard !isRunning else { return }
        isRunning = true

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 3600.0
        config.timeoutIntervalForResource = 86400.0
        let session = URLSession(configuration: config, delegate: SSEDelegate(onEvent: onEvent, onError: onError), delegateQueue: nil)
        var request = URLRequest(url: url)
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        let task = session.dataTask(with: request)
        self.task = task
        task.resume()
    }

    public func stop() {
        isRunning = false
        task?.cancel()
        task = nil
    }

    private final class SSEDelegate: NSObject, URLSessionDataDelegate, @unchecked Sendable {
        private var lineBuffer = ""
        private let onEvent: @Sendable (EventRow) -> Void
        private let onError: @Sendable (Error) -> Void

        init(onEvent: @escaping @Sendable (EventRow) -> Void, onError: @escaping @Sendable (Error) -> Void) {
            self.onEvent = onEvent
            self.onError = onError
        }

        func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
            guard let text = String(data: data, encoding: .utf8) else { return }
            lineBuffer.append(text)

            var lines = lineBuffer.components(separatedBy: "\n")
            lineBuffer = lines.removeLast() // Keep incomplete line in buffer

            for line in lines {
                let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
                if trimmed.hasPrefix("data:") {
                    let jsonStr = trimmed.dropFirst(5).trimmingCharacters(in: .whitespaces)
                    if let jsonData = jsonStr.data(using: .utf8) {
                        do {
                            let event = try JSONDecoder().decode(EventRow.self, from: jsonData)
                            DispatchQueue.main.async {
                                self.onEvent(event)
                            }
                        } catch {
                            // Non-event data or keepalive ping
                        }
                    }
                }
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
