package io.github.chibicitiberiu.chordnotepad.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import io.github.chibicitiberiu.chordnotepad.bridge.DocumentRef
import io.github.chibicitiberiu.chordnotepad.bridge.SessionCommands
import io.github.chibicitiberiu.chordnotepad.ui.editor.EditorController

/**
 * What the main screen's buttons, menus and shortcuts do: session commands,
 * with the editor's text sent first where the command reads it (the desktop
 * sends `set_text` before Play and the file commands too). Main thread.
 */
class MainActions(private val commands: SessionCommands, private val editor: EditorController) {
    // -- transport --------------------------------------------------------------

    /** Play from the top, pause or resume. */
    fun playPause() {
        editor.syncNow()
        commands.playPause()
    }

    /** Play from the cursor when idle (long-press on Play; the desktop's Shift+click). */
    fun playFromCursor() = commands.playPause(editor.cursorCodePoint())

    /** Stop. */
    fun stop() = commands.stop()

    // -- toolbar ----------------------------------------------------------------

    /** `american` or `european`. */
    fun setNotation(notation: String) = commands.setNotation(notation)

    /** A dragged tempo (the session clamps and snaps it). */
    fun setBpm(bpm: Double) = commands.setBpm(bpm)

    /** A typed tempo. */
    fun setBpmText(text: String) = commands.setBpmText(text)

    /** Tempo back to the default. */
    fun resetBpm() = commands.resetBpm()

    /** A dragged speed, in percent. */
    fun setMultiplierPct(pct: Double) = commands.setMultiplierPct(pct)

    /** A typed speed (`150`, `150%`, `1.5x`). */
    fun setMultiplierText(text: String) = commands.setMultiplierText(text)

    /** Speed back to 100 %. */
    fun resetMultiplier() = commands.resetMultiplier()

    /** The key for roman numerals. */
    fun setKey(key: String) = commands.setKey(key)

    /** The time signature. */
    fun setTimeSignature(beats: Int, unit: Int) = commands.setTimeSignature(beats, unit)

    /** Click track on or off. */
    fun toggleMetronome() = commands.toggleMetronome()

    // -- view -------------------------------------------------------------------

    /** Grow or shrink the editor font. */
    fun stepFontSize(delta: Int) = commands.stepFontSize(delta)

    /** The configured font size again. */
    fun resetFontSize() = commands.resetFontSize()

    // -- edit -------------------------------------------------------------------

    /** Undo the last edit in the editor. */
    @OptIn(ExperimentalFoundationApi::class)
    fun undo() = editor.state.undoState.undo()

    /** Redo. */
    @OptIn(ExperimentalFoundationApi::class)
    fun redo() = editor.state.undoState.redo()

    // -- files (the requests they raise are presented by the screen) -------------

    /** New document. */
    fun newDocument() {
        editor.syncNow()
        commands.newDocument()
    }

    /** Open a document (asks for it with a picker request). */
    fun openDocument() {
        editor.syncNow()
        commands.openDocument()
    }

    /** Open a recent document. */
    fun openRecent(ref: DocumentRef) {
        editor.syncNow()
        commands.openRecent(ref)
    }

    /** Save. */
    fun save() {
        editor.syncNow()
        commands.save()
    }

    /** Save under a new name. */
    fun saveAs() {
        editor.syncNow()
        commands.saveAs()
    }

    /** Export the song as MIDI. */
    fun exportMidi() {
        editor.syncNow()
        commands.exportMidi()
    }
}
