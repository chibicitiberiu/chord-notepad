import Foundation
import XCTest

@testable import ChordNotepadKit

/// ``PlainFileAccess`` with the failures a device has: files the app may not
/// touch, iCloud files not downloaded, storage that can't rename, bookmarks
/// that went stale or follow a moved file. Keyed by file name.
final class TestAccess: DocumentFileAccess, @unchecked Sendable {
    private let lock = NSLock()
    private var _denied: Set<String> = []
    private var _notDownloaded: Set<String> = []
    private var _noRename: Set<String> = []
    private var _stale: Set<String> = []
    private var _moved: [String: URL] = [:]
    private var _sizes: [String: Int] = [:]
    private var _noBookmark: Set<String> = []
    private var _bookmarksMade = 0

    func deny(_ name: String) { lock.withLock { _ = _denied.insert(name) } }
    func notDownloaded(_ name: String) { lock.withLock { _ = _notDownloaded.insert(name) } }
    func noRename(_ name: String) { lock.withLock { _ = _noRename.insert(name) } }
    func makeStale(_ name: String) { lock.withLock { _ = _stale.insert(name) } }
    /// The bookmark of `name` now resolves to `url` (the file was moved).
    func move(_ name: String, to url: URL) { lock.withLock { _moved[name] = url } }
    func size(_ name: String, _ size: Int?) { lock.withLock { _sizes[name] = size } }
    /// No bookmark can be made for `name` (the rename took the app's access).
    func refuseBookmark(_ name: String) { lock.withLock { _ = _noBookmark.insert(name) } }
    var bookmarksMade: Int { lock.withLock { _bookmarksMade } }

    private func check(_ url: URL) throws {
        let name = url.lastPathComponent
        try lock.withLock {
            if _denied.contains(name) { throw FileAccessError.permissionDenied }
            if _notDownloaded.contains(name) { throw FileAccessError.notDownloaded }
        }
    }

    func makeBookmark(for url: URL) throws -> Data {
        try lock.withLock {
            if _noBookmark.contains(url.lastPathComponent) { throw FileAccessError.permissionDenied }
            _bookmarksMade += 1
        }
        return try PlainFileAccess().makeBookmark(for: url)
    }

    func resolveBookmark(_ bookmark: Data) throws -> (url: URL, stale: Bool) {
        let path = String(decoding: bookmark, as: UTF8.self).replacingOccurrences(of: "path:", with: "")
        let name = (path as NSString).lastPathComponent
        if let moved = lock.withLock({ _moved[name] }) {
            guard FileManager.default.fileExists(atPath: moved.path) else { throw FileAccessError.notFound }
            return (moved, true)
        }
        let (url, _) = try PlainFileAccess().resolveBookmark(bookmark)
        let stale = lock.withLock { _stale.remove(name) != nil }
        return (url, stale)
    }

    func facts(_ url: URL) -> FileFacts? {
        guard var facts = PlainFileAccess().facts(url) else { return nil }
        if let size = lock.withLock({ _sizes[url.lastPathComponent] }) { facts.size = size }
        return facts
    }

    func read(_ url: URL, limit: Int) throws -> Data? {
        try check(url)
        return try PlainFileAccess().read(url, limit: limit)
    }

    func write(_ url: URL, data: Data) throws {
        try check(url)
        try PlainFileAccess().write(url, data: data)
    }

    func copy(from source: URL, to url: URL) throws {
        try check(url)
        try PlainFileAccess().copy(from: source, to: url)
    }

    func rename(_ url: URL, to name: String) throws -> URL {
        if lock.withLock({ _noRename.contains(url.lastPathComponent) }) { throw FileAccessError.unsupported }
        return try PlainFileAccess().rename(url, to: name)
    }
}

/// Android's `SafDocumentStoreTest` as behaviour, on real files in a
/// temporary folder (``PlainFileAccess``'s path bookmarks), plus what only
/// iOS has: bookmarks (stale, moved, picked twice), the shipped songs,
/// exports waiting for the export picker, a relaunch.
final class FileDocumentStoreTests: XCTestCase {
    private var root: URL!
    private var docs: URL!
    private var appDir: URL!
    private var bundleDir: URL!
    private var access: TestAccess!
    private var store: FileDocumentStore!

