package io.github.chibicitiberiu.chordnotepad.lifecycle

import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import io.github.chibicitiberiu.chordnotepad.bridge.SessionCommands

/**
 * Tells the session when the whole app goes to the background and back
 * (register on `ProcessLifecycleOwner`). On ON_STOP Python pauses playback
 * and saves the config, since the process may be killed any time after.
 */
class AppLifecycleHooks(private val commands: SessionCommands) : DefaultLifecycleObserver {
    override fun onStart(owner: LifecycleOwner) = commands.appForeground()

    override fun onStop(owner: LifecycleOwner) = commands.appBackground()
}
