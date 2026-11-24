import Foundation
import XCTest

@testable import ChordNotepadKit

/// Android's `ExampleLibraryTest`, case for case; ids are `app:examples/<name>`
/// (Android: `file:` URIs), so the name with spaces stays as it is.
final class ExampleLibraryTests: XCTestCase {
    private var dir: URL!
    private var library: ExampleLibrary!

    override func setUpWithError() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("cn-examples-\(UUID().uuidString)")
        dir = root.appendingPathComponent("examples")
        let assets = ["x.txt": Data("one".utf8), "a.txt": Data("two".utf8)]
        library = ExampleLibrary(list: { ["x.txt", "notes.md", "a.txt", "img.png"] },
                                 read: { name in
                                     guard let data = assets[name] else { throw FileAccessError.notFound }
                                     return data
                                 }, dir: dir)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: dir.deletingLastPathComponent())
    }

    private func listing() throws -> Set<String> {
        Set(try FileManager.default.contentsOfDirectory(atPath: dir.path))
    }

    func testNamesKeepsOnlyTxtFilesSorted() {
        XCTAssertEqual(library.names(), ["a.txt", "x.txt"])
    }

    func testTheFirstTapWritesTheCopy() throws {
        let file = try library.copyFor("x.txt", skipId: nil)
        XCTAssertEqual(file, dir.appendingPathComponent("x.txt"))
        XCTAssertEqual(FileManager.default.contents(atPath: file.path), Data("one".utf8))
    }

    func testATapOnAnUnchangedCopyReturnsItAndLeavesItAlone() throws {
        let first = try library.copyFor("x.txt", skipId: nil)
        let old = Date(timeIntervalSince1970: 1_000_000)
        try FileManager.default.setAttributes([.modificationDate: old], ofItemAtPath: first.path)
        let again = try library.copyFor("x.txt", skipId: nil)
        XCTAssertEqual(first, again)
        let date = try FileManager.default.attributesOfItem(atPath: again.path)[.modificationDate] as? Date
        XCTAssertEqual(date, old)
        XCTAssertEqual(try listing(), ["x.txt"])
    }

    func testAnEditedCopyGivesANumberedOne() throws {
        try Data("edited".utf8).write(to: try library.copyFor("x.txt", skipId: nil))
        let second = try library.copyFor("x.txt", skipId: nil)
        XCTAssertEqual(second.lastPathComponent, "x (2).txt")
        XCTAssertEqual(FileManager.default.contents(atPath: second.path), Data("one".utf8))
    }

    func testAnEditedFirstCopyAndAPristineSecondReopenTheSecond() throws {
        try Data("edited".utf8).write(to: try library.copyFor("x.txt", skipId: nil))
        let second = try library.copyFor("x.txt", skipId: nil)
        XCTAssertEqual(try library.copyFor("x.txt", skipId: nil), second)
        XCTAssertEqual(try listing(), ["x.txt", "x (2).txt"])
    }

    func testTwoEditedCopiesGiveTheThird() throws {
        try Data("edited".utf8).write(to: try library.copyFor("x.txt", skipId: nil))
        try Data("edited too".utf8).write(to: try library.copyFor("x.txt", skipId: nil))
        XCTAssertEqual(try library.copyFor("x.txt", skipId: nil).lastPathComponent, "x (3).txt")
    }

    func testTheSkippedIdIsPassedOverEvenWhenIdentical() throws {
        let first = try library.copyFor("x.txt", skipId: nil)
        let next = try library.copyFor("x.txt", skipId: library.idFor(first))
        XCTAssertEqual(next.lastPathComponent, "x (2).txt")
        XCTAssertEqual(FileManager.default.contents(atPath: first.path), Data("one".utf8))
    }

    func testIdsAreStableAndNameTheCopy() throws {
        let id = library.idFor(library.fileFor("x.txt"))
        XCTAssertEqual(id, "app:examples/x.txt")
        XCTAssertEqual(library.idFor(try library.copyFor("x.txt", skipId: nil)), id)
        XCTAssertEqual(library.idFor(try library.copyFor("x.txt", skipId: nil)), id)
        XCTAssertEqual(library.idFor(dir.appendingPathComponent("x (2).txt")), "app:examples/x (2).txt")
        XCTAssertNotNil(DocumentId("app:examples/x (2).txt"))
    }

    func testAnExampleThatCantBeReadThrows() {
        XCTAssertThrowsError(try library.copyFor("missing.txt", skipId: nil))
    }
}
