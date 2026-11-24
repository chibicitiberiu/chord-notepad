import Foundation

// Rename (tap the app bar's title; Android's ui/main/RenameFlow.kt): the
// dialog's field, the file name it shows ("Saved as name.txt"), and what
// happens when the storage can't rename (the session answers RenameFailed).

/// The extension a song gets when its name has none.
public let defaultSongExtension = ".txt"

/// The extension at the end of a name: a dot and 1–5 ASCII letters or digits.
private func extensionRange(_ name: String) -> Range<String.Index>? {
    guard let dot = name.lastIndex(of: ".") else { return nil }
    let tail = name[name.index(after: dot)...]
    guard (1...5).contains(tail.count),
          tail.unicodeScalars.allSatisfy({ $0.isASCII && (CharacterSet.alphanumerics.contains($0)) }) else {
        return nil
    }
    return dot..<name.endIndex
}

/// The name the field starts with (and the app bar's title): the document's
/// file name without its extension.
public func renameFieldText(_ displayName: String) -> String {
    guard let range = extensionRange(displayName) else { return displayName }
    return String(displayName[..<range.lowerBound])
}

/// The file name a typed `input` saves as: trimmed, with the current
/// document's extension (or `.txt`) unless it names one itself.
public func renamedFileName(_ input: String, currentDisplayName: String) -> String {
    let name = input.trimmingCharacters(in: .whitespacesAndNewlines)
    if name.isEmpty { return "" }
    if extensionRange(name) != nil { return name }
    let ext = extensionRange(currentDisplayName).map { String(currentDisplayName[$0]) } ?? defaultSongExtension
    return name + ext
}

/// Why the Rename button is disabled.
public enum RenameProblem: Sendable, Equatable {
    case empty
    case badCharacter
    case unchanged
}

/// Characters a document name can't hold on the usual storages.
private let badCharacters = Set("/\\:*?\"<>|")

/// The problem with renaming `currentDisplayName` to `input`, or nil.
public func renameProblem(_ input: String, currentDisplayName: String) -> RenameProblem? {
    let name = input.trimmingCharacters(in: .whitespacesAndNewlines)
    if name.isEmpty { return .empty }
    if name.contains(where: { badCharacters.contains($0) })
        || name.unicodeScalars.contains(where: { $0.value < 32 }) {
        return .badCharacter
    }
    if renamedFileName(name, currentDisplayName: currentDisplayName) == currentDisplayName { return .unchanged }
    return nil
}

/// The line under the rename field: the problem, the session's refusal, or
/// "Saved as name.txt". `error` is true when it shows in the error colour.
public func renameHint(_ input: String, currentDisplayName: String, refusal: String?) -> (text: String, error: Bool) {
    if let refusal { return (refusal, true) }
    switch renameProblem(input, currentDisplayName: currentDisplayName) {
    case .badCharacter:
        return ("A name can't contain / \\ : * ? \" < > |", true)
    case .empty:
        return ("Type a name", false)
    default:
        return ("Saved as “\(renamedFileName(input, currentDisplayName: currentDisplayName))”", false)
    }
}

/// The session couldn't rename the document (`reason`): offer Save As under
/// `name` when `canSaveAs`, else just say why.
public struct RenameFailure: Sendable, Equatable {
    public var name: String
    public var reason: String
    public var canSaveAs: Bool

    public init(name: String, reason: String, canSaveAs: Bool) {
        self.name = name
        self.reason = reason
        self.canSaveAs = canSaveAs
    }

    public init(_ event: RenameFailed) {
        self.init(name: event.name, reason: event.reason, canSaveAs: event.canSaveAs)
    }
}
