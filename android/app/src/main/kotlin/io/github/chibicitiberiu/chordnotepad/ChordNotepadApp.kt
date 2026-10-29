package io.github.chibicitiberiu.chordnotepad

import android.app.Application
import android.content.Context
import android.os.SystemClock

/** Application entry point: owns the [AppGraph]. */
class ChordNotepadApp : Application() {
    /** The app's long-lived objects. */
    lateinit var graph: AppGraph
        private set

    override fun onCreate() {
        super.onCreate()
        createdAtUptimeMs = SystemClock.uptimeMillis()
        graph = AppGraph(this).also { it.install() }
    }

    companion object {
        /** SystemClock.uptimeMillis() when Application.onCreate ran (spike measurements). */
        @Volatile
        var createdAtUptimeMs: Long = 0L
            private set
    }
}

/** The [AppGraph] of the app this context belongs to. */
val Context.appGraph: AppGraph get() = (applicationContext as ChordNotepadApp).graph
