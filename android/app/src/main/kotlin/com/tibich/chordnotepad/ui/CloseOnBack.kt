package com.tibich.chordnotepad.ui

import androidx.activity.OnBackPressedCallback
import androidx.activity.OnBackPressedDispatcher

/**
 * Back on the main screen: with unsaved changes it asks first
 * ([onCloseRequested]); otherwise it lets the system handle Back as if this
 * callback weren't there (the activity goes to the background).
 *
 * It stays enabled the whole time the main screen shows, modified or not.
 * A callback that turns enabled while the keyboard is up (the first
 * keystroke makes the song modified) makes the dispatcher register its
 * window callback again, on top of the keyboard's, so Back would ask to
 * save and quit instead of only hiding the keyboard. Staying enabled keeps
 * the keyboard's callback the newest one. The cost is the predictive
 * back-to-home animation, which the system can't show for an enabled
 * callback.
 */
class CloseOnBackCallback(
    private val dispatcher: OnBackPressedDispatcher,
    private val isModified: () -> Boolean,
    private val onCloseRequested: () -> Unit,
) : OnBackPressedCallback(true) {
    override fun handleOnBackPressed() {
        if (isModified()) {
            onCloseRequested()
            return
        }
        // Step aside for this one event: the next callback, or the
        // activity's own Back (to the background), handles it.
        isEnabled = false
        try {
            dispatcher.onBackPressed()
        } finally {
            isEnabled = true
        }
    }
}
