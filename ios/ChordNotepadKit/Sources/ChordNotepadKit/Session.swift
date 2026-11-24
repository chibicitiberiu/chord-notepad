import CNBridge
import Foundation

/// A running core session behind the JSON bridge (docs/IOS.md, "Bridge contract").
///
/// Commands go in with ``submit(_:)``; every state and event comes out on
/// ``events`` as `(typeName, json)`, in delivery order, starting with the
/// replay of every state. Decode them with ``SessionOutput/decode(typeName:json:)``.
///
/// Threading: every call into Python runs on the runtime's bridge thread, in
/// the order it was made, so ``submit(_:)`` is safe from any thread (the main
/// thread included) and returns at once. Python delivers ``events`` from its
/// `python-session` thread without waiting for anything.
public final class Session: @unchecked Sendable {
    /// What Python's `chordnotepad_ios.host.start` needs.
    public struct LaunchOptions: Sendable, Encodable, Equatable {
        /// The app's private writable folder (Application Support): config,
        /// logs and data go under it.
        public var filesDir: String
        /// The SoundFont the app ships or copied, or nil.
        public var soundfontPath: String?
        /// The output's sample rate (0: FluidSynth's default).
        public var sampleRate: Int
        /// The output's buffer size in frames (0: FluidSynth's default).
        public var framesPerBuffer: Int
        /// Set up the log file and console logging (tests turn it off).
        public var configureLogging: Bool
        /// `session.platform`: `ios` in the app.
        public var platform: String

        public init(filesDir: String, soundfontPath: String? = nil, sampleRate: Int = 0,
                    framesPerBuffer: Int = 0, configureLogging: Bool = true,
                    platform: String = "ios") {
            self.filesDir = filesDir
            self.soundfontPath = soundfontPath
            self.sampleRate = sampleRate
            self.framesPerBuffer = framesPerBuffer
            self.configureLogging = configureLogging
            self.platform = platform
        }

        enum CodingKeys: String, CodingKey {
            case filesDir = "files_dir"
            case soundfontPath = "soundfont_path"
            case sampleRate = "sample_rate"
            case framesPerBuffer = "frames_per_buffer"
            case configureLogging = "configure_logging"
            case platform
        }

        public func encode(to encoder: Encoder) throws {
            var container = encoder.container(keyedBy: CodingKeys.self)
            try container.encode(filesDir, forKey: .filesDir)
            try container.encode(soundfontPath, forKey: .soundfontPath)
            try container.encode(sampleRate, forKey: .sampleRate)
            try container.encode(framesPerBuffer, forKey: .framesPerBuffer)
            try container.encode(configureLogging, forKey: .configureLogging)
            try container.encode(platform, forKey: .platform)
        }
    }

    /// One output: the DTO's Python class name and its fields as JSON.
    public typealias Event = (typeName: String, json: String)

    /// The Python module and function that start a session.
    static let entryModule = "chordnotepad_ios.host"
    static let entryFunction = "start"

    /// Every output, in delivery order. Unbounded: Python never waits for Swift.
    public let events: AsyncStream<Event>

    private let continuation: AsyncStream<Event>.Continuation
    private let runtime: PythonRuntime
    // Python's SessionHandle; only touched on the bridge thread.
    private var handle: UnsafeMutableRawPointer?

    private init(runtime: PythonRuntime) {
        self.runtime = runtime
        (events, continuation) = AsyncStream.makeStream(of: Event.self, bufferingPolicy: .unbounded)
    }

    /// Start the session (once per process): Python builds the core on its
    /// own thread and this returns once the session is running. The first
    /// events (the replay of every state) may arrive before it returns.
    ///
    /// - Parameters:
    ///   - runtime: The started interpreter.
    ///   - store: The documents Python reads and writes.
    ///   - options: Where the app's files are, and the audio settings.
    public static func start(runtime: PythonRuntime, store: DocumentStore,
                             options: LaunchOptions) async throws -> Session {
        let session = Session(runtime: runtime)
        let optionsJSON = String(decoding: try BridgeJSON.encoder.encode(options), as: UTF8.self)
        // The sink and the store go in before Python starts: the replay comes
        // from python-session while the bridge thread is still inside start.
        EventSinkRegistry.install(session.continuation)
        StoreRegistry.install(store)
        do {
            try await runtime.onBridge {
                var handle: UnsafeMutableRawPointer?
                var error: UnsafeMutablePointer<CChar>?
                let code = cn_start_handle(entryModule, entryFunction, optionsJSON, &handle, &error)
                try check(code, error)
                session.handle = handle
            }
        } catch {
            EventSinkRegistry.install(nil)
            session.continuation.finish()
            throw error
        }
        return session
    }

