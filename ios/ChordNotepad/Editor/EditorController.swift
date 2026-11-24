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

    /// What to do with a change the user is about to make.
    func willReplace(_ range: NSRange, with text: String) -> ReplaceDecision {
        model.willReplace(UTF16Range(range.location, range.location + range.length), with: text)
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
        if view.isEditable == model.readOnly { view.isEditable = !model.readOnly }
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

/// The song text as a SwiftUI view: an ``EditorTextView`` the
/// ``EditorController`` drives. SwiftUI only places it; its text never goes
/// through `updateUIView`.
struct SongEditor: UIViewRepresentable {
    let controller: EditorController

    func makeCoordinator() -> Coordinator {
        Coordinator(controller: controller)
    }

    func makeUIView(context: Context) -> EditorTextView {
        let view = EditorTextView()
        view.delegate = context.coordinator
        controller.attach(view)
        return view
    }

    func updateUIView(_ view: EditorTextView, context: Context) {}

    static func dismantleUIView(_ view: EditorTextView, coordinator: Coordinator) {
        coordinator.controller.detach(view)
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
