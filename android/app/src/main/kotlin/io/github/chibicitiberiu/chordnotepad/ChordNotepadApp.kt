package io.github.chibicitiberiu.chordnotepad

import android.app.Application
import android.os.SystemClock

/**
 * Application entry point.
 *
 * M3 moves Python start-up here (the PyHost singleton, docs/ANDROID_PORT_PLAN.md);
 * during the M2 spike it only records the process start time for measurements.
 */
class ChordNotepadApp : Application() {
    override fun onCreate() {
        super.onCreate()
        createdAtUptimeMs = SystemClock.uptimeMillis()
    }

    companion object {
        /** SystemClock.uptimeMillis() when Application.onCreate ran. */
        @Volatile
        var createdAtUptimeMs: Long = 0L
            private set
    }
}