    /// Queue `command` for the session; returns at once. A command that can't
    /// be sent shows up on ``events`` as an `UnexpectedError` with context
    /// `bridge`, like one the core can't decode.
    public func submit(_ command: BridgeCommand) {
        let argsJSON: String
        do {
            argsJSON = try command.argsJSON()
        } catch {
            report("Command \(command.name) can't be encoded: \(error)", context: "bridge")
            return
        }
        submit(command: command.name, argsJSON: argsJSON)
    }

    /// Queue a command by name with its arguments as a JSON object.
    public func submit(command: String, argsJSON: String) {
        runtime.postToBridge { [self] in
            guard let handle else {
                report("No session; dropped command \(command)", context: "bridge")
                return
            }
            var error: UnsafeMutablePointer<CChar>?
            let code = cn_handle_submit(handle, command, argsJSON, &error)
            if code != CN_OK {
                report("Command \(command) failed: \(takeString(error) ?? "")", context: "bridge")
            }
        }
    }

    /// The active chord-sheet view packed as draw ops (op-buffer v2; decode it
    /// with ``SheetBuffer/decode(_:)``) for a strip `height` points tall, or
    /// nil without a rendered song. Packed by Python on the bridge thread,
    /// ordered with the commands; refetch when `ChordSheetState.song_revision`,
    /// `active_view`, `zoom` or the height changes. A failure is reported as
    /// an `UnexpectedError` (context `chord_sheet_buffer`) and returns nil.
    public func chordSheetBuffer(height: Double) async -> Data? {
        do {
            return try await runtime.onBridge { [self] () -> Data? in
                guard let handle else { return nil }
                var data: UnsafeMutablePointer<UInt8>?
                var length = 0
                var isNone: Int32 = 0
                var error: UnsafeMutablePointer<CChar>?
                let code = cn_handle_chord_sheet_buffer(handle, height, &data, &length, &isNone, &error)
                try check(code, error)
                guard isNone == 0, let data else { return nil }
                return Data(bytesNoCopy: data, count: length, deallocator: .free)
            }
        } catch {
            report("\(error)", context: "chord_sheet_buffer")
            return nil
        }
    }

    /// Stop playback and the session thread, save the config, release audio;
    /// then end ``events``. The interpreter keeps running (it is never
    /// finalized), but a process starts one session only.
    public func shutdown() async {
        do {
            try await runtime.onBridge { [self] in
                guard let handle else { return }
                self.handle = nil
                var error: UnsafeMutablePointer<CChar>?
                let code = cn_handle_shutdown(handle, &error)
                cn_handle_release(handle)
                try check(code, error)
            }
        } catch {
            report("Shutting the session down failed: \(error)", context: "bridge")
        }
        EventSinkRegistry.install(nil)
        continuation.finish()
    }

    /// Put an `UnexpectedError` on ``events`` from the Swift side.
    private func report(_ message: String, context: String) {
        let event = UnexpectedError(context: context, message: message)
        let json = (try? BridgeJSON.encoder.encode(event)).map { String(decoding: $0, as: UTF8.self) }
        continuation.yield((typeName: "UnexpectedError", json: json ?? "{}"))
    }
}

/// Where `_cnbridge.emit` delivers: the running session's stream.
enum EventSinkRegistry {
    private static let lock = NSLock()
    // Kept for the process: a Python thread may be inside emit when it changes.
    nonisolated(unsafe) private static var boxes: [Unmanaged<SinkBox>] = []

    static func install(_ continuation: AsyncStream<Session.Event>.Continuation?) {
        lock.withLock {
            guard let continuation else {
                cn_set_event_sink(nil, nil)
                return
            }
            let box = Unmanaged.passRetained(SinkBox(continuation))
            boxes.append(box)
            cn_set_event_sink(emitEvent, box.toOpaque())
        }
    }
}

final class SinkBox: @unchecked Sendable {
    let continuation: AsyncStream<Session.Event>.Continuation

    init(_ continuation: AsyncStream<Session.Event>.Continuation) {
        self.continuation = continuation
    }
}

private let emitEvent: CNEmitFn = { context, typeName, typeLength, json, jsonLength in
    guard let context, let typeName, let json else { return }
    let box = Unmanaged<SinkBox>.fromOpaque(context).takeUnretainedValue()
    let type = String(decoding: UnsafeRawBufferPointer(start: typeName, count: typeLength), as: UTF8.self)
    let payload = String(decoding: UnsafeRawBufferPointer(start: json, count: jsonLength), as: UTF8.self)
    box.continuation.yield((typeName: type, json: payload))
}
