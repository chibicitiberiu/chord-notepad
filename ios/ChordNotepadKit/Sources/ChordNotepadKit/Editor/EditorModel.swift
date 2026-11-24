import Foundation

/// Which version of the text the editor shows, in the session's terms: the
/// `client_token` of the `set_text` that sent it (a user edit), or the
/// `text_revision` of the session's own edit (token 0).
public struct TextIdentity: Sendable, Hashable {
    public var clientToken: Int
    public var revision: Int?

    public init(clientToken: Int, revision: Int?) {
        self.clientToken = clientToken
        self.revision = revision
    }

    /// Whether `state`'s spans were computed for exactly this text.
    public func accepts(_ state: HighlightState) -> Bool {
        state.clientToken == clientToken && (revision == nil || state.textRevision == revision)
    }
}

/// The sounding chord, as the editor paints it: UTF-16 `[start, end)` of the
/// current text.
public struct PlayingChord: Sendable, Hashable {
    public var start: Int
    public var end: Int
    public var chordIndex: Int?
    public var bar: Int

    public var range: UTF16Range { UTF16Range(start, end) }
}

/// One change for the view's text: replace UTF-16 `range` of the text as the
/// previous change left it with `replacement`.
public struct ViewEdit: Sendable, Hashable {
    public var range: UTF16Range
    public var replacement: String
}

/// What the view does after the model took an input: send `commands`, apply
/// `viewEdits` to its text in order, then select `selection` and repaint the
/// styles when `restyle`.
public struct EditorEffects: Sendable {
    public var commands: [BridgeCommand] = []
    public var viewEdits: [ViewEdit] = []
    /// Where the selection goes (nil: where it is).
    public var selection: UTF16Range?
    /// The spans, the playing chord or the font changed.
    public var restyle = false
    /// A document was opened (a `reset` edit): show it from its start.
    public var documentOpened = false
    /// The sounding chord moved: keep it in view.
    public var playingMoved = false

    public init() {}

    mutating func merge(_ other: EditorEffects) {
        commands += other.commands
        viewEdits += other.viewEdits
        selection = other.selection ?? selection
        restyle = restyle || other.restyle
        documentOpened = documentOpened || other.documentOpened
        playingMoved = playingMoved || other.playingMoved
    }

    /// The names of the commands, for tests and logs.
    public var commandNames: [String] { commands.map(\.name) }
}

/// What the Edit ribbon's buttons and the keyboard shortcuts do in the editor.
public enum EditorAction: Sendable, Hashable {
    case undo, redo
    case fontBigger, fontSmaller, fontReset
    /// `american` or `european`: the notation the text is read in.
    case setNotation(String)
    /// Rewrite the chords in the other notation (the ribbon's Convert).
    case convertNotation
    case toggleComment, duplicateLines, deleteLines, moveLinesUp, moveLinesDown
}

/// What the view does with a change the user is about to make
/// (`textView(_:shouldChangeTextIn:replacementText:)`).
public enum ReplaceDecision: Sendable, Equatable {
    /// Let it through.
    case allow
    /// Refuse it and put this text in instead (normalised paste).
    case replace(String)
    /// Refuse it (read-only).
    case refuse
}

/// The song editor's model: the text the view shows, its selection, the
/// highlighting painted over it, the undo history and the text exchange with
/// the session (Android's `EditorController`, as a value with no UI).
///
/// The view owns nothing but drawing: every input goes through a mutating
/// method that returns ``EditorEffects`` for the view to apply.
///
/// - User edits (typing, paste, dictation) go to the session as `set_text`
///   with an increasing client token (``viewChanged(text:selection:composing:)``).
///   The session doesn't echo them.
/// - The session's own edits arrive as `TextEdited` (``receive(_:)``) and come
///   back as ``ViewEdit``s, folded into the undo history per their policy;
///   they are not sent back. While the user composes (marked text from an
///   input method), they wait until the composition ends.
/// - A `HighlightState` is painted only when it was computed for the text the
///   view shows (``TextIdentity/accepts(_:)``); until then the old spans move
///   with the edits (``Swift/Array/shifted(by:)``).
/// - Undo and redo are the model's (``EditHistory``); the text they leave goes
///   to the session as a user edit.
public struct EditorModel: Sendable {
    /// The text the view shows.
    public private(set) var text = ""
    /// The view's selection (a caret when empty).
    public private(set) var selection = UTF16Range(caret: 0)
    /// The highlight spans painted now (UTF-16 offsets of ``text``).
    public private(set) var spans: [PaintedSpan] = []
    /// The chord that is sounding, or nil.
    public private(set) var playing: PlayingChord?
    /// Documents opened into the editor (edits with `reset`).
    public private(set) var documentsOpened = 0
    /// The current text's identity, for picking the right `HighlightState`.
    public private(set) var identity = TextIdentity(clientToken: 0, revision: nil)
    /// The session's editor settings (font, wrap, read-only, notation).
    public private(set) var editorState: EditorState?
    /// An input method is composing (marked text).
    public private(set) var composing = false
    public private(set) var history = EditHistory()

