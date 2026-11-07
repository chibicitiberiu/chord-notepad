package com.tibich.chordnotepad.ui.main

import com.tibich.chordnotepad.bridge.DocumentState
import com.tibich.chordnotepad.bridge.PlaybackStatus
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
 * - Every open that arrives after [expectOpen] counts in [opened], so the
 *   main screen can close a page (Settings, the User Guide…) over it: Open
 *   with from another app always lands on the song, in Play.
 */
class ModeController(initial: AppMode? = null) {
    private val _mode = MutableStateFlow(initial ?: AppMode.EDIT)
    private var decided = initial != null
    private var expecting: Expect = Expect.NONE
    private var lastDocument: String? = null
    private var lastModified = false

    private enum class Expect { NONE, OPEN, NEW }

    /** The open tab. */
    val mode: StateFlow<AppMode> = _mode.asStateFlow()

    private val _opened = MutableStateFlow(0)

    /** How many asked-for opens have arrived (see the class doc). */
    val opened: StateFlow<Int> = _opened.asStateFlow()

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

    /**
     * The tab saved with the activity, when the process was killed and is
     * coming back (L13: Play came back as Edit). It wins over the first
     * document's rule; in a process that already decided (a rotation) it's
     * ignored.
     */
    fun restore(saved: AppMode) {
        if (decided) return
        _mode.value = saved
        decided = true
    }

    /**
     * Open… or a recent document was asked for; with [target], the
     * document Open with names. When that's the [current] one, unmodified,
     * the session has nothing to change (no new document state comes), so it
     * counts as opened now.
     */
    fun expectOpen(target: String? = null, current: DocumentState? = null) {
        if (target != null && current != null && current.documentId == target && !current.isModified) {
            _mode.value = AppMode.PLAY
            decided = true
            expecting = Expect.NONE
            _opened.value++
            return
        }
        expecting = Expect.OPEN
    }

    /** New was asked for. */
    fun expectNew() {
        expecting = Expect.NEW
    }

    /** Save, Save As or Rename was asked for: a document change that follows isn't an open. */
    fun expectSave() {
        expecting = Expect.NONE
    }

    /** The session's document changed. */
    fun onDocument(doc: DocumentState) {
        val id = doc.documentId
        val changed = id != lastDocument
        // The same song again after "Don't save": its changes are gone.
        val reread = !changed && lastModified && !doc.isModified
        lastDocument = id
        lastModified = doc.isModified
        when {
            !decided -> {
                _mode.value = if (id != null) AppMode.PLAY else AppMode.EDIT
                decided = true
                // A cold start from Open with: this is the open that was asked for.
                if (expecting == Expect.OPEN && id != null) {
                    expecting = Expect.NONE
                    _opened.value++
                }
            }
            expecting == Expect.OPEN && (changed || reread) && id != null -> {
                _mode.value = AppMode.PLAY
                expecting = Expect.NONE
                _opened.value++
            }
            expecting == Expect.NEW && id == null && !doc.isModified -> {
                _mode.value = AppMode.EDIT
                expecting = Expect.NONE
            }
        }
    }
}
