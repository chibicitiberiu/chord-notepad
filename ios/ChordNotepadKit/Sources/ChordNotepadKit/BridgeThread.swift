import Foundation

/// The one thread every Swift → Python call runs on ("python-bridge"), in the
/// order the calls were queued. It is the "serial bridge queue" of the
/// threading contract (docs/IOS.md): a dedicated thread rather than a
/// DispatchQueue so that Python always sees the same OS thread (its main
/// thread, since the interpreter starts here) and so it can have a large
/// stack. Secondary threads on Apple platforms get 512 KB by default, too
/// little for the core's imports.
///
/// The thread lives as long as the process, like the interpreter.
final class BridgeThread: @unchecked Sendable {
    /// The stack the bridge thread gets (16 MB; the imports recurse deeply).
    static let stackSize = 16 << 20

    private let condition = NSCondition()
    private var jobs: [@Sendable () -> Void] = []
    private var thread: Thread?

    init(name: String = "python-bridge") {
        let thread = Thread { [self] in self.loop() }
        thread.name = name
        thread.stackSize = BridgeThread.stackSize
        condition.lock()
        self.thread = thread
        condition.unlock()
        thread.start()
    }

    /// Whether the caller is on the bridge thread.
    var isCurrent: Bool {
        condition.lock()
        defer { condition.unlock() }
        return Thread.current === thread
    }

    /// Queue `job`; returns at once.
    func post(_ job: @escaping @Sendable () -> Void) {
        condition.lock()
        jobs.append(job)
        condition.signal()
        condition.unlock()
    }

    /// Run `body` on the bridge thread and return its result.
    func run<T: Sendable>(_ body: @escaping @Sendable () throws -> T) async throws -> T {
        try await withCheckedThrowingContinuation { continuation in
            post {
                continuation.resume(with: Result { try body() })
            }
        }
    }

    private func loop() {
        while true {
            condition.lock()
            while jobs.isEmpty {
                condition.wait()
            }
            let job = jobs.removeFirst()
            condition.unlock()
            job()
        }
    }
}