    // The text the session has, as far as the editor knows.
    private var syncedText = ""
    private var lastToken = 0
    private var latestHighlight: HighlightState?
    // The highlight painted, and the identity of the text it was painted on
    // (a state that came before its text is painted again once the text is there).
    private var appliedHighlight: HighlightState?
    private var appliedIdentity: TextIdentity?
    private var latestPlayback: PlaybackState?
    // Session edits that arrived while composing.
    private var pending: [TextEdited] = []
    // The text and selection when the composition began.
    private var composeBase: (text: String, selection: UTF16Range)?

    public init() {}

    public var readOnly: Bool { editorState?.readOnly ?? false }
    public var wordWrap: Bool { editorState?.wordWrap ?? false }
    public var fontPoints: Int { editorState?.fontSize ?? EditorFont.defaultPoints }
    public var fontKind: EditorFontKind { EditorFont.kind(forFamily: editorState?.fontFamily ?? "") }
    /// `american` or `european`; nil before the session says.
    public var notation: String? { editorState?.notation }
    public var canUndo: Bool { !composing && !readOnly && history.canUndo }
    public var canRedo: Bool { !composing && !readOnly && history.canRedo }

    /// Where the text must not wrap (inside chords), while it wraps.
    public var joinPoints: [Int] { ChordNotepadKit.joinPoints(text, spans: spans, wordWrap: wordWrap) }

    /// The styled runs to paint over the text.
    public func styleRuns(_ palette: EditorPalette) -> [StyleRun] {
        ChordNotepadKit.styleRuns(spans: spans, playing: playing?.range, length: text.utf16.count,
                                  palette: palette)
    }

    // MARK: - The session's output

    /// Fold one of the session's outputs in.
    public mutating func receive(_ output: SessionOutput) -> EditorEffects {
        switch output {
        case .textEdited(let edit):
            if composing {
                pending.append(edit)
                return EditorEffects()
            }
            return applySessionEdit(edit)
        case .highlightState(let state):
            latestHighlight = state
            var effects = EditorEffects()
            effects.restyle = repaintHighlight()
            return effects
        case .playbackState(let state):
            latestPlayback = state
            return repaintPlaying()
        case .editorState(let state):
            let changed = state != editorState
            editorState = state
            var effects = EditorEffects()
            effects.restyle = changed
            return effects
        default:
            return EditorEffects()
        }
    }

    private mutating func applySessionEdit(_ edited: TextEdited) -> EditorEffects {
        var effects = EditorEffects()
        let unsent = text != syncedText
        let edit = edited.utf16(in: text)
        let before = selection
        let old = UTF16Text.substring(text, UTF16Range(edit.start, edit.end))
        spans = spans.shifted(by: TextChange(start: edit.start, oldEnd: edit.end,
                                             newEnd: edit.start + edit.replacement.utf16.count))
        text = UTF16Text.replacing(text, UTF16Range(edit.start, edit.end), with: edit.replacement)
        selection = edit.selection.clamped(to: text.utf16.count)
        if !unsent {
            syncedText = text
            identity = TextIdentity(clientToken: 0, revision: edited.textRevision)
        }
        switch edited.undo {
        case .reset:
            history.clear()
            documentsOpened += 1
            effects.documentOpened = true
        case .group, .plain:
            history.recordStep([EditHistory.Replacement(start: edit.start, old: old, new: edit.replacement)],
                               before: before, after: selection)
        }
        effects.viewEdits.append(ViewEdit(range: UTF16Range(edit.start, edit.end), replacement: edit.replacement))
        effects.selection = selection
        if unsent {
            // The user typed after the session last heard from the editor:
            // the editor's text wins, the session re-syncs to it.
            effects.commands.append(sendUserText())
        }
        _ = repaintHighlight()
        effects.merge(repaintPlaying())
        effects.restyle = true
        return effects
    }

