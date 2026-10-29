package io.github.chibicitiberiu.chordnotepad.ui.identifier

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import io.github.chibicitiberiu.chordnotepad.bridge.IdentifierState
import io.github.chibicitiberiu.chordnotepad.bridge.ScreenCommands

/**
 * The chord identifier screen's own state over the session's
 * [IdentifierState]: the typed-notes field and the candidate the user picked.
 * The notes, candidates and messages all come from Python. Main thread.
 *
 * The field follows the session only after a key tap (`notes_text` is what
 * it should show then); while the user types there it keeps their text.
 *
 * @param commands The identifier's commands.
 * @param insertAtCursor Inserts a chord (and a space) at the editor's cursor
 *   (`insert_chord`, with the cursor in code points).
 * @param initialTyped The field's text kept across a rotation.
 * @param initialPicked The picked candidate kept across a rotation.
 */
class IdentifierModel(
    private val commands: ScreenCommands,
    private val insertAtCursor: (chord: String) -> Unit,
    initialTyped: String = "",
    initialPicked: String? = null,
) {
    /** What the typed-notes field shows. */
    var typed: String by mutableStateOf(initialTyped)
        private set

    /** The candidate picked in the list (played, and what Insert inserts), or null. */
    var picked: String? by mutableStateOf(initialPicked)
        private set

    private var followKeys = false

    /** The screen opened: start from no notes, as the desktop's fresh dialog does. */
    fun open() {
        typed = ""
        picked = null
        followKeys = false
        commands.identifierClear()
    }

    /** A new [IdentifierState] arrived. */
    fun onState(state: IdentifierState) {
        if (followKeys) {
            typed = state.notesText
            followKeys = false
        }
        if (picked != null && picked !in state.candidates) picked = null
    }

    /** Tap on a key: select or deselect it (a newly selected key sounds). */
    fun tapKey(key: PianoKey) {
        followKeys = true
        commands.identifierToggleNote(key.name, key.octave)
    }

    /** Long-press on a key: sound it without selecting it. */
    fun pressKey(key: PianoKey) = commands.playNote(key.name, key.octave)

    /** The user edited the typed-notes field. */
    fun type(text: String) {
        if (text == typed) return
        typed = text
        followKeys = false
        commands.identifierSetNotesText(text)
    }

    /** Clear: no notes, an empty field. */
    fun clear() {
        typed = ""
        picked = null
        followKeys = false
        commands.identifierClear()
    }

    /** Tap on a candidate: pick it and play it. */
    fun pick(chord: String) {
        picked = chord
        commands.playIdentifiedChord(chord)
    }

    /** Insert [chord] (default: the picked one) at the editor's cursor; nothing when none. */
    fun insert(chord: String? = picked) {
        val c = chord ?: return
        picked = c
        insertAtCursor(c)
    }
}
