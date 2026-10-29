package io.github.chibicitiberiu.chordnotepad.bridge

import android.content.Context
import android.os.Looper
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

/** Starts Chaquopy once per process, off the main thread. */
object PythonRuntime {
    /**
     * Load the native audio libraries, then start Python if it isn't running.
     * Blocks for a second or two on a cold start.
     *
     * @throws IllegalStateException when called on the main thread.
     */
    @Synchronized
    fun ensureStarted(context: Context) {
        check(Looper.myLooper() != Looper.getMainLooper()) { "Python must not start on the main thread" }
        if (Python.isStarted()) return
        // Before Python: FluidSynth is opened by soname through ctypes, which
        // only finds it once the app's linker namespace has it (this also
        // pulls in liboboe, libsndfile and its codecs, libc++_shared).
        System.loadLibrary("fluidsynth")
        Python.start(AndroidPlatform(context.applicationContext))
    }
}
