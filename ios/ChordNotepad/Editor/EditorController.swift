import ChordNotepadKit
import SwiftUI
import UIKit
import os

/// The live editor: the kit's ``EditorModel`` on the main actor, the session's
/// commands out, and the text view it drives. Every input (the session's
/// output, the view's changes, the ribbon, key commands, undo) goes through
/// the model; its ``EditorEffects`` are applied here, so the view never
/// decides anything and never fights the user's typing:
///
/// - the session's edits are put into the text storage directly (never by
///   assigning `text`), with the view's own callbacks ignored meanwhile;
/// - styles are attributes on the text storage, repainted from the kit's
///   runs, and left alone while an input method composes;
/// - the typing attributes are reset after every change, so text typed after
///   a chord is plain until the next highlight says otherwise.
@MainActor
final class EditorController: ObservableObject {
    @Published private(set) var model = EditorModel()
    /// Where commands go (the session's `submit`).
    var submit: (BridgeCommand) -> Void = { _ in }
    /// Every command sent, by name (the session test checks there's no echo).
    private(set) var sentCommands: [String] = []

    private(set) weak var textView: EditorTextView?
    private var applying = false
    private var paintedFont: UIFont?
    /// A pinch on the text in progress.
    private var pinch = FontPinch()
    private var noticeTask: Task<Void, Never>?

    init() {}

    // MARK: - Inputs

    /// One of the session's outputs.
    func receive(_ output: SessionOutput) {
        apply(model.receive(output))
    }

    /// The view's text or selection changed (its delegate).
    func viewChanged() {
        guard !applying, let view = textView else { return }
        let selected = view.selectedRange
        let effects = model.viewChanged(text: view.text ?? "",
                                        selection: UTF16Range(selected.location, selected.location + selected.length),
                                        composing: view.markedTextRange != nil)
        apply(effects)
        if view.markedTextRange == nil {
            view.typingAttributes = baseAttributes(view)
            view.followCaretSideways()
        }
    }

    /// A ribbon button or a key command.
    func perform(_ action: EditorAction) {
        apply(model.perform(action))
    }

    /// One of the find bar's actions (the bar, the ribbon's Find, the app's
    /// shortcuts). Play mode finds without replacing; closing in Edit gives
    /// the text the keys back, as the desktop's Escape does.
    func find(_ action: FindAction) {
        let effects = model.find(action, canReplace: !playMode)
        apply(effects)
        if effects.findNotice {
            noticeTask?.cancel()
            noticeTask = Task { [weak self] in
                try? await Task.sleep(for: .seconds(TextFind.noticeSeconds))
                guard !Task.isCancelled else { return }
                self?.apply(self?.model.find(.clearNotice) ?? EditorEffects())
            }
        }
        if action == .close {
            if playMode || model.readOnly {
                textView?.host?.takeKeysIfFree()
            } else {
                textView?.becomeFirstResponder()
            }
        }
    }

    /// A pinch on the text: each new whole size goes to the session as a
    /// step (`step_font_size`), from the size when it began.
    func pinched(_ state: UIGestureRecognizer.State, scale: Double) {
        switch state {
        case .began:
            pinch.began(points: model.fontPoints)
            if let step = pinch.changed(scale: scale) { submitStep(step) }
        case .changed:
            if let step = pinch.changed(scale: scale) { submitStep(step) }
        default:
            pinch.ended()
        }
    }

    private func submitStep(_ step: Int) {
        var effects = EditorEffects()
        effects.commands = [.stepFontSize(delta: step)]
        apply(effects)
    }

    /// What to do with a change the user is about to make.
    func willReplace(_ range: NSRange, with text: String) -> ReplaceDecision {
        model.willReplace(UTF16Range(range.location, range.location + range.length), with: text)
    }

    /// Commands made from the model (a tool reads its text, selection and
    /// cursor, and may send the text first), sent as the editor's own.
    func run(_ body: (inout EditorModel) -> [BridgeCommand]) {
        var effects = EditorEffects()
        effects.commands = body(&model)
        apply(effects)
    }

    /// Put the caret at code point `codePoint` and give the text view the
    /// keyboard (Playback settings' Edit, after the switch to Edit mode).
    func placeCursor(codePoint: Int) {
        let utf16 = OffsetMapper(model.text).toUTF16(codePoint)
        DispatchQueue.main.async { [weak self] in
            guard let self, let view = self.textView else { return }
            view.selectedRange = NSRange(location: min(utf16, view.textStorage.length), length: 0)
            self.viewChanged()
            view.becomeFirstResponder()
            view.scrollRangeToVisible(view.selectedRange)
        }
    }

