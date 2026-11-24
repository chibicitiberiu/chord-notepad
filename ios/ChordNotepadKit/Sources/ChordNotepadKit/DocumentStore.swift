import CNBridge
import Foundation

/// The documents Python reads and writes, by id (on iOS a security-scoped
/// bookmark key or a file URL; Python treats ids as opaque).
///
/// Python calls these on its `python-session` thread, and `writeBytes` and
/// `copyFromFile` also on an export's worker thread, so an implementation
/// must be safe on any thread. Blocking file I/O is fine; waiting for the
/// bridge thread (a ``Session`` call) is not: that can deadlock, because the
/// bridge thread may be waiting for the session thread at the same time.
///
/// A failure throws ``DocumentStoreError`` with a user-facing message (worded
/// like the desktop's: "File not found: …", "Permission denied: …"); Python
/// shows it as the `FileOperationError`'s text. Any other error is shown as
/// its `String(describing:)`.
public protocol DocumentStore: AnyObject, Sendable {
    /// The document's bytes (at most 5 MB). Python decodes them, and reads
    /// them again before a save to keep the file's encoding and line endings.
    func readBytes(id: String) throws -> Data
    /// Replace the document's content (a song Python encoded, a MIDI export).
    func writeBytes(id: String, data: Data) throws
    /// Replace the document's content with the local file at `path` (an audio
    /// export rendered into the caches folder), streamed.
    func copyFromFile(id: String, path: String) throws
    /// Whether the document can still be opened.
    func isAvailable(id: String) -> Bool
    /// Recently used documents still available, newest first.
    func recent() throws -> [DocumentRef]
    /// Move a document to the front of the recent list (capped).
    func addRecent(_ ref: DocumentRef) throws
    /// The recent list's cap (`max_recent_files`).
    func setMaxRecent(_ count: Int) throws
    /// The ref for `id`, or nil when the document can't be reached.
    func describe(id: String) throws -> DocumentRef?
    /// Rename the document in place to `displayName` (with its extension) and
    /// return its new ref; the recent list follows. Throw
    /// ``DocumentStoreError/renameUnsupported(_:)`` when the storage can't
    /// rename it (the UI offers Save As).
    func rename(id: String, displayName: String) throws -> DocumentRef
}

/// A document operation failed; the message is shown to the user.
public enum DocumentStoreError: Error, Equatable, CustomStringConvertible {
    /// Any failure (Python raises `FileOperationError`).
    case failed(String)
    /// The storage can't rename this document (Python raises `RenameNotSupported`).
    case renameUnsupported(String)

    public var description: String {
        switch self {
        case .failed(let message), .renameUnsupported(let message): return message
        }
    }
}

/// Makes `store` the one the Python side calls (one at a time per process).
///
/// A replaced store's box is never released: a Python thread may still be
/// inside one of its callbacks, and there is about one store per process.
enum StoreRegistry {
    private static let lock = NSLock()
    nonisolated(unsafe) private static var current: Unmanaged<StoreBox>?

    static func install(_ store: DocumentStore?) {
        lock.withLock {
            current = store.map { Unmanaged.passRetained(StoreBox($0)) }
            if let current {
                var callbacks = makeStoreCallbacks(context: current.toOpaque())
                cn_set_store(&callbacks)
            } else {
                cn_set_store(nil)
            }
        }
    }
}

final class StoreBox: @unchecked Sendable {
    let store: DocumentStore

    init(_ store: DocumentStore) {
        self.store = store
    }
}

private func box(_ context: UnsafeMutableRawPointer?) -> DocumentStore {
    Unmanaged<StoreBox>.fromOpaque(context!).takeUnretainedValue().store
}

/// Runs `body`, turning a thrown error into the C error code and message.
private func guarded(_ error: UnsafeMutablePointer<UnsafeMutablePointer<CChar>?>?,
                     _ body: () throws -> Void) -> Int32 {
    do {
        try body()
        return Int32(CN_OK)
    } catch DocumentStoreError.renameUnsupported(let message) {
        error?.pointee = mallocString(message)
        return Int32(CN_RENAME_UNSUPPORTED)
    } catch DocumentStoreError.failed(let message) {
        error?.pointee = mallocString(message)
        return Int32(CN_ERROR)
    } catch let other {
        error?.pointee = mallocString(String(describing: other))
        return Int32(CN_ERROR)
    }
}

private func refJSON(_ ref: DocumentRef) throws -> String {
    String(decoding: try BridgeJSON.encoder.encode(ref), as: UTF8.self)
}

private func string(_ pointer: UnsafePointer<CChar>?) -> String {
    pointer.map { String(cString: $0) } ?? ""
}

/// The C callbacks over the registered ``DocumentStore`` (context: its box).
private func makeStoreCallbacks(context: UnsafeMutableRawPointer) -> CNStoreCallbacks {
    CNStoreCallbacks(
        context: context,
        read_bytes: { context, id, outData, outLen, error in
            guarded(error) {
                let data = try box(context).readBytes(id: string(id))
                let buffer = malloc(max(data.count, 1))!.assumingMemoryBound(to: UInt8.self)
                data.copyBytes(to: buffer, count: data.count)
                outData?.pointee = buffer
                outLen?.pointee = data.count
            }
        },
        write_bytes: { context, id, data, len, error in
            guarded(error) {
                let bytes = data.map { Data(bytes: $0, count: len) } ?? Data()
                try box(context).writeBytes(id: string(id), data: bytes)
            }
        },
        copy_from_file: { context, id, path, error in
            guarded(error) {
                try box(context).copyFromFile(id: string(id), path: string(path))
            }
        },
        is_available: { context, id, outAvailable, error in
            guarded(error) {
                outAvailable?.pointee = box(context).isAvailable(id: string(id)) ? 1 : 0
            }
        },
        recent: { context, outJSON, error in
            guarded(error) {
                let refs = try box(context).recent()
                let json = String(decoding: try BridgeJSON.encoder.encode(refs), as: UTF8.self)
                outJSON?.pointee = mallocString(json)
            }
        },
        add_recent: { context, id, displayName, location, error in
            guarded(error) {
                try box(context).addRecent(DocumentRef(
                    displayName: string(displayName), id: string(id), location: string(location)))
            }
        },
        set_max_recent: { context, count, error in
            guarded(error) {
                try box(context).setMaxRecent(Int(count))
            }
        },
        describe: { context, id, outJSON, error in
            guarded(error) {
                if let ref = try box(context).describe(id: string(id)) {
                    outJSON?.pointee = mallocString(try refJSON(ref))
                } else {
                    outJSON?.pointee = nil
                }
            }
        },
        rename: { context, id, displayName, outJSON, error in
            guarded(error) {
                let ref = try box(context).rename(id: string(id), displayName: string(displayName))
                outJSON?.pointee = mallocString(try refJSON(ref))
            }
        }
    )
}
