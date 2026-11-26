import ChordNotepadKit
import XCTest

/// The last song every launch reopens (docs/IOS.md, "The last song"): what
/// is kept, what a launch opens, the restore's command, the file.
final class LastSongTests: XCTestCase {
    private func doc(_ id: String?, modified: Bool = false, readOnly: Bool = false,
                     name: String = "Song.txt", location: String? = "Song.txt (Downloads)") -> DocumentState {
        DocumentState(displayName: name, documentId: id, isModified: modified, location: location,
                      readOnly: readOnly, title: name)
    }

    private func args(_ command: BridgeCommand) throws -> [String: Any] {
        try jsonObject(try command.argsJSON())
    }

    // MARK: - What is kept

    func testTheSongOnScreenIsKeptWithTheEditorsTextAndTheTab() {
        XCTAssertNil(LastSong.of(document: nil, editorText: "x", unsentTyping: false, mode: .edit),
                     "nothing before the session's first document")
        let kept = LastSong.of(document: doc("bookmark:A", readOnly: true), editorText: "C G\nla", unsentTyping: false,
                               mode: .edit)
        XCTAssertEqual(kept, LastSong(text: "C G\nla", documentId: "bookmark:A", displayName: "Song.txt",
                                      location: "Song.txt (Downloads)", modified: false, readOnly: true, mode: .edit))
        // Typing the session hasn't been sent yet is a change even before its document state says so.
        XCTAssertEqual(LastSong.of(document: doc("bookmark:A"), editorText: "C G", unsentTyping: true,
                                   mode: .play)?.modified, true)
    }

    // MARK: - What a launch opens

    func testTheFirstLaunchOpensQuickStartAndNoOtherDoes() {
        XCTAssertEqual(LastSongPolicy.launchSong(.missing), .quickStart, "no file yet: the first launch")
        XCTAssertEqual(LastSongPolicy.launchSong(.unreadable), .empty, "the app ran before: never Quick Start")
        // An empty untitled song (New, nothing typed) opens as that, not as the quick-start song.
        let empty = LastSong(text: "", documentId: nil, modified: false, mode: .edit)
        XCTAssertEqual(LastSongPolicy.launchSong(.song(empty)), .empty)
    }

    func testAnUntitledSongWithTextIsAnUnsavedDraft() throws {
        let untitled = LastSong(text: "My song", documentId: nil, displayName: "Untitled", modified: false, mode: .edit)
        let launch = LastSongPolicy.launchSong(.song(untitled))
        XCTAssertEqual(launch, .draft(untitled))
        XCTAssertTrue(launch.hasUnsavedText)
        XCTAssertEqual(launch.mode, .edit)
        let restore = LastSongPolicy.restore(untitled, resolved: nil)
        XCTAssertEqual(restore.command.name, "restore_draft")
        let sent = try args(restore.command)
        XCTAssertTrue(sent["document"] is NSNull)
        XCTAssertEqual(sent["modified"] as? Bool, true, "never saved: unsaved changes")
        XCTAssertEqual(sent["read_only"] as? Bool, false)
        XCTAssertEqual(sent["text"] as? String, "My song")
        XCTAssertNil(restore.documentId)
        XCTAssertTrue(restore.modified)
        XCTAssertNil(restore.notice, "nothing went missing")
        XCTAssertEqual(launch.kind, "draft")
    }

    func testASavedSongWithoutChangesIsReadAgain() {
        let saved = LastSong(text: "old text", documentId: "bookmark:A", displayName: "Song.txt",
                             location: "Song.txt (Downloads)", modified: false, mode: .edit)
        XCTAssertEqual(LastSongPolicy.launchSong(.song(saved)),
                       .open(DocumentRef(displayName: "Song.txt", id: "bookmark:A", location: "Song.txt (Downloads)"),
                             readOnly: false, mode: .edit))
        XCTAssertFalse(LastSongPolicy.launchSong(.song(saved)).hasUnsavedText)
        // An example's copy is a saved song like any other.
        let example = LastSong(text: "x", documentId: "app:examples/Blues.txt", displayName: "Blues.txt",
                               location: "Blues.txt (Examples)", modified: false, mode: .play)
        XCTAssertEqual(LastSongPolicy.launchSong(.song(example)),
                       .open(DocumentRef(displayName: "Blues.txt", id: "app:examples/Blues.txt",
                                         location: "Blues.txt (Examples)"), readOnly: false, mode: .play))
        // Without a kept name the ref still has the id, so the open's error can name something.
        let bare = LastSong(text: "", documentId: "bookmark:B", modified: false)
        XCTAssertEqual(LastSongPolicy.launchSong(.song(bare)),
                       .open(DocumentRef(displayName: "bookmark:B", id: "bookmark:B", location: "bookmark:B"),
                             readOnly: false, mode: .play))
    }

