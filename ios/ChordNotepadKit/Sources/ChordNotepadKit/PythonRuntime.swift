import CNBridge
import Foundation

/// A failure inside Python (or starting it); `message` holds Python's
/// formatted traceback when there is one.
public struct PythonError: Error, CustomStringConvertible, Sendable {
    public let message: String

    public init(_ message: String) {
        self.message = message
    }

    public var description: String { message }
}

/// The embedded CPython interpreter: one per process, never finalized.
///
/// Every call into Python runs on the runtime's bridge thread
/// (``BridgeThread``), under the GIL the C side takes for it, so no Swift
/// caller (the main thread included) ever runs Python code itself. The
/// interpreter starts on that thread with:
/// - an isolated `PyConfig` (no `PYTHON*` variables, no user site folder),
///   UTF-8 mode, no signal handlers (the app owns them);
/// - `home` and the folders put in front of `sys.path` from ``Configuration``,
///   plus the kit's own Python glue (`chordnotepad_ios`);
/// - `use_system_logger` on iOS, so `print` and logging reach the system log.
///
/// After the start the GIL is released (`PyEval_SaveThread`), so Python's own
/// threads (`python-session`, the render and export workers) run freely.
public final class PythonRuntime: @unchecked Sendable {
    /// How to start the interpreter.
    public struct Configuration: Sendable, Equatable {
        /// `PyConfig.home` (the stdlib's prefix: the app's `python` folder on
        /// iOS), or nil to let CPython find its own (Linux tests).
        public var home: String?
        /// Folders put in front of `sys.path`, in order (the core, its
        /// packages). The kit's glue folder follows them.
        public var searchPaths: [String]
        /// Variables set with `setenv` before Python starts, e.g.
        /// `CHORD_NOTEPAD_LIBFLUIDSYNTH` (iOS) or `CN_TEST_FAKE_PLAYER` (tests).
        public var environment: [String: String]
        /// Write `__pycache__` files (off: the app bundle is read-only).
        public var writeBytecode: Bool
        /// Send stdout and stderr to the system log (Apple builds only).
        public var useSystemLogger: Bool

        public init(home: String? = nil, searchPaths: [String] = [],
                    environment: [String: String] = [:], writeBytecode: Bool = false,
                    useSystemLogger: Bool = Configuration.defaultUseSystemLogger) {
            self.home = home
            self.searchPaths = searchPaths
            self.environment = environment
            self.writeBytecode = writeBytecode
            self.useSystemLogger = useSystemLogger
        }

        #if os(iOS)
        public static let defaultUseSystemLogger = true
        #else
        public static let defaultUseSystemLogger = false
        #endif
    }

    /// The configuration the interpreter started with.
    public let configuration: Configuration

    let thread: BridgeThread

    private init(configuration: Configuration, thread: BridgeThread) {
        self.configuration = configuration
        self.thread = thread
    }

    /// The folder holding the kit's Python glue (`chordnotepad_ios`).
    public static var gluePath: String {
        Bundle.module.resourceURL!.appendingPathComponent("Python").path
    }

    private static let lock = NSLock()
    nonisolated(unsafe) private static var started: (Configuration, Task<PythonRuntime, Error>)?

    /// Start the interpreter, or return the running one.
    ///
    /// There is one interpreter per process and it is never finalized, so a
    /// second call with the same configuration returns the same runtime (a
    /// failed start stays failed); another configuration is an error.
    public static func start(_ configuration: Configuration) async throws -> PythonRuntime {
        let task: Task<PythonRuntime, Error> = lock.withLock {
            if let (running, task) = started {
                if running == configuration {
                    return task
                }
                return Task {
                    throw PythonError("Python is already running with another configuration "
                                      + "(one interpreter per process)")
                }
            }
            let task = Task { try await boot(configuration) }
            started = (configuration, task)
            return task
        }
        return try await task.value
    }

    private static func boot(_ configuration: Configuration) async throws -> PythonRuntime {
        let thread = BridgeThread()
        let paths = configuration.searchPaths + [gluePath]
        try await thread.run {
            for (name, value) in configuration.environment {
                setenv(name, value, 1)
            }
            let cPaths = paths.map { strdup($0) }
            defer { cPaths.forEach { free($0) } }
            let home = configuration.home.map { strdup($0) }
            defer { home.map { free($0) } }
            var error: UnsafeMutablePointer<CChar>?
            let code = cPaths.map { UnsafePointer($0) }.withUnsafeBufferPointer { buffer in
                var options = CNRuntimeOptions(
                    home: home.map { UnsafePointer($0!) } ?? nil,
                    paths: buffer.baseAddress,
                    path_count: buffer.count,
                    write_bytecode: configuration.writeBytecode ? 1 : 0,
                    use_system_logger: configuration.useSystemLogger ? 1 : 0)
                return cn_runtime_initialize(&options, &error)
            }
            try check(code, error)
        }
        return PythonRuntime(configuration: configuration, thread: thread)
    }

    /// `module.function(*args)` on the bridge thread; its `str()`, or nil for None.
    public func call(_ module: String, _ function: String, _ args: [String] = []) async throws -> String? {
        try await thread.run {
            let cArgs = args.map { strdup($0) }
            defer { cArgs.forEach { free($0) } }
            var result: UnsafeMutablePointer<CChar>?
            var error: UnsafeMutablePointer<CChar>?
            let code = cArgs.map { UnsafePointer($0) }.withUnsafeBufferPointer { buffer in
                cn_call_strings(module, function, buffer.baseAddress, buffer.count, &result, &error)
            }
            try check(code, error)
            return takeString(result)
        }
    }

    /// Run `body` on the bridge thread (for ``Session``).
    func onBridge<T: Sendable>(_ body: @escaping @Sendable () throws -> T) async throws -> T {
        try await thread.run(body)
    }

    /// Queue `body` on the bridge thread and return at once (for ``Session``).
    func postToBridge(_ body: @escaping @Sendable () -> Void) {
        thread.post(body)
    }
}

/// Throws the C side's error message (freeing it) unless `code` is `CN_OK`.
func check(_ code: Int32, _ error: UnsafeMutablePointer<CChar>?) throws {
    if code == CN_OK {
        if let error { cn_free(error) }
        return
    }
    throw PythonError(takeString(error) ?? "Python call failed")
}

/// A malloc'd C string as a String, freeing it; nil for NULL.
func takeString(_ pointer: UnsafeMutablePointer<CChar>?) -> String? {
    guard let pointer else { return nil }
    defer { cn_free(pointer) }
    return String(cString: pointer)
}

/// `text` as a malloc'd C string (for the C side to free).
func mallocString(_ text: String) -> UnsafeMutablePointer<CChar>? {
    strdup(text)
}
