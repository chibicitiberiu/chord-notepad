import ChordNotepadKit
import Foundation
import UIKit

/// The live editor check (CI's `-CNScreen editor` and the session test):
/// type into the real text view through UIKit's own input path
/// (`insertText`, which calls the view's delegate as the keyboard does), then
/// see the session answer with a `HighlightState` for the editor's own
/// client token.
@MainActor
enum EditorScript {
    /// The quick-start song's first chord line; the typing goes at its end.
    static let line = "C        C/E      F      C"
    /// A long chord line: unwrapped (the default), it runs past the screen's
    /// right edge, so the screenshot shows the sideways scroll.
    static let typed = "      D/F#    G7sus4    Bb    Eb/G    Abmaj7    Db    Gb    B7    E"
    /// The chords in ``typed``, as the session should find them.
    static let typedChords = ["D/F#", "G7sus4", "Bb", "Eb/G", "Abmaj7", "Db", "Gb", "B7", "E"]

    /// Put the caret at the end of ``line`` and type ``typed``. False when the
    /// view or the line isn't there.
    static func type(into editor: EditorController) -> Bool {
        guard let view = editor.textView else { return false }
        let text = editor.model.text as NSString
        let found = text.range(of: line)
        guard found.location != NSNotFound else { return false }
        _ = view.becomeFirstResponder()
        view.selectedRange = NSRange(location: NSMaxRange(found), length: 0)
        // The delegate reports both; when it already has, these do nothing.
        editor.viewChanged()
        view.insertText(typed)
        editor.viewChanged()
        if !editor.model.text.contains(line + typed), let range = view.selectedTextRange {
            // Not the first responder (a test's window has no scene): the
            // text input protocol's replace, which also calls the delegate.
            view.replace(range, withText: typed)
            editor.viewChanged()
        }
        return editor.model.text.contains(line + typed)
    }

    /// The chords inside the typed text that the editor paints now.
    static func paintedChords(_ editor: EditorController) -> [String] {
        let text = editor.model.text as NSString
        let found = text.range(of: line + typed)
        guard found.location != NSNotFound else { return [] }
        let typedStart = found.location + (line as NSString).length
        return editor.model.spans
            .filter { $0.kind == .chord && $0.start >= typedStart && $0.end <= NSMaxRange(found) }
            .map { text.substring(with: NSRange(location: $0.start, length: $0.end - $0.start)) }
    }

    /// Wait until the session's highlight of the editor's own text is painted
    /// with every typed chord.
    static func waitForHighlight(_ editor: EditorController, timeout: Duration) async -> Bool {
        let deadline = ContinuousClock.now + timeout
        while ContinuousClock.now < deadline {
            if passed(editor) { return true }
            try? await Task.sleep(for: .milliseconds(50))
        }
        return passed(editor)
    }

    private static func passed(_ editor: EditorController) -> Bool {
        editor.model.identity.clientToken > 0 && editor.model.highlightedIdentity == editor.model.identity
            && paintedChords(editor) == typedChords
    }

    /// `Diagnostics/editor.json`.
    struct Report: Codable {
        var ok: Bool
        var typed: Bool
        var clientToken: Int
        var highlightedToken: Int?
        var paintedChords: [String]
        var setTextCount: Int
        var textLength: Int
        var wordWrap: Bool
        var contentWidth: Double
        var viewWidth: Double
        var problems: [String]
    }

    static func report(_ editor: EditorController, typed: Bool, highlighted: Bool) -> Report {
        var problems: [String] = []
        if !typed { problems.append("the text view or the quick-start song's first chord line wasn't there") }
        if typed && !highlighted { problems.append("no highlight of the typed chords for the editor's token") }
        let setTexts = editor.sentCommands.filter { $0 == "set_text" }.count
        if typed && setTexts == 0 { problems.append("no set_text was sent") }
        if let view = editor.textView, view.text != editor.model.text {
            problems.append("the text view's text differs from the model's")
        }
        let view = editor.textView
        return Report(ok: problems.isEmpty, typed: typed, clientToken: editor.model.identity.clientToken,
                      highlightedToken: editor.model.highlightedIdentity?.clientToken,
                      paintedChords: paintedChords(editor), setTextCount: setTexts,
                      textLength: editor.model.text.utf16.count, wordWrap: editor.model.wordWrap,
                      contentWidth: Double(view?.contentSize.width ?? 0), viewWidth: Double(view?.bounds.width ?? 0),
                      problems: problems)
    }
}
