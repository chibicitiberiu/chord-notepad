import Foundation

// The session's requests and how the iOS app answers them (Android's
// ui/requests/RequestController.kt and files/DocumentPickers.kt). The session
// asks with a request event and waits for `respond {request_id, value}`; only
// one is pending at a time, and a newer one replaces it.

/// A request the session is waiting on.
public enum SessionRequest: Sendable, Equatable {
    case confirmDiscard(ConfirmDiscardRequest)
    case pickDocument(PickDocumentRequest)
    case insertDirective(InsertDirectiveRequest)
    case paintPdf(PaintPdfRequest)

    /// The request in `output`, or nil when it isn't one.
    public init?(_ output: SessionOutput) {
        switch output {
        case .confirmDiscardRequest(let request): self = .confirmDiscard(request)
        case .pickDocumentRequest(let request): self = .pickDocument(request)
        case .insertDirectiveRequest(let request): self = .insertDirective(request)
        case .paintPdfRequest(let request): self = .paintPdf(request)
        default: return nil
        }
    }

    public var requestId: Int {
        switch self {
        case .confirmDiscard(let request): return request.requestId
        case .pickDocument(let request): return request.requestId
        case .insertDirective(let request): return request.requestId
        case .paintPdf(let request): return request.requestId
        }
    }
}

/// How the app presents a pending request.
public enum RequestPresentation: Sendable, Equatable {
    /// The screen shows a dialog for it (the unsaved-changes question, an
    /// Insert directive's fields).
    case dialog(SessionRequest)
    /// A document picker, or for an export a file of the store's, answers it.
    case picker(PickDocumentRequest)
    /// Painted and written off the main actor, no UI (``RequestController/paintOnce(_:)``).
    case paint(PaintPdfRequest)
}

public func presentationOf(_ request: SessionRequest) -> RequestPresentation {
    switch request {
    case .confirmDiscard, .insertDirective: return .dialog(request)
    case .pickDocument(let pick): return .picker(pick)
    case .paintPdf(let paint): return .paint(paint)
    }
}

/// What answers a ``PickDocumentRequest`` on iOS.
public enum PickerLaunch: Sendable, Equatable {
    /// `UIDocumentPickerViewController(forOpeningContentTypes:)` with these
    /// UTType identifiers; the picked file is adopted (bookmarked).
    case open(contentTypes: [String])
    /// Save As: iOS's export picker needs a file before it opens, so the app
    /// makes an empty one with this name and the picker moves it where the
    /// user chooses (`forExporting:asCopy: false`); the moved file is
    /// adopted, and the session then writes the song into it.
    case save(suggestedName: String)
    /// An export: no picker yet. The request is answered at once with a file
    /// of the store's (``FileDocumentStore/prepareExport(named:)``); once the
    /// session has written it, the export picker copies it where the user
    /// chooses.
    case export(PickMode, suggestedName: String)
}

/// What Open offers: text first, then anything, as the desktop's "Text Files /
/// All Files" and Android's `OPEN_MIME_TYPES` (`.cho` and `.chordpro` files
/// aren't plain text to iOS; the core reports a file it can't read).
public let openContentTypes = ["public.plain-text", "public.text", "public.data"]

/// The picker for `request`.
public func pickerFor(_ request: PickDocumentRequest) -> PickerLaunch {
    let name = request.suggestedName
    switch request.mode {
    case .open: return .open(contentTypes: openContentTypes)
    case .save: return .save(suggestedName: name.isEmpty ? "Untitled.txt" : name)
    case .exportMidi: return .export(.exportMidi, suggestedName: name.isEmpty ? "Untitled.mid" : name)
    case .exportAudio: return .export(.exportAudio, suggestedName: name.isEmpty ? "Untitled.wav" : name)
    case .exportPdf: return .export(.exportPdf, suggestedName: name.isEmpty ? "Untitled.pdf" : name)
    }
}

/// The unsaved-changes question's texts (the desktop's
/// `formatting.CONFIRM_DISCARD_*`, Android's `unsaved_*`).
public enum DiscardQuestion {
    public static let title = "Unsaved Changes"
    public static let message = "Do you want to save your changes?"
    public static let save = "Save"
    public static let discard = "Don't save"
    public static let cancel = "Cancel"
}

/// Answers the session's requests (Android's `RequestController`). It
/// remembers which pick request already got its picker, so the same request
/// seen again doesn't open a second one, and a picker's result answers only
/// the request it was opened for (a result for anything else is ignored).
///
/// Main actor; adopting a picked file and making an export's file are file
/// I/O and run through `runOffMain`, which hands its result back on the main
/// actor.
@MainActor
public final class RequestController {
    /// Runs `work` away from the main actor, then `done` with its result on it.
    public typealias OffMain = (_ work: @escaping @Sendable () -> DocumentRef?,
                                _ done: @escaping @Sendable @MainActor (DocumentRef?) -> Void) -> Void
    /// The same for a PDF's painting, whose result is the request's answer.
    public typealias PaintOffMain = (_ work: @escaping @Sendable () -> String?,
                                     _ done: @escaping @Sendable @MainActor (String?) -> Void) -> Void

    private let pending: () -> SessionRequest?
    private let submit: (BridgeCommand) -> Void
    private let answered: (Int) -> Void
    private let adopt: @Sendable (URL, PickMode) throws -> DocumentRef
    private let prepareExport: @Sendable (PickMode, String) throws -> DocumentRef
    private let runOffMain: OffMain
    private let paint: @Sendable (PaintPdfRequest) throws -> String?
    private let paintOffMain: PaintOffMain
    private var launchedPickerId: Int?
    private var paintedId: Int?