    /// Send the text if the session hasn't got it yet (before a command that reads it).
    func sync() {
        var effects = EditorEffects()
        effects.commands = model.syncCommands()
        apply(effects)
    }

    // MARK: - The view

    /// The text view now on screen: give it the model's text, selection and styles.
    func attach(_ view: EditorTextView) {
        textView = view
        view.editorUndo.canUndoNow = { [weak self] in self?.model.canUndo ?? false }
        view.editorUndo.canRedoNow = { [weak self] in self?.model.canRedo ?? false }
        view.editorUndo.onUndo = { [weak self] in self?.perform(.undo) }
        view.editorUndo.onRedo = { [weak self] in self?.perform(.redo) }
        view.onAction = { [weak self] in self?.perform($0) }
        view.onTraitsChanged = { [weak self] in
            guard let self, let view = self.textView else { return }
            self.restyle(view)
        }
        view.onPlayTap = { [weak self] in self?.playTapped(at: $0) }
        view.onScrub = { [weak self] in self?.scrubbed($0, at: $1) }
        view.onHold = { [weak self] in self?.held(at: $0) }
        view.onPinch = { [weak self] in self?.pinched($0, scale: $1) }
        view.host?.onCommand = { [weak self] in self?.onAppCommand?($0) }
        view.onWidthChanged = { [weak self] in self?.updateMarker() }
        view.markerScrub.grabs = { [weak self] in self?.scrubGrabs($0) ?? false }
        view.markerScrub.touchDown = { [weak self] in
            if self?.playMode == true { self?.playHandlers?.touched() }
        }
        view.setPlayMode(playMode, editable: !model.readOnly)
        applying = true
        let storage = view.textStorage
        storage.replaceCharacters(in: NSRange(location: 0, length: storage.length), with: model.text)
        view.selectedRange = nsRange(model.selection)
        applying = false
        restyle(view)
    }

    func detach(_ view: EditorTextView) {
        if textView === view { textView = nil }
    }

    // MARK: - Play mode

    /// The system menu's Open… and find actions, from the text view (the app's shortcuts).
    var onAppCommand: ((AppCommand) -> Void)?

    /// What Play mode's touches do (the app model's commands).
    var playHandlers: PlayHandlers?
    /// The text is frozen with the playhead marker (the Play tab).
    private(set) var playMode = false
    /// The session's playhead (UTF-16) and whether a song plays.
    private var sessionHead: Int?
    private var songPlaying = false
    /// Where a tap or a scrub put the marker, until the session's playhead moves.
    private var localHead: Int?
    /// Where a scrub has taken the marker; sent once, on release.
    private var scrubTo: Int?
    /// The text and spans the Play elements were made for.
    private var playElementsMadeFor: PlayElementsKey?

    private struct PlayElementsKey: Equatable {
        var text: String
        var spans: [PaintedSpan]
    }

    /// The playhead the marker shows (UTF-16).
    var playhead: Int? { localHead ?? sessionHead }

    /// The tab, the session's playhead (code points) and whether a song plays.
    func updatePlay(mode: AppMode, playhead: Int?, playing: Bool) {
        let head = playhead.map { OffsetMapper(model.text).toUTF16($0) }
        if head != sessionHead {
            sessionHead = head
            localHead = nil
        }
        songPlaying = playing
        let on = mode == .play
        if on != playMode {
            playMode = on
            // Play finds without the Replace row, as the desktop's Play workspace.
            apply(model.findModeChanged(canReplace: !on))
            if let view = textView {
                view.setPlayMode(on, editable: !model.readOnly)
                refreshPlayElements(view)
                if !on { scrubTo = nil }
                // The frozen text let the keys go: its host takes them, so the system
                // menu's Open… and find actions reach the app (``EditorHost/onCommand``).
                if on { view.host?.takeKeysIfFree() }
            }
        }
        updateMarker()
    }

    /// The chords the playhead can stop at, where they are in the text view.
    func chordBoxes() -> [ChordBox] {
        textView?.boxes(of: playableChords(model.spans)) ?? []
    }

    /// The box of the chord the marker sits before.
    func markerBox() -> ChordBox? {
        guard let view = textView, let chord = markerChord(playableChords(model.spans), playhead: playhead) else {
            return nil
        }
        return view.boxes(of: [chord]).first
    }

    private func updateMarker() {
        guard let view = textView else { return }
        view.showMarker(playMode ? markerBox() : nil, color: palette(view).primary.uiColor)
    }