    override func setUpWithError() throws {
        root = FileManager.default.temporaryDirectory.appendingPathComponent("cn-store-\(UUID().uuidString)")
        docs = root.appendingPathComponent("docs")
        appDir = root.appendingPathComponent("support")
        bundleDir = root.appendingPathComponent("bundle")
        for dir in [docs!, appDir!, bundleDir!] {
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        }
        try Data("C G\n".utf8).write(to: bundleDir.appendingPathComponent("01_quick_start.txt"))
        access = TestAccess()
        store = makeStore(maxRecent: 3)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: root)
    }

    private func makeStore(maxRecent: Int = 3) -> FileDocumentStore {
        let bundleDir = self.bundleDir!
        return FileDocumentStore(
            access: access, appDir: appDir, recentFile: appDir.appendingPathComponent("recent-documents.json"),
            bookmarksFile: appDir.appendingPathComponent("bookmarks.json"),
            bundled: { name in
                let url = bundleDir.appendingPathComponent(name)
                return FileManager.default.fileExists(atPath: url.path) ? url : nil
            }, maxRecent: maxRecent)
    }

    /// A file in the documents folder, adopted as if picked.
    @discardableResult
    private func picked(_ name: String, _ text: String = "C G\n") throws -> DocumentRef {
        let url = docs.appendingPathComponent(name)
        try Data(text.utf8).write(to: url)
        return try store.adopt(url)
    }

    private func ids(_ refs: [DocumentRef]) -> [String] { refs.map(\.id) }

    private func expectError(_ fragment: String, file: StaticString = #filePath, line: UInt = #line,
                             _ body: () throws -> Void) {
        do {
            try body()
            XCTFail("expected a DocumentStoreError containing '\(fragment)'", file: file, line: line)
        } catch let error as DocumentStoreError {
            XCTAssertTrue(error.description.contains(fragment), "'\(error.description)' should contain '\(fragment)'",
                          file: file, line: line)
        } catch {
            XCTFail("expected a DocumentStoreError, got \(error)", file: file, line: line)
        }
    }

    // MARK: - Ids

    func testIdsRoundTripAndRefuseEscapes() {
        for id in ["bundle:01_quick_start.txt", "app:examples/a b.txt", "app:exports/X/song.mid", "bookmark:ABC-1"] {
            XCTAssertEqual(DocumentId(id)?.string, id)
        }
        for id in ["", "song.txt", "bundle:", "bundle:a/b.txt", "app:../secret", "app:examples/../../x", "app:",
                   "app:examples//a", "bookmark:", "bookmark:a/b", "file:///tmp/a.txt", "content://d/1"] {
            XCTAssertNil(DocumentId(id), id)
        }
    }

    // MARK: - Reading

    func testReadsTheBytesAsTheyAreLeavingDecodingToPython() throws {
        let latin1 = Data([0xC9, 0x74, 0xE9, 0x0D, 0x0A, 0x41])
        let url = docs.appendingPathComponent("a.txt")
        try latin1.write(to: url)
        let ref = try store.adopt(url)
        XCTAssertEqual(try store.readBytes(id: ref.id), latin1)
    }

    func testReadErrorsUseTheDesktopWording() throws {
        expectError("File not found: the document") { _ = try store.readBytes(id: "bookmark:nobody") }
        expectError("File not found: gone.txt") { _ = try store.readBytes(id: "app:examples/gone.txt") }
        let locked = try picked("locked.txt")
        access.deny("locked.txt")
        expectError("Permission denied: locked.txt (docs)") { _ = try store.readBytes(id: locked.id) }
    }

    func testARecentFileThatHasGoneIsNamedFromItsEntryAndLeavesTheList() throws {
        let other = try picked("other.txt")
        let gone = try picked("fntest.txt")
        try store.addRecent(other)
        try store.addRecent(gone)
        try FileManager.default.removeItem(at: docs.appendingPathComponent("fntest.txt"))
        expectError("File not found: fntest.txt (docs)") { _ = try store.readBytes(id: gone.id) }
        XCTAssertEqual(ids(try store.recent()), [other.id])
        XCTAssertNil(store.bookmarks[String(gone.id.dropFirst("bookmark:".count))], "its bookmark went too")
    }

    func testReadsStopAt5MBByTheFileSizeOrByTheBytesRead() throws {
        let limit = FileDocumentStore.maxReadBytes
        let big = try picked("big.txt")
        access.size("big.txt", limit + 1)
        expectError("File too large to open (over 5 MB): big.txt (docs)") { _ = try store.readBytes(id: big.id) }
        // A size that is missing or wrong: the read itself stops.
        let huge = try picked("huge.txt", String(repeating: "a", count: limit + 1))
        expectError("File too large to open (over 5 MB): huge.txt (docs)") { _ = try store.readBytes(id: huge.id) }
        access.size("huge.txt", 10)
        expectError("File too large") { _ = try store.readBytes(id: huge.id) }
        let fits = try picked("fits.txt", String(repeating: "a", count: limit))
        XCTAssertEqual(try store.readBytes(id: fits.id).count, limit)
    }

    func testAFileNotDownloadedSaysSo() throws {
        let cloud = try picked("cloud.txt")
        access.notDownloaded("cloud.txt")
        expectError("File not downloaded yet (open it in the Files app to download it, then try again): cloud.txt (docs)") {
            _ = try store.readBytes(id: cloud.id)
        }
        try store.addRecent(cloud)
        XCTAssertEqual(ids(try store.recent()), [cloud.id], "still there: it can be downloaded")
    }

    // MARK: - Bookmarks

    func testPickingTheSameFileAgainGivesTheSameId() throws {
        let first = try picked("song.txt")
        let again = try store.adopt(docs.appendingPathComponent("song.txt"))
        XCTAssertEqual(first, again)
        XCTAssertEqual(first.displayName, "song.txt")
        XCTAssertEqual(first.location, "song.txt (docs)")
        XCTAssertTrue(first.id.hasPrefix("bookmark:"))
        XCTAssertEqual(store.bookmarks.entries.count, 1)
        let other = try picked("other.txt")
        XCTAssertNotEqual(other.id, first.id)
    }

    func testAStaleBookmarkIsMadeAgainUnderTheSameId() throws {
        let ref = try picked("song.txt")
        let made = access.bookmarksMade
        access.makeStale("song.txt")
        XCTAssertEqual(try store.readBytes(id: ref.id), Data("C G\n".utf8))
        XCTAssertEqual(access.bookmarksMade, made + 1, "made again")
        XCTAssertEqual(try store.describe(id: ref.id)?.id, ref.id)
    }

    func testABookmarkFollowsAMovedFile() throws {
        let ref = try picked("song.txt")
        try store.addRecent(ref)
        let elsewhere = root.appendingPathComponent("moved")
        try FileManager.default.createDirectory(at: elsewhere, withIntermediateDirectories: true)
        let moved = elsewhere.appendingPathComponent("song.txt")
        try FileManager.default.moveItem(at: docs.appendingPathComponent("song.txt"), to: moved)
        access.move("song.txt", to: moved)
        XCTAssertEqual(try store.readBytes(id: ref.id), Data("C G\n".utf8))
        XCTAssertEqual(try store.describe(id: ref.id)?.location, "song.txt (moved)")
        XCTAssertEqual(store.bookmarks.entries.values.first?.path, moved.standardizedFileURL.path)
        XCTAssertEqual(ids(try store.recent()), [ref.id], "the same id in Recent")
    }

    func testARelaunchFindsTheRecentListAndItsBookmarks() throws {
        let a = try picked("a.txt", "A\n")
        let b = try picked("b.txt", "B\n")
        try store.addRecent(a)
        try store.addRecent(b)
        let relaunched = makeStore()
        XCTAssertEqual(ids(try relaunched.recent()), [b.id, a.id])
        XCTAssertEqual(try relaunched.readBytes(id: a.id), Data("A\n".utf8))
        XCTAssertEqual(try relaunched.describe(id: b.id), b)
    }

    func testCorruptListsReadAsEmpty() throws {
        try Data("{not json".utf8).write(to: appDir.appendingPathComponent("recent-documents.json"))
        try Data("[1, 2".utf8).write(to: appDir.appendingPathComponent("bookmarks.json"))
        let fresh = makeStore()
        XCTAssertEqual(try fresh.recent(), [])
        XCTAssertEqual(fresh.bookmarks.entries.count, 0)
    }

    // MARK: - Writing

    func testWritesReplaceTheOldContentInPlace() throws {
        let ref = try picked("a.txt", "a much longer old text")
        try store.writeBytes(id: ref.id, data: Data("G 😀".utf8))
        XCTAssertEqual(try String(contentsOf: docs.appendingPathComponent("a.txt"), encoding: .utf8), "G 😀")
        try store.writeBytes(id: ref.id, data: Data([1, 2]))
        XCTAssertEqual(FileManager.default.contents(atPath: docs.appendingPathComponent("a.txt").path), Data([1, 2]))
        access.deny("a.txt")
        expectError("Permission denied: a.txt (docs)") { try store.writeBytes(id: ref.id, data: Data([1])) }
        expectError("File not found: the document") { try store.writeBytes(id: "bookmark:gone", data: Data([1])) }
    }

    func testCopyFromFileStreamsALocalFileIntoTheDocumentReplacingIt() throws {
        let ref = try picked("song.wav", "an older and longer export, longer than the new one is not")
        let local = root.appendingPathComponent("audio-export-1.wav")
        let data = Data((0..<700_000).map { UInt8($0 % 251) })
        try data.write(to: local)
        try store.copyFromFile(id: ref.id, path: local.path)
        XCTAssertEqual(FileManager.default.contents(atPath: docs.appendingPathComponent("song.wav").path), data)
        access.deny("song.wav")
        expectError("Permission denied") { try store.copyFromFile(id: ref.id, path: local.path) }
        expectError("File not found") { try store.copyFromFile(id: "bookmark:gone", path: local.path) }
        let other = try picked("other.wav")
        expectError("Failed to write file") {
            try store.copyFromFile(id: other.id, path: root.appendingPathComponent("missing.wav").path)
        }
    }

    // MARK: - Shipped songs and example copies

    func testAShippedSongReadsButIsNeverWrittenOrRenamed() throws {
        let id = "bundle:01_quick_start.txt"
        XCTAssertEqual(try store.readBytes(id: id), Data("C G\n".utf8))
        XCTAssertEqual(try store.describe(id: id),
                       DocumentRef(displayName: "01_quick_start.txt", id: id, location: "01_quick_start.txt (Examples)"))
        expectError("Permission denied: 01_quick_start.txt (Examples) comes with the app and can't be changed. Use Save As.") {
            try store.writeBytes(id: id, data: Data())
        }
        XCTAssertThrowsError(try store.rename(id: id, displayName: "x.txt")) {
            XCTAssertEqual($0 as? DocumentStoreError,
                           .renameUnsupported("“01_quick_start.txt” comes with the app and can't be renamed."))
        }
        XCTAssertFalse(store.isAvailable(id: "bundle:nothing.txt"))
    }

    func testAnExampleCopyStaysInTheRecentListUntilItsFileIsDeleted() throws {
        let library = ExampleLibrary(list: { ["x.txt"] }, read: { _ in Data("song".utf8) },
                                     dir: appDir.appendingPathComponent(ExampleLibrary.folder))
        let ref = try store.exampleCopy(library, name: "x.txt", skipId: nil)
        XCTAssertEqual(ref, DocumentRef(displayName: "x.txt", id: "app:examples/x.txt", location: "x.txt (Examples)"))
        try store.addRecent(ref)
        XCTAssertEqual(ids(try store.recent()), [ref.id])
        try store.writeBytes(id: ref.id, data: Data("edited".utf8))
        XCTAssertEqual(try store.readBytes(id: ref.id), Data("edited".utf8))
        try FileManager.default.removeItem(at: library.fileFor("x.txt"))
        XCTAssertEqual(try store.recent(), [])
    }

    func testAnExampleCopyRenamesInItsFolderAndRefusesATakenName() throws {
        let library = ExampleLibrary(list: { ["x.txt", "y.txt"] }, read: { Data($0.utf8) },
                                     dir: appDir.appendingPathComponent(ExampleLibrary.folder))
        let x = try store.exampleCopy(library, name: "x.txt", skipId: nil)
        _ = try store.exampleCopy(library, name: "y.txt", skipId: nil)
        try store.addRecent(x)
        let renamed = try store.rename(id: x.id, displayName: "Tune.txt")
        XCTAssertEqual(renamed, DocumentRef(displayName: "Tune.txt", id: "app:examples/Tune.txt",
                                            location: "Tune.txt (Examples)"))
        XCTAssertEqual(try store.readBytes(id: renamed.id), Data("x.txt".utf8))
        XCTAssertEqual(ids(try store.recent()), [renamed.id])
        expectError("Couldn't rename to y.txt: a file with that name is already there.") {
            _ = try store.rename(id: renamed.id, displayName: "y.txt")
        }
    }

    // MARK: - Rename

    func testRenameKeepsTheIdRenamesTheFileAndMovesTheRecentEntry() throws {
        let a = try picked("a.txt", "C G")
        let b = try picked("b.txt")
        try store.addRecent(b)
        try store.addRecent(a)
        let renamed = try store.rename(id: a.id, displayName: "Tune.txt")
        XCTAssertEqual(renamed, DocumentRef(displayName: "Tune.txt", id: a.id, location: "Tune.txt (docs)"))
        XCTAssertEqual(try String(contentsOf: docs.appendingPathComponent("Tune.txt"), encoding: .utf8), "C G")
        XCTAssertFalse(FileManager.default.fileExists(atPath: docs.appendingPathComponent("a.txt").path))
        XCTAssertEqual(try store.recent(), [renamed, b])
        XCTAssertEqual(try store.readBytes(id: a.id), Data("C G".utf8), "the bookmark follows the new name")
        XCTAssertEqual(try makeStore().describe(id: a.id), renamed, "and is saved")
    }

    func testRenameFailures() throws {
        let a = try picked("a.txt")
        _ = try picked("b.txt")
        let c = try picked("c.txt")
        access.noRename("c.txt")
        XCTAssertThrowsError(try store.rename(id: c.id, displayName: "x.txt")) {
            XCTAssertEqual($0 as? DocumentStoreError,
                           .renameUnsupported("c.txt (docs) is stored where Chord Notepad can't rename it."))
        }
        expectError("Couldn't rename to b.txt: a file with that name is already there.") {
            _ = try store.rename(id: a.id, displayName: "b.txt")
        }
        expectError("File not found: the document") { _ = try store.rename(id: "bookmark:gone", displayName: "x.txt") }
        let export = try store.prepareExport(named: "song.mid")
        XCTAssertThrowsError(try store.rename(id: export.id, displayName: "x.mid")) {
            guard case .renameUnsupported? = $0 as? DocumentStoreError else { return XCTFail("\($0)") }
        }
    }

    func testARenameThatCostsTheAccessSaysSoAndKeepsNothingUnreadable() throws {
        let a = try picked("a.txt")
        try store.addRecent(a)
        access.refuseBookmark("Renamed.txt")
        expectError("Renamed to Renamed.txt, but Chord Notepad can't reach the file any more. Open it again (Open…)") {
            _ = try store.rename(id: a.id, displayName: "Renamed.txt")
        }
    }

    // MARK: - The recent list

    func testAvailabilityFollowsTheFiles() throws {
        let a = try picked("a.txt")
        XCTAssertTrue(store.isAvailable(id: a.id))
        XCTAssertFalse(store.isAvailable(id: "bookmark:other"))
        XCTAssertFalse(store.isAvailable(id: "song.txt"))
        try FileManager.default.removeItem(at: docs.appendingPathComponent("a.txt"))
        XCTAssertFalse(store.isAvailable(id: a.id))
    }

    func testRecentListNewestFirstNoDuplicatesCappedBookmarksOfDroppedEntriesReleased() throws {
        let refs = try (1...4).map { try picked("\($0).txt") }
        try store.addRecent(refs[0])
        try store.addRecent(refs[1])
        try store.addRecent(refs[0])
        try store.addRecent(refs[2])
        try store.addRecent(refs[3])
        XCTAssertEqual(ids(try store.recent()), [refs[3].id, refs[2].id, refs[0].id])
        let kept = Set(store.bookmarks.entries.keys.map { "bookmark:" + $0 })
        XCTAssertEqual(kept, Set([refs[3].id, refs[2].id, refs[0].id]), "2.txt's bookmark was released")
    }

    func testRecentPrunesDeletedDocumentsForGood() throws {
        let refs = try (1...3).map { try picked("\($0).txt") }
        for ref in refs.reversed() { try store.addRecent(ref) }
        try FileManager.default.removeItem(at: docs.appendingPathComponent("3.txt"))
        XCTAssertEqual(ids(try store.recent()), [refs[0].id, refs[1].id])
        try Data("back".utf8).write(to: docs.appendingPathComponent("3.txt"))
        XCTAssertEqual(ids(try store.recent()), [refs[0].id, refs[1].id], "gone for good")
        XCTAssertEqual(ids(try makeStore().recent()), [refs[0].id, refs[1].id], "and saved")
    }

    func testRecentJSONHasTheDocumentRefShape() throws {
        let a = try picked("a.txt")
        try store.addRecent(a)
        let saved = try XCTUnwrap(FileManager.default.contents(atPath: appDir.appendingPathComponent("recent-documents.json").path))
        let items = try XCTUnwrap(JSONSerialization.jsonObject(with: saved) as? [[String: Any]])
        XCTAssertEqual(Set(items.first?.keys ?? [:].keys), ["id", "display_name", "location"])
    }

    func testASmallerCapTrimsOnTheNextRead() throws {
        for i in 1...3 { try store.addRecent(try picked("\(i).txt")) }
        try store.setMaxRecent(1)
        XCTAssertEqual(try store.recent().map(\.displayName), ["3.txt"])
    }

    func testTheOpenDocumentKeepsItsBookmarkEvenWithAZeroCap() throws {
        let a = try picked("1.txt")
        try store.setMaxRecent(0)
        try store.addRecent(a)
        XCTAssertNotNil(store.bookmarks[String(a.id.dropFirst("bookmark:".count))])
        XCTAssertEqual(try store.recent(), [])
        XCTAssertEqual(try store.readBytes(id: a.id), Data("C G\n".utf8))
    }

    func testDescribeGivesTheRefOrNilWhenUnreachable() throws {
        let a = try picked("a.txt")
        XCTAssertEqual(try store.describe(id: a.id), DocumentRef(displayName: "a.txt", id: a.id, location: "a.txt (docs)"))
        XCTAssertNil(try store.describe(id: "bookmark:gone"))
        XCTAssertNil(try store.describe(id: "nonsense"))
    }

    // MARK: - Exports

    func testAnExportIsAStoreFileThatTellsWhenItIsWritten() throws {
        let written = Recorded()
        store.onExportWritten { id, url in written.add(id, url) }
        let export = try store.prepareExport(named: "Song.mid")
        XCTAssertTrue(export.id.hasPrefix("app:exports/"), export.id)
        XCTAssertTrue(export.id.hasSuffix("/Song.mid"), export.id)
        XCTAssertEqual(export.displayName, "Song.mid")
        XCTAssertEqual(export.location, "Song.mid")
        let file = try XCTUnwrap(store.exportFile(export.id))
        XCTAssertEqual(FileManager.default.contents(atPath: file.path), Data(), "there before the export runs")
        XCTAssertEqual(try store.describe(id: export.id)?.location, "Song.mid")

        try store.writeBytes(id: export.id, data: Data("MThd".utf8))
        XCTAssertEqual(written.all.map(\.0), [export.id])
        XCTAssertEqual(written.all.first?.1.path, file.path)
        XCTAssertEqual(FileManager.default.contents(atPath: file.path), Data("MThd".utf8))

        let audio = try store.prepareExport(named: "Song.wav")
        let local = root.appendingPathComponent("render.wav")
        try Data("RIFF".utf8).write(to: local)
        try store.copyFromFile(id: audio.id, path: local.path)
        XCTAssertEqual(written.all.map(\.0), [export.id, audio.id])

        // A song's write isn't an export.
        let song = try picked("a.txt")
        try store.writeBytes(id: song.id, data: Data("x".utf8))
        XCTAssertEqual(written.all.count, 2)

        store.discardExport(export.id)
        XCTAssertFalse(FileManager.default.fileExists(atPath: file.path))
        XCTAssertFalse(FileManager.default.fileExists(atPath: file.deletingLastPathComponent().path))
        store.discardAllExports()
        XCTAssertFalse(FileManager.default.fileExists(atPath: appDir.appendingPathComponent("exports").path))
        XCTAssertNil(store.exportFile(song.id))
    }

    func testWhereAnExportWasSavedIsNamedAsTheStoreNamesPlaces() throws {
        let folder = root.appendingPathComponent("Downloads", isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let saved = folder.appendingPathComponent("Song 2.wav")
        try Data("RIFF".utf8).write(to: saved)
        XCTAssertEqual(store.savedLocation(saved), "Song 2.wav (Downloads)")
        // A place the app can't read: the name the user gave it.
        XCTAssertEqual(store.savedLocation(folder.appendingPathComponent("gone.wav")), "gone.wav")
    }

    func testAnExportNameThatIsNoFileNameIsReplaced() throws {
        let export = try store.prepareExport(named: "a/b.mid")
        XCTAssertEqual(export.displayName, "Export")
    }

    /// What the export handler was told, safe from any thread.
    private final class Recorded: @unchecked Sendable {
        private let lock = NSLock()
        private var items: [(String, URL)] = []
        func add(_ id: String, _ url: URL) { lock.withLock { items.append((id, url)) } }
        var all: [(String, URL)] { lock.withLock { items } }
    }
}
