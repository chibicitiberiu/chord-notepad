import Foundation

/// What a screen shows, folded from the session's output: the newest state of
/// each kind, the editor's text (rebuilt from `TextEdited`, since no state
/// carries it) and the latest messages.
///
/// The app folds the live ``Session/events`` into one; the preview catalog
/// folds a recorded ``Fixture``. Both go through ``apply(_:)``, so a screen
/// looks the same with or without Python.
public struct SessionSnapshot: Sendable, Equatable {
    /// How many messages ``messages`` keeps.
    public static let messageLimit = 20

    /// The editor's text after every `TextEdited` so far.
    public private(set) var text = ""
    /// `TextEdited.text_revision` of the newest edit.
    public private(set) var textRevision = 0
    public private(set) var editor: EditorState?
    public private(set) var document: DocumentState?
    public private(set) var status: StatusState?
    public private(set) var playback: PlaybackState?
    public private(set) var highlight: HighlightState?
    /// The newest `AudioUnavailable` message, nil once audio played.
    public private(set) var audioProblem: String?
    /// User-facing messages (errors, refused renames, audio problems), oldest first.
    public private(set) var messages: [String] = []
    /// How many outputs were applied.
    public private(set) var outputCount = 0

    public init() {}

    /// Fold one output in.
    public mutating func apply(_ output: SessionOutput) {
        outputCount += 1
        switch output {
        case .textEdited(let edit):
            applyEdit(edit)
        case .editorState(let state):
            editor = state
        case .documentState(let state):
            document = state
        case .statusState(let state):
            status = state
        case .playbackState(let state):
            playback = state
        case .highlightState(let state):
            highlight = state
        case .audioUnavailable(let event):
            audioProblem = event.message
            note(event.message)
        case .userError(let event):
            note(event.title.isEmpty ? event.message : "\(event.title): \(event.message)")
        case .unexpectedError(let event):
            note("Unexpected error (\(event.context ?? "session")): \(event.message)")
        case .renameFailed(let event):
            note(event.reason)
        default:
            break
        }
    }

    /// Fold one output in as it crossed the bridge.
    public mutating func apply(typeName: String, json: String) throws {
        apply(try SessionOutput.decode(typeName: typeName, json: json))
    }

    /// Replace code points `start..<end` of the text, as the core does.
    private mutating func applyEdit(_ edit: TextEdited) {
        let mapper = OffsetMapper(text)
        let units = text.utf16
        let lower = units.index(units.startIndex, offsetBy: mapper.toUTF16(edit.start))
        let upper = units.index(units.startIndex, offsetBy: mapper.toUTF16(max(edit.start, edit.end)))
        text.replaceSubrange(lower..<upper, with: edit.replacement)
        textRevision = edit.textRevision
    }

    private mutating func note(_ message: String) {
        messages.append(message)
        if messages.count > Self.messageLimit {
            messages.removeFirst(messages.count - Self.messageLimit)
        }
    }
}

/// One scene of the session's output recorded by the kit's integration test
/// (`ios/Fixtures/<scene>.json`, docs/IOS.md "Fixtures for the preview
/// catalog"): the newest JSON of every state and the scene's other outputs in
/// order. The preview catalog shows screens from these without Python.
public struct Fixture: Sendable, Equatable {
    public let scene: String
    public let description: String
    /// Every state, then the events in order, as `(typeName, json)`.
    public let outputs: [RecordedOutput]

    /// Read `<scene>.json`.
    public init(contentsOf url: URL) throws {
        let data = try Data(contentsOf: url)
        guard let root = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw FixtureError("\(url.lastPathComponent) isn't a JSON object")
        }
        scene = root["scene"] as? String ?? url.deletingPathExtension().lastPathComponent
        description = root["description"] as? String ?? ""
        var outputs: [RecordedOutput] = []
        // States first (sorted, so a fixture always folds the same way); the
        // events follow, so a TextEdited lands on the empty text it was made for.
        let states = root["states"] as? [String: Any] ?? [:]
        for name in states.keys.sorted() {
            outputs.append(RecordedOutput(typeName: name, json: try Fixture.text(states[name]!)))
        }
        for case let event as [String: Any] in root["events"] as? [Any] ?? [] {
            guard let type = event["type"] as? String, let json = event["json"] else {
                throw FixtureError("\(url.lastPathComponent): an event without type or json")
            }
            outputs.append(RecordedOutput(typeName: type, json: try Fixture.text(json)))
        }
        self.outputs = outputs
    }

    /// The fixture folded into a snapshot.
    public func snapshot() throws -> SessionSnapshot {
        var snapshot = SessionSnapshot()
        for output in outputs {
            try snapshot.apply(typeName: output.typeName, json: output.json)
        }
        return snapshot
    }

    /// Every `*.json` in `directory`, by scene name.
    public static func all(in directory: URL) throws -> [Fixture] {
        try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
            .filter { $0.pathExtension == "json" }
            .sorted { $0.lastPathComponent < $1.lastPathComponent }
            .map { try Fixture(contentsOf: $0) }
    }

    private static func text(_ value: Any) throws -> String {
        let data = try JSONSerialization.data(withJSONObject: value, options: [.sortedKeys, .fragmentsAllowed])
        return String(decoding: data, as: UTF8.self)
    }
}

/// One recorded output: the DTO's Python class name and its JSON.
public struct RecordedOutput: Sendable, Equatable {
    public let typeName: String
    public let json: String

    public init(typeName: String, json: String) {
        self.typeName = typeName
        self.json = json
    }
}

public struct FixtureError: Error, CustomStringConvertible {
    public let description: String

    init(_ description: String) {
        self.description = description
    }
}
