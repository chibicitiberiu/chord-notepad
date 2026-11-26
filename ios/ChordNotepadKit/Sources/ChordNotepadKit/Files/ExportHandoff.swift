import Foundation

// An export on iOS, from the app's side (docs/IOS.md "Files", Exports): the
// session renders and writes the store's file while "Preparing export…" is
// up (its ExportState), then the app opens the export picker on the file and
// tells the session how it went (`export_finished`). Plain state, tested on
// Linux; AppModel drives it and presents the dialog and the picker.

/// "Preparing export…": a spinner, the percentage of an audio export, Cancel.
public struct ExportDialog: Sendable, Equatable {
    public static let title = "Preparing export…"
    public static let cancel = "Cancel"

    /// The store id of the export's file.
    public let documentId: String
    /// `midi`, `audio` or `pdf` (`ExportState.kind`).
    public let kind: String
    /// How much of an audio export is rendered, 0 to 1; nil for MIDI and PDF.
    public let progress: Double?

    public init(documentId: String, kind: String, progress: Double?) {
        self.documentId = documentId
        self.kind = kind
        self.progress = progress
    }

    /// "42%" under the spinner for an audio export, as the status line counts.
    public var percent: String? {
        progress.map { "\(Int((min(1, max(0, $0)) * 100).rounded()))%" }
    }
}

/// A written export's file, waiting for (or in) the export picker.
public struct ExportFile: Sendable, Equatable {
    public let id: String
    public let file: URL

    public init(id: String, file: URL) {
        self.id = id
        self.file = file
    }
}

/// What the app does when the user cancels "Preparing export…".
public struct ExportCancel: Sendable, Equatable {
    /// A written file that hadn't reached the picker: delete it.
    public var discard: ExportFile?
    /// The picker is opening for it: close it once it is up (``ExportHandoff/pickerPresented(_:)``
    /// says so); nothing is saved.
    public var closePicker = false

    public init(discard: ExportFile? = nil, closePicker: Bool = false) {
        self.discard = discard
        self.closePicker = closePicker
    }
}

/// Which exports wait for the export picker, which one it shows, and which
/// ones the app is done with (saved, not saved or cancelled).
public struct ExportHandoff: Sendable, Equatable {
    /// Written, waiting for the picker, oldest first.
    public private(set) var waiting: [ExportFile] = []
    /// The export whose picker is opening or open.
    public private(set) var offering: ExportFile?
    /// ``offering``'s picker is on screen (its presentation finished).
    public private(set) var pickerShown = false
    /// The exports the app told the session about (`export_finished`):
    /// "Preparing export…" doesn't show for them, and a file of one of them
    /// that arrives late is deleted.
    public private(set) var finished: Set<String> = []
    /// Cancel came while ``offering``'s picker was opening: close it once up.
    public private(set) var closeWhenShown = false

    public init() {}

    /// "Preparing export…" for the session's export: from the picked file
    /// until the picker is on screen, unless cancelled. Nil while none is
    /// prepared or the export failed (the state is empty then).
    public func dialog(_ state: ExportState?) -> ExportDialog? {
        guard let state, let id = state.documentId, !finished.contains(id) else { return nil }
        if offering?.id == id && pickerShown { return nil }
        return ExportDialog(documentId: id, kind: state.kind, progress: state.progress)
    }

    /// The store wrote export `id`'s file. False: the export was cancelled,
    /// delete the file (no picker).
    public mutating func written(_ export: ExportFile) -> Bool {
        if finished.contains(export.id) { return false }
        waiting.removeAll { $0.id == export.id }
        waiting.append(export)
        return true
    }

    /// The export to open the picker for now, if the picker is free.
    public mutating func nextOffer() -> ExportFile? {
        guard offering == nil, !waiting.isEmpty else { return nil }
        let next = waiting.removeFirst()
        offering = next
        pickerShown = false
        closeWhenShown = false
        return next
    }

    /// The picker for `id` is on screen. True: it was cancelled meanwhile,
    /// close it (its answer is "not saved").
    public mutating func pickerPresented(_ id: String) -> Bool {
        guard offering?.id == id else { return false }
        pickerShown = true
        return closeWhenShown
    }

    /// The picker for `id` closed. True: tell the session
    /// (`export_finished`); false when it already knows (a cancelled export).
    /// The caller deletes the file either way.
    public mutating func pickerDone(_ id: String) -> Bool {
        if offering?.id == id {
            offering = nil
            pickerShown = false
            closeWhenShown = false
        }
        return finished.insert(id).inserted
    }

    /// The user cancelled "Preparing export…" for `id`: the app tells the
    /// session (`export_finished`, not saved) at once.
    public mutating func cancel(_ id: String) -> ExportCancel {
        finished.insert(id)
        var effect = ExportCancel()
        if let index = waiting.firstIndex(where: { $0.id == id }) {
            effect.discard = waiting.remove(at: index)
        }
        if offering?.id == id {
            if pickerShown {
                effect.closePicker = true
            } else {
                closeWhenShown = true
            }
        }
        return effect
    }
}
