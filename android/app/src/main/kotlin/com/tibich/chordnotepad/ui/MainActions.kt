package com.tibich.chordnotepad.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import com.tibich.chordnotepad.bridge.DocumentRef
import com.tibich.chordnotepad.bridge.SessionCommands
import com.tibich.chordnotepad.ui.editor.EditorController
import com.tibich.chordnotepad.ui.main.ModeController

/**
 * What the main screen's buttons, drawer, sheets and shortcuts do: session
 * commands, with the editor's text sent first where the command reads it
 * (the desktop sends `set_text` before Play and the file commands too).
 * Opening and creating documents tell [mode] what to expect (existing songs
 * open in Play, new ones in Edit). Main thread.
 */
class MainActions(
    private val commands: SessionCommands,
    private val editor: EditorController,
    private val mode: ModeController = ModeController(),
) {
    // -- transport --------------------------------------------------------------

    /** Play from the playhead, pause or resume. */
    fun playPause() {
        editor.syncNow()
        commands.playPause()
    }

    /** ⏮: stop and put the playhead back on the first chord. */
    fun rewind() {
        editor.syncNow()
        commands.rewind()
    }

    /** Stop. */
    fun stop() = commands.stop()

    /** Move the playhead to the chord at UTF-16 offset [utf16] (silent). */
    fun setPlayhead(utf16: Int) {
        editor.syncNow()
        commands.setPlayhead(editor.codePointAt(utf16))
    }

    /** A tapped chord at UTF-16 offset [utf16]: the playhead goes there and it sounds. */
    fun tapChord(utf16: Int) = editor.tapAt(utf16)

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

    // -- playback menu ----------------------------------------------------------

    /** Playback › Voicing: a `VoicingMenuState` item value. */
    fun setVoicing(voicing: String) = commands.setVoicing(voicing)

    /** Playback › Instrument: a General MIDI program. */
    fun setInstrument(program: Int) = commands.setInstrument(program)

    // -- view -------------------------------------------------------------------

    /** Grow or shrink the editor font. */
    fun stepFontSize(delta: Int) = commands.stepFontSize(delta)

    /** The configured font size again. */
    fun resetFontSize() = commands.resetFontSize()

    /** View › Font…: the family to configure and the size in points. */
    fun setFont(family: String, size: Int) = commands.setFont(family, size)

    /** The player's ▭: show or hide the chord sheet. */
    fun setChordSheetVisible(visible: Boolean) = commands.setChordSheetVisible(visible)

    // -- song defaults --------------------------------------------------------------

    /** Write the starting values no directive sets into the top of the song. */
    fun writeSongDefaults() {
        editor.syncNow()
        commands.writeSongDefaults()
    }

    // -- edit -------------------------------------------------------------------

    /** Undo the last edit in the editor. */
    @OptIn(ExperimentalFoundationApi::class)
    fun undo() = editor.state.undoState.undo()

    /** Redo. */
    @OptIn(ExperimentalFoundationApi::class)
    fun redo() = editor.state.undoState.redo()

    // -- files (the requests they raise are presented by the screen) -------------

    /** New document (it opens in Edit). */
    fun newDocument() {
        editor.syncNow()
        mode.expectNew()
        commands.newDocument()
    }

    /** Open a document (asks for it with a picker request; it opens in Play). */
    fun openDocument() {
        editor.syncNow()
        mode.expectOpen()
        commands.openDocument()
    }

    /** Open a recent document (in Play). */
    fun openRecent(ref: DocumentRef) {
        editor.syncNow()
        mode.expectOpen()
        commands.openRecent(ref)
    }

    /** Save. */
    fun save() {
        editor.syncNow()
        mode.expectSave()
        commands.save()
    }

    /** Save under a new name. */
    fun saveAs() {
        editor.syncNow()
        mode.expectSave()
        commands.saveAs()
    }

    /** Save As, suggesting [name] (after a rename the storage refused). */
    fun saveAs(name: String) {
        editor.syncNow()
        mode.expectSave()
        commands.saveAs(name)
    }

    /** Rename the document to [name] (typed without the extension). */
    fun rename(name: String) = commands.renameDocument(name)

    /** Export the song as MIDI. */
    fun exportMidi() {
        editor.syncNow()
        commands.exportMidi()
    }

    /**
     * Ask to close (Back with unsaved changes; the desktop's window close):
     * the session asks about the changes, then answers with `CloseApproved`.
     */
    fun requestClose() {
        editor.syncNow()
        commands.requestClose()
    }
}
