import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's ChordSheetControllerTest as behaviour: one fetch per distinct
/// request after the height settles, no song clears the sheet, a hidden
/// sheet fetches nothing, a newer version shows a message, loading lasts
/// from the request until its buffer is shown, stale replies are dropped.
@MainActor
final class ChordSheetLoaderTests: XCTestCase {
    /// Records each fetch's height and answers with `reply`.
    private final class Source: @unchecked Sendable {
        private let lock = NSLock()
        private var heights: [Double] = []
        private var answer: Data?

        init(_ answer: Data?) {
            self.answer = answer
        }

        var fetches: [Double] { lock.withLock { heights } }

        func reply(_ data: Data?) {
            lock.withLock { answer = data }
        }

        func fetch(_ height: Double) -> Data? {
            lock.withLock {
                heights.append(height)
                return answer
            }
        }
    }

    private func request(_ revision: Int = 1, view: String = "staff", height: Int = 130) -> SheetRequest {
        SheetRequest(songRevision: revision, viewId: view, zoom: 1, height: height)
    }

    private func loader(_ source: Source) -> ChordSheetLoader {
        ChordSheetLoader(settle: .milliseconds(30)) { height in source.fetch(height) }
    }

    func testOneFetchPerDistinctRequestAfterTheHeightSettles() async throws {
        let source = Source(try SheetBufferTests.bytes("multikey_staff"))
        let loader = loader(source)
        loader.follow(request(height: 100))
        loader.follow(request(height: 130))  // a split drag: only the last height
        await loader.settled()
        XCTAssertEqual(source.fetches, [130])
        XCTAssertEqual(loader.state.sheet?.buffer.viewId, "staff")
        XCTAssertEqual(loader.state.loaded, request(height: 130))

        loader.follow(request(height: 130))  // the same request (a playhead move)
        await loader.settled()
        loader.follow(request(2, height: 130))  // the song changed
        await loader.settled()
        XCTAssertEqual(source.fetches, [130, 130])
        XCTAssertEqual(loader.fetchCount, 2)
    }

    func testNoSongClearsTheSheetAndAHiddenSheetFetchesNothing() async throws {
        let source = Source(try SheetBufferTests.bytes("multikey_staff"))
        let loader = loader(source)
        loader.follow(request())
        await loader.settled()
        XCTAssertNotNil(loader.state.sheet)
        source.reply(nil)
        loader.follow(request(2))
        await loader.settled()
        XCTAssertNil(loader.state.sheet)
        XCTAssertNil(loader.state.failure)
        loader.follow(nil)
        await loader.settled()
        XCTAssertEqual(source.fetches.count, 2)
        XCTAssertFalse(loader.state.loading)
    }

    func testAnUnsupportedVersionShowsAMessageInsteadOfDrawing() async throws {
        var bytes = try SheetBufferTests.bytes("multikey_staff")
        bytes[4] = 9
        let loader = loader(Source(bytes))
        loader.follow(request())
        await loader.settled()
        XCTAssertNil(loader.state.sheet)
        XCTAssertEqual(loader.state.failure, ChordSheetLoad.newerVersionMessage)
        XCTAssertFalse(loader.state.loading)
    }

    func testAMalformedBufferSaysItCouldNotBeDrawn() async {
        let loader = loader(Source(Data("CNSB".utf8)))
        loader.follow(request())
        await loader.settled()
        XCTAssertEqual(loader.state.failure, ChordSheetLoad.malformedMessage)
    }

    func testLoadingIsOnFromTheRequestUntilItsBufferIsShown() async throws {
        let source = Source(try SheetBufferTests.bytes("multikey_staff"))
        let loader = loader(source)
        var seen: [Bool] = []
        loader.onChange = { seen.append($0.loading) }
        XCTAssertFalse(loader.state.loading)
        loader.follow(request())
        XCTAssertTrue(loader.state.loading)  // inside the settle delay
        await loader.settled()
        XCTAssertFalse(loader.state.loading)
        loader.follow(request(2))  // an edit
        XCTAssertTrue(loader.state.loading)
        XCTAssertNotNil(loader.state.sheet, "the old sheet stays until the new one is ready")
        await loader.settled()
        XCTAssertFalse(loader.state.loading)
        loader.follow(nil)  // hidden: nothing is coming
        XCTAssertFalse(loader.state.loading)
        XCTAssertEqual(seen, [true, false, true, false, false])
    }

    func testAReplyToAnOlderRequestIsDropped() throws {
        var load = ChordSheetLoad()
        XCTAssertTrue(load.request(request(1)))
        XCTAssertTrue(load.request(request(2)))
        let old = PreparedSheet(try SheetBuffer.decode(try SheetBufferTests.bytes("multikey_staff")))
        XCTAssertFalse(load.finish(request(1), .sheet(old)))
        XCTAssertNil(load.sheet)
        XCTAssertTrue(load.loading)
        XCTAssertTrue(load.finish(request(2), .sheet(old)))
        XCTAssertEqual(load.sheet?.id, old.id)
        XCTAssertFalse(load.request(request(2)), "the same request needs no fetch")
        XCTAssertFalse(load.request(nil), "hidden needs no fetch")
        XCTAssertFalse(load.loading)
    }

    func testEachPreparedSheetHasItsOwnIdentity() throws {
        let buffer = try SheetBuffer.decode(try SheetBufferTests.bytes("multikey_staff"))
        XCTAssertNotEqual(PreparedSheet(buffer).id, PreparedSheet(buffer).id)
        XCTAssertTrue(PreparedSheet(try SheetBuffer.decode(try SheetBufferTests.bytes("american_staff")))
            .imageKeys.contains { $0.hasPrefix("clef_treble:") })
    }
}