    /// A tap in Play mode at `point` (the text view's content): a chord plays,
    /// a miss moves the playhead to the nearest chord unless a song plays.
    func playTapped(at point: CGPoint) {
        guard playMode else { return }
        playHandlers?.touched()
        guard let tap = resolveTap(chordBoxes(), Double(point.x), Double(point.y), slop: PlayTouch.chordSlop,
                                   nearestOnMiss: !songPlaying) else { return }
        localHead = tap.start
        updateMarker()
        playHandlers?.tap(tap)
    }

    /// Whether a drag from `point` scrubs the marker (not while a song plays).
    func scrubGrabs(_ point: CGPoint) -> Bool {
        playMode && !songPlaying
            && grabsMarker(markerBox(), Double(point.x), Double(point.y), grabWidth: PlayTouch.markerGrabWidth)
    }

    /// The scrub moved or ended: the marker follows chord by chord; the chord
    /// it ends on goes to the session once (`set_playhead` restarts playback).
    func scrubbed(_ state: UIGestureRecognizer.State, at point: CGPoint) {
        switch state {
        case .began, .changed:
            if let target = scrubTarget(chordBoxes(), current: playhead, Double(point.x), Double(point.y)) {
                localHead = target
                scrubTo = target
                updateMarker()
            }
        case .ended:
            if let scrubTo { playHandlers?.scrub(scrubTo) }
            scrubTo = nil
        default:
            scrubTo = nil
        }
    }

    /// A long-press at `point`: a red or faded directive there is explained.
    func held(at point: CGPoint) {
        guard playMode, let view = textView else { return }
        let boxes = view.boxes(of: explainableDirectives(model.spans))
        guard let box = explainableAt(boxes, Double(point.x), Double(point.y), slop: PlayTouch.chordSlop) else { return }
        UIImpactFeedbackGenerator(style: .medium).impactOccurred()
        playHandlers?.explain(box.start)
    }

    /// Show the session's explanation by its directive, or put it away (nil).
    func showHint(_ explained: ExplainedDirective?) {
        guard let view = textView else { return }
        guard playMode, let explained else {
            view.hideHint()
            return
        }
        let mapper = OffsetMapper(model.text)
        guard let rect = view.rect(of: UTF16Range(mapper.toUTF16(explained.start), mapper.toUTF16(explained.end)))
        else {
            view.hideHint()
            return
        }
        view.showHint(explained.card, at: rect,
                      colors: AppColors.forScheme(dark: view.traitCollection.userInterfaceStyle == .dark))
    }

    // MARK: - Effects

    private func apply(_ effects: EditorEffects) {
        for command in effects.commands {
            sentCommands.append(command.name)
            submit(command)
        }
        guard let view = textView else { return }
        applying = true
        defer { applying = false }
        if !effects.viewEdits.isEmpty {
            let storage = view.textStorage
            storage.beginEditing()
            for edit in effects.viewEdits {
                let range = edit.range.clamped(to: storage.length)
                storage.replaceCharacters(in: nsRange(range), with: edit.replacement)
            }
            storage.endEditing()
            if storage.string != model.text {
                // Never expected: the view and the model disagree. The model wins.
                Log.ui.error("Editor text out of step (\(storage.length) vs \(self.model.text.utf16.count) units); resyncing")
                storage.replaceCharacters(in: NSRange(location: 0, length: storage.length), with: model.text)
            }
        }
        if let selection = effects.selection {
            view.selectedRange = nsRange(selection.clamped(to: view.textStorage.length))
        }
        if effects.restyle || !effects.viewEdits.isEmpty {
            restyle(view)
        }
        if effects.documentOpened {
            view.scrollToStart()
        } else if effects.findMoved, let selection = effects.selection {
            // A match the find bar selected (the text may not have the keys): into view on both axes.
            view.follow(selection)
        } else if effects.playingMoved, let playing = model.playing {
            view.follow(playing.range)
        } else if effects.selection != nil {
            view.scrollRangeToVisible(view.selectedRange)
            view.followCaretSideways()
        }
    }

    /// Repaint the model's styles over the view's text (not while composing:
    /// changing marked text's attributes ends the composition).
    private func restyle(_ view: EditorTextView) {
        guard view.markedTextRange == nil else { return }
        let palette = palette(view)
        let font = font(view)
        if paintedFont != font {
            paintedFont = font
            view.font = font
        }
        EditorAppearance.paint(model.styleRuns(palette), on: view.textStorage, font: font, palette: palette)
        view.typingAttributes = EditorAppearance.baseAttributes(font: font, palette: palette)
        view.setWordWrap(model.wordWrap, joinPoints: model.joinPoints)
        view.textChanged()
        view.backgroundColor = palette.background.uiColor
        view.tintColor = palette.primary.uiColor
        let editable = !model.readOnly && !playMode
        if view.isEditable != editable { view.isEditable = editable }
        updateMarker()
        refreshPlayElements(view)
    }

