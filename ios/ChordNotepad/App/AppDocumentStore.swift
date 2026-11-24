import ChordNotepadKit
import Foundation

/// The app's document store: the kit's ``FileDocumentStore`` over
/// ``ScopedFileAccess`` (docs/IOS.md, "Files"). Ids:
///
/// - `bundle:<file>`: a song the app ships (the quick-start song), read only;
/// - `app:examples/<file>`: a copy the menu's Examples made, in Application
///   Support, always writable, not in Files;
/// - `app:exports/<uuid>/<file>`: an export waiting for the export picker;
/// - `bookmark:<uuid>`: a song the user picked (Open, Save As) or opened from
///   Files, found again through its bookmark in `bookmarks.json`.
enum AppDocumentStore {
    /// The store, its lists in Application Support.
    static func make() -> FileDocumentStore {
        FileDocumentStore(
            access: ScopedFileAccess(documents: AppPaths.documents),
            appDir: AppPaths.filesDir,
            recentFile: AppPaths.filesDir.appendingPathComponent("recent-documents.json"),
            bookmarksFile: AppPaths.filesDir.appendingPathComponent("bookmarks.json"),
            bundled: { name in
                guard DocumentId.isFileName(name) else { return nil }
                let file = name as NSString
                return Bundle.main.url(forResource: file.deletingPathExtension, withExtension: file.pathExtension)
            })
    }

    /// The ref of a song the app ships.
    static func bundledRef(_ fileName: String) -> DocumentRef {
        DocumentRef(displayName: fileName, id: DocumentId.bundled(fileName).string,
                    location: "\(fileName) (Examples)")
    }

    /// The example songs the app ships (`examples/*.txt` in the bundle) and
    /// their copies in Application Support.
    static let examples = ExampleLibrary(
        list: {
            let folder = Bundle.main.resourceURL?.appendingPathComponent(ExampleLibrary.folder)
            return (folder.flatMap { try? FileManager.default.contentsOfDirectory(atPath: $0.path) }) ?? []
        },
        read: { name in
            guard let folder = Bundle.main.resourceURL?.appendingPathComponent(ExampleLibrary.folder),
                  let data = FileManager.default.contents(atPath: folder.appendingPathComponent(name).path) else {
                throw FileAccessError.notFound
            }
            return data
        },
        dir: AppPaths.filesDir.appendingPathComponent(ExampleLibrary.folder, isDirectory: true))

    /// What Examples lists.
    static var exampleNames: [String] { examples.names() }
}
