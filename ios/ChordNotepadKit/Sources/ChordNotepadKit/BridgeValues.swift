import Foundation

// The hand-written half of the bridge types; Generated/Bridge.swift has the
// schema's DTOs, enums and command builders.

/// Any JSON value: the schema's `json` (a Python field typed `Any`, such as the
/// voicing form's values) and `respond`'s `any`.
public enum JSONValue: Codable, Sendable, Equatable, Hashable {
    case null
    case bool(Bool)
    case int(Int)
    case double(Double)
    case string(String)
    case array([JSONValue])
    case object([String: JSONValue])

    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            // Before the numbers: Foundation would read true as 1.
            self = .bool(value)
        } else if let value = try? container.decode(Int.self) {
            self = .int(value)
        } else if let value = try? container.decode(Double.self) {
            self = .double(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            self = .object(try container.decode([String: JSONValue].self))
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .null: try container.encodeNil()
        case .bool(let value): try container.encode(value)
        case .int(let value): try container.encode(value)
        case .double(let value): try container.encode(value)
        case .string(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        }
    }

    /// The member `key` of an object, else nil.
    public subscript(key: String) -> JSONValue? {
        if case .object(let members) = self { return members[key] }
        return nil
    }

    /// The string, else nil.
    public var stringValue: String? {
        if case .string(let value) = self { return value }
        return nil
    }
}

/// A text range in code points: `[start, end]` on the wire.
public struct Selection: Codable, Sendable, Equatable, Hashable {
    public var start: Int
    public var end: Int

    public init(start: Int, end: Int) {
        self.start = start
        self.end = end
    }

    public init(from decoder: Decoder) throws {
        var container = try decoder.unkeyedContainer()
        start = try container.decode(Int.self)
        end = try container.decode(Int.self)
        if !container.isAtEnd {
            throw DecodingError.dataCorruptedError(
                in: container, debugDescription: "A selection is [start, end]")
        }
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.unkeyedContainer()
        try container.encode(start)
        try container.encode(end)
    }
}

/// A session output that doesn't decode.
public enum BridgeDecodeError: Error, Equatable, CustomStringConvertible {
    /// No DTO has this wire type name (a newer core?).
    case unknownType(String)
    /// The payload doesn't match the type: a missing field, a wrong type.
    case badPayload(String, String)

    public var description: String {
        switch self {
        case .unknownType(let name): return "Unknown session output type: \(name)"
        case .badPayload(let name, let reason): return "Can't decode \(name): \(reason)"
        }
    }
}

/// The JSON coders the bridge uses: keys exactly as declared (no conversion
/// strategy), sorted on output so command JSON is stable.
public enum BridgeJSON {
    public static var decoder: JSONDecoder { JSONDecoder() }

    public static var encoder: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return encoder
    }
}

/// One command for ``Session/submit(_:)``: a command name and its arguments.
/// Build it with the typed builders in Generated/Bridge.swift, e.g.
/// `.setText(clientToken: 3, text: "C G")`.
public struct BridgeCommand: Sendable {
    /// The command's wire name (an `AppSession` method or a host command).
    public let name: String
    private let args: any Encodable & Sendable

    init(name: String, args: any Encodable & Sendable) {
        self.name = name
        self.args = args
    }

    /// A command from a name and its arguments already as a JSON object.
    public init(name: String, argsJSON: String) {
        self.init(name: name, args: RawJSON(text: argsJSON))
    }

    /// The arguments as a JSON object.
    ///
    /// - Throws: `EncodingError` for a value JSON can't hold (a non-finite
    ///   Double); ``Session`` reports it as an `UnexpectedError`.
    public func argsJSON() throws -> String {
        if let raw = args as? RawJSON { return raw.text }
        let data = try BridgeJSON.encoder.encode(args)
        return String(decoding: data, as: UTF8.self)
    }
}

/// The arguments of a command without parameters: `{}`.
struct EmptyArgs: Encodable, Sendable {}

/// `respond {request_id, value}` with a typed value.
struct RespondArgs<Value: Encodable & Sendable>: Encodable, Sendable {
    let requestId: Int
    let value: Value

    enum CodingKeys: String, CodingKey {
        case requestId = "request_id"
        case value
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(requestId, forKey: .requestId)
        try container.encode(value, forKey: .value)
    }
}

/// Arguments given as JSON text.
private struct RawJSON: Encodable, Sendable {
    let text: String

    func encode(to encoder: Encoder) throws {
        let value = try JSONDecoder().decode(JSONValue.self, from: Data(text.utf8))
        try value.encode(to: encoder)
    }
}
