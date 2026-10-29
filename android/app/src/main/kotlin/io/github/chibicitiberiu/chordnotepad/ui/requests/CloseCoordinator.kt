package io.github.chibicitiberiu.chordnotepad.ui.requests

import io.github.chibicitiberiu.chordnotepad.bridge.DiscardChoice
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * Turns the session's `CloseApproved` into "finish the activity", for the
 * Android Back button (the desktop's window close).
 *
 * Two things the session alone doesn't do:
 *  - **Discard**: when the user chose "Don't save", the session still holds the
 *    discarded text (the desktop quits, taking it along), so reopening the app
 *    would show it. The coordinator resets the session to a fresh untitled
 *    document first ([resetSession]).
 *  - **Rotation**: `CloseApproved` is a non-replaying event. The coordinator is
 *    app-scoped and always collecting, and turns it into [finishRequested], a
 *    state a late collector (a recreated activity) still sees once.
 *
 * Main thread.
 *
 * @param resetSession Puts the session in a new, empty, unmodified document
 *   without asking about unsaved changes.
 */
class CloseCoordinator(private val resetSession: () -> Unit) {
    private var discarded = false
    private val _finishRequested = MutableStateFlow(false)

    /** True from the moment the session approved the close until [consumeFinish]. */
    val finishRequested: StateFlow<Boolean> = _finishRequested

    /** Collect [closeApproved] in [scope] (app lifetime). */
    fun bind(scope: CoroutineScope, closeApproved: Flow<Unit>) {
        scope.launch { closeApproved.collect { onCloseApproved() } }
    }

    /** The user asked to close (Back); forgets an earlier discard. */
    fun onCloseRequested() {
        discarded = false
    }

    /** The unsaved-changes dialog was answered with [choice]. */
    fun onDiscardAnswered(choice: DiscardChoice) {
        discarded = choice == DiscardChoice.DISCARD
    }

    /** The session approved the close: reset after a discard, then ask the UI to finish. */
    fun onCloseApproved() {
        if (discarded) resetSession()
        discarded = false
        _finishRequested.value = true
    }

    /** The UI is finishing; stop reporting it. */
    fun consumeFinish() {
        _finishRequested.value = false
    }
}
