package io.github.chibicitiberiu.chordnotepad.ui.tools

import io.github.chibicitiberiu.chordnotepad.bridge.ScreenCommands
import io.github.chibicitiberiu.chordnotepad.bridge.Selection
import io.github.chibicitiberiu.chordnotepad.bridge.SessionCommands
import io.github.chibicitiberiu.chordnotepad.ui.editor.EditorController

/**
 * What ⋮ › Tools does: session commands with the editor's selection or
 * cursor in code points, the text sent first (the session reads it). The
 * dialogs that follow a request (Insert, Suggest Capo) are presented from
 * the pending request (`SessionRequests`). Main thread.
 *
 * @param selectionNow The editor's text and its selection in UTF-16 units.
 * @param cursorNow The editor's cursor in code points, after syncing the text.
 */
class ToolActions(
    private val commands: SessionCommands,
    /** The chord identifier's commands. */
    val screen: ScreenCommands,
    private val sync: () -> Unit,
    private val selectionNow: () -> Triple<CharSequence, Int, Int>,
    private val cursorNow: () -> Int,
) {
    /** Over the app's editor. */
    constructor(commands: SessionCommands, screen: ScreenCommands, editor: EditorController) : this(
        commands = commands,
        screen = screen,
        sync = editor::syncNow,
        selectionNow = { Triple(editor.state.text, editor.state.selection.start, editor.state.selection.end) },
        cursorNow = editor::cursorCodePoint,
    )

    /**
     * The editor's selection in code points, or null for none (the whole
     * song), after syncing the text. Transpose asks when its dialog opens,
     * so the dialog can say which it will do.
     */
    fun selection(): Selection? {
        sync()
        val (text, start, end) = selectionNow()
        return selectionOf(text, start, end)
    }

    /** Transpose [selection] (null: the whole song) by [semitones]; one undo step. */
    fun transpose(semitones: Int, selection: Selection?) {
        sync()
        commands.transpose(semitones, selection)
    }

    /** Insert ▸ [kind]: ask for its fields; the directive goes in at the cursor. */
    fun insertDirective(kind: DirectiveKind) = commands.requestInsertDirective(kind.wire, cursorNow())

    /** Suggest Capo for the selection (or the whole song); the voicing is asked next. */
    fun suggestCapo() = commands.requestSuggestCapo(selection())

    /** Convert notation › [target] (`american`/`european`). */
    fun convertNotation(target: String) {
        sync()
        commands.convertNotation(target)
    }

    /** The chord identifier's Insert: [chord] and a space at the cursor. */
    fun insertChord(chord: String) = screen.insertChord(cursorNow(), chord)
}
