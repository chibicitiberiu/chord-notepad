package com.tibich.chordnotepad

import android.app.Application
import android.content.Context

/** Application entry point: owns the [AppGraph]. */
class ChordNotepadApp : Application() {
    /** The app's long-lived objects. */
    lateinit var graph: AppGraph
        private set

    override fun onCreate() {
        super.onCreate()
        graph = AppGraph(this).also { it.install() }
    }
}

/** The [AppGraph] of the app this context belongs to. */
val Context.appGraph: AppGraph get() = (applicationContext as ChordNotepadApp).graph