    // MARK: - The view's input

    /// What to do with a change the user is about to make: refuse it while
    /// read-only, normalise what a paste (or dictation, or a drop) brings in.
    public func willReplace(_ range: UTF16Range, with replacement: String) -> ReplaceDecision {
        if readOnly { return .refuse }
        if needsNormalizing(replacement) { return .replace(normalizeSongText(replacement)) }
        return .allow
    }

    /// The view's text or selection changed (the user typed, pasted, moved
    /// the caret; `composing` while an input method has marked text). Moves
    /// the painted spans, records the undo step and sends the text.
    public mutating func viewChanged(text newText: String, selection newSelection: UTF16Range,
                                     composing nowComposing: Bool) -> EditorEffects {
        var effects = EditorEffects()
        let newSelection = newSelection.clamped(to: newText.utf16.count)
        if nowComposing && !composing {
            composing = true
            composeBase = (text, selection)
            history.seal()
        }
        if newText == text {
            if newSelection != selection && !composing { history.seal() }
            selection = newSelection
        } else {
            let oldUnits = Array(text.utf16)
            let newUnits = Array(newText.utf16)
            if let change = diffUnits(oldUnits, newUnits) {
                spans = spans.shifted(by: change)
                if !composing {
                    let replacement = EditHistory.Replacement(
                        start: change.start,
                        old: String(decoding: oldUnits[change.start..<change.oldEnd], as: UTF16.self),
                        new: String(decoding: newUnits[change.start..<change.newEnd], as: UTF16.self))
                    history.recordTyping(replacement, before: selection, after: newSelection)
                }
                effects.restyle = true
            }
            text = newText
            selection = newSelection
            effects.commands.append(contentsOf: syncCommands())
        }
        if !nowComposing && composing {
            effects.merge(endComposition())
        }
        return effects
    }

    private mutating func endComposition() -> EditorEffects {
        composing = false
        var effects = EditorEffects()
        if let base = composeBase, let change = diffTexts(base.text, text) {
            let oldUnits = Array(base.text.utf16)
            let newUnits = Array(text.utf16)
            history.recordStep([EditHistory.Replacement(
                start: change.start,
                old: String(decoding: oldUnits[change.start..<change.oldEnd], as: UTF16.self),
                new: String(decoding: newUnits[change.start..<change.newEnd], as: UTF16.self))],
                before: base.selection, after: selection)
        }
        composeBase = nil
        let waiting = pending
        pending = []
        for edit in waiting { effects.merge(applySessionEdit(edit)) }
        effects.restyle = true
        return effects
    }

    /// The commands that bring the session up to the view's text: a
    /// `set_text` when it hasn't got it yet. Run before a command that reads
    /// the text (play, save, a tap), as the desktop's `set_text` before Play.
    public mutating func syncCommands() -> [BridgeCommand] {
        text == syncedText ? [] : [sendUserText()]
    }

    private mutating func sendUserText() -> BridgeCommand {
        lastToken += 1
        identity = TextIdentity(clientToken: lastToken, revision: nil)
        syncedText = text
        return .setText(clientToken: lastToken, text: text)
    }

    // MARK: - Actions

    /// Run a ribbon button or a keyboard shortcut.
    public mutating func perform(_ action: EditorAction) -> EditorEffects {
        var effects = EditorEffects()
        switch action {
        case .undo:
            return undo()
        case .redo:
            return redo()
        case .fontBigger:
            effects.commands = [.stepFontSize(delta: 1)]
        case .fontSmaller:
            effects.commands = [.stepFontSize(delta: -1)]
        case .fontReset:
            effects.commands = [.resetFontSize()]
        case .setNotation(let notation):
            if notation != self.notation { effects.commands = [.setNotation(notation: notation)] }
        case .convertNotation:
            guard !readOnly else { return effects }
            let target = notation == "european" ? "american" : "european"
            effects.commands = syncCommands() + [.convertNotation(cursor: cursorCodePoint, target: target)]
        case .toggleComment, .duplicateLines, .deleteLines, .moveLinesUp, .moveLinesDown:
            guard !readOnly else { return effects }
            let (anchor, cursor) = selectionCodePoints
            let command: BridgeCommand
            switch action {
            case .toggleComment: command = .toggleComment(anchor: anchor, cursor: cursor)
            case .duplicateLines: command = .duplicateLines(anchor: anchor, cursor: cursor)
            case .deleteLines: command = .deleteLines(anchor: anchor, cursor: cursor)
            case .moveLinesUp: command = .moveLines(anchor: anchor, cursor: cursor, offset: -1)
            default: command = .moveLines(anchor: anchor, cursor: cursor, offset: 1)
            }
            effects.commands = syncCommands() + [command]
        }
        return effects
    }

