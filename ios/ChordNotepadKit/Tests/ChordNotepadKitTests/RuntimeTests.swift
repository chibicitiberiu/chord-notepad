import Foundation
import XCTest

@testable import ChordNotepadKit

/// The interpreter and the _cnbridge plumbing, with a tiny test module
/// (python/cn_kit_testmod.py) instead of the core.
final class RuntimeTests: XCTestCase {
    func testTheInterpreterStartsIsolatedInUTF8ModeOnTheBridgeThread() async throws {
        let runtime = try await TestPython.runtime()
        let facts = try jsonObject(try await runtime.call("cn_kit_testmod", "runtime_facts"))
        XCTAssertEqual(facts["utf8_mode"] as? Int, 1)
        XCTAssertEqual(facts["isolated"] as? Int, 1)
        XCTAssertEqual(facts["filesystem_encoding"] as? String, "utf-8")
        XCTAssertEqual(facts["version"] as? [Int], [3, 14])
        // Python started on the bridge thread, so that is its main thread.
        XCTAssertEqual(facts["is_main_thread"] as? Bool, true)
        let path = try XCTUnwrap(facts["path"] as? [String])
        XCTAssertEqual(Array(path.prefix(TestPython.configuration.searchPaths.count)),
                       TestPython.configuration.searchPaths)
        XCTAssertEqual(path[TestPython.configuration.searchPaths.count], PythonRuntime.gluePath)
        XCTAssertTrue(path.contains { $0.hasSuffix("/lib-dynload") }, "CPython's own path follows: \(path)")
    }

    func testTheSameConfigurationReturnsTheRunningRuntime() async throws {
        let first = try await TestPython.runtime()
        let second = try await TestPython.runtime()
        XCTAssertTrue(first === second)
    }

    func testAnotherConfigurationIsRefused() async throws {
        _ = try await TestPython.runtime()
        do {
            _ = try await PythonRuntime.start(PythonRuntime.Configuration(searchPaths: ["/elsewhere"]))
            XCTFail("a second interpreter configuration started")
        } catch let error as PythonError {
            XCTAssertTrue(error.message.contains("one interpreter per process"), error.message)
        }
    }

    func testAPythonErrorComesBackWithItsTraceback() async throws {
        let runtime = try await TestPython.runtime()
        do {
            _ = try await runtime.call("cn_kit_testmod", "fail", ["boom ♯"])
            XCTFail("no error")
        } catch let error as PythonError {
            XCTAssertTrue(error.message.contains("Traceback"), error.message)
            XCTAssertTrue(error.message.contains("ValueError: boom ♯"), error.message)
        }
        do {
            _ = try await runtime.call("no_such_module_here", "f")
            XCTFail("no error")
        } catch let error as PythonError {
            XCTAssertTrue(error.message.contains("ModuleNotFoundError"), error.message)
        }
    }

    func testEventsFromPythonThreadsReachTheStreamInOrderPerThread() async throws {
        let runtime = try await TestPython.runtime()
        let (stream, continuation) = AsyncStream.makeStream(of: Session.Event.self)
        EventSinkRegistry.install(continuation)
        defer { EventSinkRegistry.install(nil) }
        _ = try await runtime.call("cn_kit_testmod", "emit_from_threads", ["50"])
        continuation.finish()
        var next = ["a": 0, "b": 0]
        for await event in stream {
            XCTAssertEqual(event.typeName, "Ping")
            let payload = try jsonObject(event.json)
            let thread = try XCTUnwrap(payload["thread"] as? String)
            XCTAssertEqual(payload["i"] as? Int, next[thread])
            XCTAssertEqual(payload["text"] as? String, "Ré ♯ 😀")
            next[thread]! += 1
        }
        XCTAssertEqual(next, ["a": 50, "b": 50])
    }

    func testEveryStoreCallReachesTheSwiftStore() async throws {
        let runtime = try await TestPython.runtime()
        let store = MemoryStore()
        StoreRegistry.install(store)
        defer { StoreRegistry.install(nil) }
        let results = try jsonObject(try await runtime.call("cn_kit_testmod", "store_round_trip", ["song.txt"]))
        func result(_ key: String) -> [String: Any] { results[key] as? [String: Any] ?? [:] }

        XCTAssertNotNil(result("write")["ok"])
        // Written, then renamed by the "rename" call further down.
        XCTAssertEqual(store.contents("renamed/New.txt"), Data("Am  G\nRé 😀".utf8))
        XCTAssertEqual(result("read")["ok_bytes"] as? [Int], Array("Am  G\nRé 😀".utf8).map(Int.init))
        // The message is the exception's only argument: callback_store shows str(exc).
        XCTAssertEqual(result("read_missing")["error"] as? String, "StoreError")
        XCTAssertEqual(result("read_missing")["message"] as? String, "File not found: missing")
        XCTAssertEqual(store.copies.map(\.path), ["/tmp/export.wav"])
        XCTAssertEqual(result("available")["ok"] as? Bool, true)
        XCTAssertEqual(result("available_missing")["ok"] as? Bool, false)
        XCTAssertEqual(store.maxRecent, 7)
        let recent = try XCTUnwrap(result("recent")["ok"] as? String)
        XCTAssertEqual(try JSONDecoder().decode([DocumentRef].self, from: Data(recent.utf8)),
                       [DocumentRef(displayName: "Song.txt", id: "song.txt", location: "Files")])
        let described = try XCTUnwrap(result("describe")["ok"] as? String)
        XCTAssertEqual(try JSONDecoder().decode(DocumentRef.self, from: Data(described.utf8)),
                       memoryRef("song.txt"))
        XCTAssertTrue(result("describe_missing")["ok"] is NSNull, "\(result("describe_missing"))")
        let renamed = try XCTUnwrap(result("rename")["ok"] as? String)
        XCTAssertEqual(try JSONDecoder().decode(DocumentRef.self, from: Data(renamed.utf8)).id,
                       "renamed/New.txt")
        XCTAssertEqual(result("rename_refused")["error"] as? String, "RenameUnsupportedError")
        XCTAssertEqual(result("rename_refused")["is_store_error"] as? Bool, true)
        XCTAssertEqual(result("rename_refused")["message"] as? String, "This storage can't rename “locked”.")
        XCTAssertNotNil(result("write_empty")["ok"])
        XCTAssertEqual(result("read_empty")["ok_bytes"] as? [Int], [])
    }

    func testAStoreCallReleasesTheGILWhileSwiftBlocks() async throws {
        let runtime = try await TestPython.runtime()
        let store = MemoryStore(files: ["slow.txt": Data("C".utf8)])
        StoreRegistry.install(store)
        defer { StoreRegistry.install(nil) }
        let result = try jsonObject(
            try await runtime.call("cn_kit_testmod", "gil_released_during_store_call", ["slow.txt"]))
        // 300 ms blocked at 5 ms per tick: the other thread ran throughout.
        XCTAssertGreaterThan(result["ticks_during_call"] as? Int ?? 0, 10)
    }

    func testWithoutAStoreTheCallsRaiseStoreError() async throws {
        let runtime = try await TestPython.runtime()
        StoreRegistry.install(nil)
        let results = try jsonObject(try await runtime.call("cn_kit_testmod", "store_round_trip", ["x"]))
        let read = try XCTUnwrap(results["read"] as? [String: Any])
        XCTAssertEqual(read["error"] as? String, "StoreError")
        XCTAssertEqual(read["message"] as? String, "No document store is registered")
    }
}
