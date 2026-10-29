package io.github.chibicitiberiu.chordnotepad.ui.main

import io.github.chibicitiberiu.chordnotepad.bridge.DocumentState
import io.github.chibicitiberiu.chordnotepad.bridge.PlaybackStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** The app bar's two tabs (docs/design/android-ui-spec.md, "Modes"). */
enum class AppMode {
    /** Editable text, the editing ribbon, no chord sheet. */
    EDIT,

    /** Frozen text with the playhead, the player, the chord sheet. */
    PLAY,
}

/**
 * Which tab is open. App-scoped (`AppGraph.mode`), so a rotation keeps it.
 * Main thread.
 *
 * - The first document the session reports decides the start: a saved one
 *   opens in Play, an untitled one in Edit.
 * - After the user asks to open a document ([expectOpen]), the document
 *   that then arrives opens in Play; after New ([expectNew]), the empty one
 *   opens in Edit. Saving (which can change the document too) never switches.
 * - Switching to Edit while a song plays or is paused stops it ([select]).
 */
class ModeController(initial: AppMode? = null) {
    private val _mode = MutableStateFlow(initial ?: AppMode.EDIT)
    private var decided = initial != null
    private var expecting: Expect = Expect.NONE
    private var lastDocument: String? = null

    private enum class Expect { NONE, OPEN, NEW }

    /** The open tab. */
    val mode: StateFlow<AppMode> = _mode.asStateFlow()

    /**
     * The user picked [target]. Returns true when playback must be stopped
     * first (Edit while a song plays or is paused; the session keeps the text
     * read-only until it stops).
     */
    fun select(target: AppMode, playback: PlaybackStatus?): Boolean {
        val stop = target == AppMode.EDIT && _mode.value == AppMode.PLAY &&
            playback != null && playback != PlaybackStatus.IDLE
        _mode.value = target
        decided = true
        return stop
    }

    /** Open… or a recent document was asked for. */
    fun expectOpen() {
        expecting = Expect.OPEN
    }

    /** New was asked for. */
    fun expectNew() {
        expecting = Expect.NEW
    }

    /** Save or Save As was asked for: a document change that follows isn't an open. */
    fun expectSave() {
        expecting = Expect.NONE
    }

    /** The session's document changed. */
    fun onDocument(doc: DocumentState) {
        val id = doc.documentId
        val changed = id != lastDocument
        lastDocument = id
        when {
            !decided -> {
                _mode.value = if (id != null) AppMode.PLAY else AppMode.EDIT
                decided = true
            }
            expecting == Expect.OPEN && changed && id != null -> {
                _mode.value = AppMode.PLAY
                expecting = Expect.NONE
            }
            expecting == Expect.NEW && id == null && !doc.isModified -> {
                _mode.value = AppMode.EDIT
                expecting = Expect.NONE
            }
        }
    }
}