    /// - Parameters:
    ///   - pending: The session's pending request (the snapshot's).
    ///   - submit: Sends a command.
    ///   - answered: Told the id of each request answered, before the answer
    ///     is sent (the snapshot drops it, so its dialog goes).
    ///   - adopt: Bookmarks and describes a picked file
    ///     (``FileDocumentStore/adopt(_:)``); file I/O.
    ///   - prepareExport: Makes the store's file for an export
    ///     (``FileDocumentStore/prepareExport(named:)``); file I/O.
    ///   - runOffMain: Runs file I/O away from the main actor.
    ///   - paint: Paints a PDF export and writes it (``PdfExporter/export(_:)``):
    ///     "" written, else the reason; file I/O.
    ///   - paintOffMain: Runs the painting away from the main actor.
    public init(pending: @escaping () -> SessionRequest?, submit: @escaping (BridgeCommand) -> Void,
                answered: @escaping (Int) -> Void,
                adopt: @escaping @Sendable (URL, PickMode) throws -> DocumentRef,
                prepareExport: @escaping @Sendable (PickMode, String) throws -> DocumentRef,
                runOffMain: @escaping OffMain,
                paint: @escaping @Sendable (PaintPdfRequest) throws -> String? = { _ in nil },
                paintOffMain: @escaping PaintOffMain = { work, done in
                    Task.detached {
                        let answer = work()
                        await MainActor.run { done(answer) }
                    }
                }) {
        self.pending = pending
        self.submit = submit
        self.answered = answered
        self.adopt = adopt
        self.prepareExport = prepareExport
        self.runOffMain = runOffMain
        self.paint = paint
        self.paintOffMain = paintOffMain
    }

    /// A request just became pending: paints a PDF's pages, answers an
    /// export with the store's file, and returns the picker to open for an
    /// open or a save that hasn't had one yet (marking it opened), else nil.
    public func onPending(_ request: SessionRequest?) -> PickerLaunch? {
        guard let request else { return nil }
        switch presentationOf(request) {
        case .paint(let paint):
            paintOnce(paint)
            return nil
        case .picker:
            return takePickerLaunch()
        case .dialog:
            return nil
        }
    }

    /// Paint and write `request`'s PDF off the main actor and answer it, once
    /// per request (the same pending request seen again isn't painted twice).
    /// Always answered, whatever fails, so the session's flow never waits.
    public func paintOnce(_ request: PaintPdfRequest) {
        guard paintedId != request.requestId else { return }
        paintedId = request.requestId
        let paint = self.paint
        paintOffMain({
            do {
                return try paint(request)
            } catch {
                return "\(type(of: error)): \(error)"
            }
        }) { [weak self] answer in
            guard let self else { return }
            self.answered(request.requestId)
            self.submit(.respondToPaintPdfRequest(requestId: request.requestId, value: answer))
        }
    }

    /// The picker for the pending pick request, once per request; nil
    /// otherwise. An export gets no picker now: it is answered with the
    /// store's file, and the export picker opens once the file is written.
    public func takePickerLaunch() -> PickerLaunch? {
        guard case .pickDocument(let request)? = pending(), launchedPickerId != request.requestId else { return nil }
        launchedPickerId = request.requestId
        let launch = pickerFor(request)
        if case .export(let mode, let name) = launch {
            let prepare = prepareExport
            runOffMain({ try? prepare(mode, name) }) { [weak self] ref in
                self?.respondPick(request.requestId, ref)
            }
            return nil
        }
        return launch
    }

    /// The picker returned `url` (nil: the user backed out). Answers the pick
    /// request it was opened for; a result for any other is ignored.
    public func onPicked(_ url: URL?) {
        guard case .pickDocument(let request)? = pending(), request.requestId == launchedPickerId else { return }
        guard let url else {
            respondPick(request.requestId, nil)
            return
        }
        let adopt = self.adopt
        let mode = request.mode
        runOffMain({ try? adopt(url, mode) }) { [weak self] ref in
            self?.respondPick(request.requestId, ref)
        }
    }

    /// The unsaved-changes question's answer; nil (dismissed) is Cancel.
    public func answerDiscard(_ request: ConfirmDiscardRequest, _ choice: DiscardChoice?) {
        let answer = choice ?? .cancel
        answered(request.requestId)
        submit(.respondToConfirmDiscardRequest(requestId: request.requestId, value: answer))
    }

    /// An Insert directive dialog's fields, or nil for Cancel; the session checks them.
    public func answerDirective(_ request: InsertDirectiveRequest, _ fields: [String: String]?) {
        answered(request.requestId)
        submit(.respondToInsertDirectiveRequest(requestId: request.requestId, value: fields))
    }

    /// Ask the session whether an Insert dialog's `fields` make a valid
    /// directive (reply: `DirectiveCheck`); the request stays pending.
    public func checkDirective(_ request: InsertDirectiveRequest, _ fields: [String: String]) {
        submit(.checkDirective(fields: .object(fields.mapValues { .string($0) }), kind: request.kind,
                               requestId: request.requestId))
    }

    /// Cancel `request` (dismissed, or no UI for it).
    public func cancel(_ request: SessionRequest) {
        switch request {
        case .confirmDiscard(let discard):
            answerDiscard(discard, .cancel)
        case .pickDocument(let pick):
            respondPick(pick.requestId, nil)
        case .insertDirective(let insert):
            answerDirective(insert, nil)
        case .paintPdf(let paint):
            answered(paint.requestId)
            submit(.respondToPaintPdfRequest(requestId: paint.requestId, value: nil))
        }
    }

    private func respondPick(_ requestId: Int, _ ref: DocumentRef?) {
        answered(requestId)
        submit(.respondToPickDocumentRequest(requestId: requestId, value: ref))
    }
}
