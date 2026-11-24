import Foundation
import XCTest

@testable import ChordNotepadKit

/// The generated bridge types against the schema and against the core's own
/// decoders (the Swift counterpart of Android's BridgeSchemaContractTest).
final class BridgeCodecTests: XCTestCase {
    private var schema: [String: Any] {
        get throws {
            let url = TestPython.repo.appendingPathComponent("android/bridge_schema.json")
            return try jsonObject(String(decoding: try Data(contentsOf: url), as: UTF8.self))
        }
    }

    func testTheGeneratedFactsMatchTheCommittedSchema() throws {
        let schema = try schema
        XCTAssertEqual(BridgeSchema.version, schema["version"] as? Int)
        XCTAssertEqual(BridgeSchema.commandNames, schema["commands"] as? [String])
        let types = try XCTUnwrap(schema["types"] as? [String: [String: Any]])
        XCTAssertEqual(Set(BridgeSchema.fieldNames.keys), Set(types.keys))
        for (name, spec) in types {
            let fields = try XCTUnwrap(spec["fields"] as? [String: String])
            XCTAssertEqual(Set(BridgeSchema.fieldNames[name] ?? []), Set(fields.keys), name)
        }
        XCTAssertEqual(BridgeSchema.enumValues, schema["enums"] as? [String: [String]])
    }

    func testEveryCommandHasABuilder() {
        XCTAssertEqual(Set(commandSamples.map(\.name)), Set(BridgeSchema.commandNames))
    }

    func testEveryBuilderIsAcceptedByTheCoresDecoder() async throws {
        try TestPython.requireCore()
        let runtime = try await TestPython.runtime()
        for command in commandSamples {
            let args = try command.argsJSON()
            let problem = try await runtime.call("cn_kit_testmod", "check_command", [command.name, args])
            XCTAssertEqual(problem, "", "\(command.name) \(args)")
        }
        for (requestType, command) in respondSamples {
            let args = try command.argsJSON()
            let problem = try await runtime.call("cn_kit_testmod", "check_answer", [requestType, args])
            XCTAssertEqual(problem, "", "\(requestType) \(args)")
        }
    }

    func testRequiredNullableArgumentsAreWrittenAsNull() async throws {
        // decode_args rejects a missing key that has no default in AppSession.
        let cases: [(BridgeCommand, String)] = [
            (.restoreDraft(document: nil, modified: false, readOnly: false, text: "C"),
             #"{"document":null,"modified":false,"read_only":false,"text":"C"}"#),
            (.openRecovered(document: nil, name: nil, text: "C"),
             #"{"document":null,"name":null,"text":"C"}"#),
            (.setKey(key: nil), #"{"key":null}"#),
            (.setChordSheetOnScreen(onScreen: nil), #"{"on_screen":null}"#),
            (.transpose(cursor: nil, selection: nil, semitones: 2),
             #"{"cursor":null,"selection":null,"semitones":2}"#),
            (.transpose(cursor: 4, selection: Selection(start: 1, end: 3), semitones: -1),
             #"{"cursor":4,"selection":[1,3],"semitones":-1}"#),
            (.newDocument(), "{}"),
            (.respondToConfirmDiscardRequest(requestId: 3, value: .discard),
             #"{"request_id":3,"value":"discard"}"#),
            (.respondToPickDocumentRequest(requestId: 4, value: nil), #"{"request_id":4,"value":null}"#),
        ]
        for (command, expected) in cases {
            XCTAssertEqual(try command.argsJSON(), expected, command.name)
        }
        try TestPython.requireCore()
        let runtime = try await TestPython.runtime()
        let missing = try await runtime.call("cn_kit_testmod", "check_command", ["set_key", "{}"])
        XCTAssertEqual(missing, "set_key: missing argument 'key'")
    }

    func testValueTypesEncodeEveryFieldEvenNil() throws {
        let ref = DocumentRef(displayName: "Song.txt", id: "file:///Song.txt", location: "Files")
        XCTAssertEqual(String(decoding: try BridgeJSON.encoder.encode(ref), as: UTF8.self),
                       #"{"display_name":"Song.txt","id":"file:///Song.txt","location":"Files"}"#)
        let error = UnexpectedError(context: nil, message: "x")
        XCTAssertEqual(String(decoding: try BridgeJSON.encoder.encode(error), as: UTF8.self),
                       #"{"context":null,"message":"x"}"#)
    }

    func testOutputsDecodeByTheirWireTypeName() throws {
        let highlight = try SessionOutput.decode(typeName: "HighlightState", json: """
            {"text_revision": 3, "client_token": 5, "spans": [{"start": 0, "end": 2, "kind": "chord", "message": ""}],
             "a_field_from_a_newer_core": 1}
            """)
        guard case .highlightState(let state) = highlight else { return XCTFail("\(highlight)") }
        XCTAssertEqual(state.textRevision, 3)
        XCTAssertEqual(state.clientToken, 5)
        XCTAssertEqual(state.spans, [Span(end: 2, kind: .chord, message: "", start: 0)])
        XCTAssertEqual(highlight.typeName, "HighlightState")
        XCTAssertEqual(highlight.kind, .state)

        let startup = try SessionOutput.decode(typeName: "StartupState", json: #"{"screen": "none"}"#)
        XCTAssertEqual(startup, .startupState(StartupState(screen: .noScreen)))

        let closed = try SessionOutput.decode(typeName: "CloseApproved", json: "{}")
        XCTAssertEqual(closed, .closeApproved(CloseApproved()))
        XCTAssertEqual(closed.kind, .event)

        let section = try JSONDecoder().decode(TimelineSection.self, from: Data(
            #"{"label": "verse", "first_bar": 1, "last_bar": 8, "repeat": true}"#.utf8))
        XCTAssertTrue(section.repeat)
    }

    func testAnUnknownTypeOrAMissingFieldIsAnError() {
        XCTAssertThrowsError(try SessionOutput.decode(typeName: "NoSuchState", json: "{}")) { error in
            XCTAssertEqual(error as? BridgeDecodeError, .unknownType("NoSuchState"))
        }
        XCTAssertThrowsError(try SessionOutput.decode(typeName: "HighlightState", json: #"{"spans": []}"#)) {
            guard case .badPayload("HighlightState", _)? = $0 as? BridgeDecodeError else {
                return XCTFail("\($0)")
            }
        }
        XCTAssertThrowsError(try SessionOutput.decode(typeName: "StartupState", json: #"{"screen": "later"}"#))
    }

    func testJSONValueKeepsBoolsIntsDoublesAndNesting() throws {
        let text = #"{"a":true,"b":1,"c":1.5,"d":"x","e":null,"f":[false,2],"g":{"h":"i"}}"#
        let value = try JSONDecoder().decode(JSONValue.self, from: Data(text.utf8))
        XCTAssertEqual(value, .object([
            "a": .bool(true), "b": .int(1), "c": .double(1.5), "d": .string("x"), "e": .null,
            "f": .array([.bool(false), .int(2)]), "g": .object(["h": .string("i")]),
        ]))
        XCTAssertEqual(String(decoding: try BridgeJSON.encoder.encode(value), as: UTF8.self), text)
        XCTAssertEqual(value["g"]?["h"]?.stringValue, "i")
    }

    func testASelectionIsAPairOnTheWire() throws {
        XCTAssertEqual(try JSONDecoder().decode(Selection.self, from: Data("[2,5]".utf8)),
                       Selection(start: 2, end: 5))
        XCTAssertThrowsError(try JSONDecoder().decode(Selection.self, from: Data("[2,5,7]".utf8)))
    }
}