    /// Undo the last step; the text it leaves goes to the session.
    public mutating func undo() -> EditorEffects {
        guard canUndo, let step = history.popUndo() else { return EditorEffects() }
        var effects = EditorEffects()
        for r in step.replacements.reversed() {
            effects.merge(replace(r.newRange, with: r.old))
        }
        selection = step.selectionBefore.clamped(to: text.utf16.count)
        effects.selection = selection
        effects.commands.append(contentsOf: syncCommands())
        return effects
    }

    /// Redo the last undone step.
    public mutating func redo() -> EditorEffects {
        guard canRedo, let step = history.popRedo() else { return EditorEffects() }
        var effects = EditorEffects()
        for r in step.replacements {
            effects.merge(replace(r.oldRange, with: r.new))
        }
        selection = step.selectionAfter.clamped(to: text.utf16.count)
        effects.selection = selection
        effects.commands.append(contentsOf: syncCommands())
        return effects
    }

    private mutating func replace(_ range: UTF16Range, with replacement: String) -> EditorEffects {
        var effects = EditorEffects()
        let r = range.clamped(to: text.utf16.count)
        spans = spans.shifted(by: TextChange(start: r.start, oldEnd: r.end, newEnd: r.start + replacement.utf16.count))
        text = UTF16Text.replacing(text, r, with: replacement)
        effects.viewEdits.append(ViewEdit(range: r, replacement: replacement))
        effects.restyle = true
        return effects
    }

    /// A tap on the chord at UTF-16 offset `utf16`: the session plays it (and
    /// moves the playhead there), after the text is synced.
    public mutating func tap(at utf16: Int) -> [BridgeCommand] {
        syncCommands() + [.tapChordAt(offset: codePoint(utf16), rolled: false)]
    }

    /// The code-point offset of UTF-16 offset `utf16` in the current text.
    public func codePoint(_ utf16: Int) -> Int { OffsetMapper(text).toCodePoint(utf16) }

    /// The caret (selection end) in code points.
    public var cursorCodePoint: Int { codePoint(selection.end) }

    /// The selection as the session's `(anchor, cursor)` in code points. A
    /// UITextView selection has no direction: it starts at its anchor.
    public var selectionCodePoints: (anchor: Int, cursor: Int) {
        let mapper = OffsetMapper(text)
        return (mapper.toCodePoint(selection.start), mapper.toCodePoint(selection.end))
    }

    // MARK: - Painting

    private mutating func repaintHighlight() -> Bool {
        guard let state = latestHighlight, state != appliedHighlight || identity != appliedIdentity,
              identity.accepts(state), text == syncedText else { return false }
        let mapper = OffsetMapper(text)
        spans = state.spans.compactMap { span in
            let r = span.utf16Range(mapper)
            return r.isEmpty ? nil : PaintedSpan(r.start, r.end, span.kind)
        }
        appliedHighlight = state
        appliedIdentity = identity
        return true
    }

    private mutating func repaintPlaying() -> EditorEffects {
        var effects = EditorEffects()
        var now: PlayingChord?
        if let state = latestPlayback, let span = state.playingSpan {
            let r = span.utf16Range(OffsetMapper(text))
            now = PlayingChord(start: r.start, end: r.end, chordIndex: state.chordIndex, bar: state.bar)
        }
        if now != playing {
            playing = now
            effects.restyle = true
            effects.playingMoved = now != nil
        }
        return effects
    }
}

extension EditorModel {
    /// The editor as a recorded scene leaves it (the preview catalog), with
    /// `selection` (UTF-16) when given.
    public static func folding(_ outputs: [SessionOutput], selection: UTF16Range? = nil) -> EditorModel {
        var model = EditorModel()
        for output in outputs { _ = model.receive(output) }
        if let selection {
            _ = model.viewChanged(text: model.text, selection: selection, composing: false)
        }
        return model
    }
}

extension Fixture {
    /// The fixture folded into the editor's model.
    public func editorModel(selection: UTF16Range? = nil) throws -> EditorModel {
        EditorModel.folding(try outputs.map { try SessionOutput.decode(typeName: $0.typeName, json: $0.json) },
                            selection: selection)
    }
}