    /// Play mode's VoiceOver elements: one per chord, activated as a tap on
    /// it, and the rest of each line as text (``playAccessibilityItems``).
    /// Made again only when the text or its spans change, so VoiceOver's
    /// focus stays put while a song plays; none in Edit.
    private func refreshPlayElements(_ view: EditorTextView) {
        guard playMode else {
            playElementsMadeFor = nil
            if view.playElements != nil {
                view.playElements = nil
                UIAccessibility.post(notification: .layoutChanged, argument: nil)
            }
            return
        }
        let key = PlayElementsKey(text: model.text, spans: model.spans)
        guard key != playElementsMadeFor || view.playElements == nil else { return }
        let changedMode = view.playElements == nil
        playElementsMadeFor = key
        view.playElements = playAccessibilityItems(text: model.text, spans: model.spans).map { item in
            PlayTextElement(item, in: view, current: { [weak self] in self?.markerChordStart == item.start },
                            activate: item.kind == .chord ? { [weak self] in self?.activateChord(item.start) } : nil)
        }
        if changedMode { UIAccessibility.post(notification: .layoutChanged, argument: nil) }
    }

    /// What VoiceOver's activation of a chord does: what a tap on it does.
    func activateChord(_ start: Int) {
        guard playMode else { return }
        playHandlers?.touched()
        localHead = start
        updateMarker()
        playHandlers?.tap(.onChord(start))
    }

    /// The chord the marker sits before (UTF-16 start).
    private var markerChordStart: Int? {
        markerChord(playableChords(model.spans), playhead: playhead)?.start
    }

    private func palette(_ view: UITextView) -> EditorPalette {
        EditorPalette.forScheme(dark: view.traitCollection.userInterfaceStyle == .dark)
    }

    private func font(_ view: UITextView) -> UIFont {
        EditorAppearance.font(kind: model.fontKind, points: model.fontPoints,
                              category: view.traitCollection.preferredContentSizeCategory)
    }

    private func baseAttributes(_ view: UITextView) -> [NSAttributedString.Key: Any] {
        EditorAppearance.baseAttributes(font: font(view), palette: palette(view))
    }

    private func nsRange(_ range: UTF16Range) -> NSRange {
        NSRange(location: range.start, length: range.length)
    }
}

/// The song text as a SwiftUI view: an ``EditorTextView`` (in its
/// ``EditorHost``) the ``EditorController`` drives. SwiftUI only places it;
/// its text never goes through `updateUIView`.
struct SongEditor: UIViewRepresentable {
    let controller: EditorController

    func makeCoordinator() -> Coordinator {
        Coordinator(controller: controller)
    }

    func makeUIView(context: Context) -> EditorHost {
        let host = EditorHost()
        host.textView.delegate = context.coordinator
        controller.attach(host.textView)
        return host
    }

    func updateUIView(_ host: EditorHost, context: Context) {}

    static func dismantleUIView(_ host: EditorHost, coordinator: Coordinator) {
        coordinator.controller.detach(host.textView)
    }

    /// The text view's delegate: every change and selection goes to the
    /// controller; a paste (or a drop, or dictation) that needs normalising
    /// is put in normalised instead.
    @MainActor
    final class Coordinator: NSObject, UITextViewDelegate {
        let controller: EditorController

        init(controller: EditorController) {
            self.controller = controller
        }

        func textView(_ textView: UITextView, shouldChangeTextIn range: NSRange,
                      replacementText text: String) -> Bool {
            switch controller.willReplace(range, with: text) {
            case .allow:
                return true
            case .refuse:
                return false
            case .replace(let normalized):
                if let start = textView.position(from: textView.beginningOfDocument, offset: range.location),
                   let end = textView.position(from: start, offset: range.length),
                   let textRange = textView.textRange(from: start, to: end) {
                    textView.replace(textRange, withText: normalized)
                    controller.viewChanged()
                }
                return false
            }
        }

        func textViewDidChange(_ textView: UITextView) {
            controller.viewChanged()
        }

        func textViewDidChangeSelection(_ textView: UITextView) {
            controller.viewChanged()
        }
    }
}