    func testTheQuickStartSongComesBackAsTheReadOnlyQuickStartSong() throws {
        let unchanged = LastSong(text: "…", documentId: LastSongPolicy.quickStartId, displayName: "01_quick_start.txt",
                                 location: "01_quick_start.txt (Examples)", modified: false, readOnly: true, mode: .play)
        XCTAssertEqual(LastSongPolicy.launchSong(.song(unchanged)), .quickStart)
        var changed = unchanged
        changed.modified = true
        changed.mode = AppMode.edit.rawValue
        XCTAssertEqual(LastSongPolicy.launchSong(.song(changed)), .draft(changed))
        let ref = DocumentRef(displayName: "01_quick_start.txt", id: LastSongPolicy.quickStartId,
                              location: "01_quick_start.txt (Examples)")
        let sent = try args(LastSongPolicy.restore(changed, resolved: ref).command)
        XCTAssertEqual((sent["document"] as? [String: Any])?["id"] as? String, LastSongPolicy.quickStartId)
        XCTAssertEqual(sent["read_only"] as? Bool, true, "still Save As")
        XCTAssertEqual(sent["modified"] as? Bool, true)
    }

    func testAChangedSongKeepsItsDocumentWhileTheStoreReachesIt() throws {
        let changed = LastSong(text: "new words", documentId: "bookmark:A", displayName: "Song.txt",
                               location: "Song.txt (Downloads)", modified: true, mode: .edit)
        let ref = DocumentRef(displayName: "Song.txt", id: "bookmark:A", location: "Song.txt (iCloud Drive)")
        let restore = LastSongPolicy.restore(changed, resolved: ref)
        let sent = try args(restore.command)
        XCTAssertEqual((sent["document"] as? [String: Any])?["location"] as? String, "Song.txt (iCloud Drive)",
                       "the store's ref, as it is now")
        XCTAssertEqual(sent["modified"] as? Bool, true)
        XCTAssertEqual(sent["text"] as? String, "new words")
        XCTAssertEqual(restore.documentId, "bookmark:A")
        XCTAssertNil(restore.notice)
    }

    func testAChangedSongWhoseFileIsGoneKeepsItsWordsAsANewSongAndSaysSo() throws {
        // Android's DraftPolicy.restore: the document is dropped, the text kept as unsaved changes.
        let changed = LastSong(text: "new words", documentId: "bookmark:A", displayName: "Song.txt",
                               location: "Song.txt (Downloads)", modified: true, readOnly: true, mode: .edit)
        let restore = LastSongPolicy.restore(changed, resolved: nil)
        let sent = try args(restore.command)
        XCTAssertTrue(sent["document"] is NSNull)
        XCTAssertEqual(sent["modified"] as? Bool, true)
        XCTAssertEqual(sent["read_only"] as? Bool, false, "a new song isn't read only")
        XCTAssertEqual(sent["text"] as? String, "new words")
        XCTAssertNil(restore.documentId)
        XCTAssertEqual(restore.notice,
                       "Couldn't find Song.txt (Downloads): its unsaved changes are open as a new song.")
    }

    // MARK: - The file

    func testTheFileKeepsTheSongAndTellsAFirstLaunchFromABrokenFile() throws {
        let folder = FileManager.default.temporaryDirectory
            .appendingPathComponent("last-song-\(UUID().uuidString)", isDirectory: true)
        defer { try? FileManager.default.removeItem(at: folder) }
        let file = LastSongFile(url: folder.appendingPathComponent("last_song.json"))
        XCTAssertEqual(file.read(), .missing)
        let song = LastSong(text: "Ünïcode 🎸\nC G", documentId: "bookmark:A", displayName: "Song.txt",
                            location: "Song.txt (Downloads)", modified: true, readOnly: false, mode: .edit)
        XCTAssertTrue(file.write(song), "the folder is made as needed")
        XCTAssertEqual(file.read(), .song(song))
        var later = song
        later.text = "shorter"
        XCTAssertTrue(file.write(later))
        XCTAssertEqual(file.read(), .song(later), "written in full each time")
        try Data("{not json".utf8).write(to: file.url)
        XCTAssertEqual(file.read(), .unreadable)
    }
}
