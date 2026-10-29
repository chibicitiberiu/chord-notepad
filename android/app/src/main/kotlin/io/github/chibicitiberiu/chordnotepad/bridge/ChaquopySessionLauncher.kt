package io.github.chibicitiberiu.chordnotepad.bridge

import android.content.Context
import com.chaquo.python.Kwarg
import com.chaquo.python.PyObject
import com.chaquo.python.Python

/**
 * Starts the session through `chordnotepad_android.host.start`. The only
 * place outside the spike that holds a [PyObject].
 */
class ChaquopySessionLauncher(private val context: Context) : SessionLauncher {
    override fun launch(env: LaunchEnvironment, store: DocumentStoreBridge, sink: EventSink): SessionHandle {
        PythonRuntime.ensureStarted(context)
        val py = Python.getInstance()
        val audioOptions = py.builtins.callAttr(
            "dict",
            Kwarg("sample_rate", env.audio.sampleRate),
            Kwarg("frames_per_buffer", env.audio.framesPerBuffer),
            Kwarg("soundfont_path", env.audio.soundfontPath),
        )
        val handle = py.getModule(PythonEntry.MODULE).callAttr(
            PythonEntry.START, env.filesDir, env.nativeLibDir, store, sink, audioOptions,
        )
        return ChaquopySessionHandle(handle)
    }
}

private class ChaquopySessionHandle(private val handle: PyObject) : SessionHandle {
    override fun submit(command: String, argsJson: String) {
        handle.callAttr("submit", command, argsJson)
    }

    override fun chordSheetBuffer(height: Float): ByteArray? =
        handle.callAttr("chord_sheet_buffer", height)?.use { it.toJava(ByteArray::class.java) }

    override fun shutdown() {
        handle.callAttr("shutdown")
        handle.close()
    }
}
