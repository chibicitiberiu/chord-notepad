package io.github.chibicitiberiu.chordnotepad.spike

// M2 SPIKE CODE (throwaway). The real bridge is M3's PyHost + session events.

import android.content.Context
import android.media.AudioManager
import android.os.SystemClock
import android.util.Log
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import io.github.chibicitiberiu.chordnotepad.ChordNotepadApp
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors

const val TAG = "CNSPIKE"

/** All Python calls go through one dedicated thread; Main never calls Python. */
object SpikePython {
    val dispatcher: CoroutineDispatcher = Executors.newSingleThreadExecutor { r ->
        Thread(r, "python-dispatch")
    }.asCoroutineDispatcher()

    private lateinit var spike: PyObject

    suspend fun start(context: Context): JSONObject = withContext(dispatcher) {
        val app = context.applicationContext
        val t0 = SystemClock.elapsedRealtimeNanos()
        // Resolves liboboe, libsndfile (+codecs) and libc++_shared from the APK.
        System.loadLibrary("fluidsynth")
        val t1 = SystemClock.elapsedRealtimeNanos()
        if (!Python.isStarted()) Python.start(AndroidPlatform(app))
        val t2 = SystemClock.elapsedRealtimeNanos()
        val sf2 = copySoundfont(app)
        val t3 = SystemClock.elapsedRealtimeNanos()
        spike = Python.getInstance().getModule("chordnotepad_android.spike")
        val t4 = SystemClock.elapsedRealtimeNanos()
        val am = app.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        val rate = am.getProperty(AudioManager.PROPERTY_OUTPUT_SAMPLE_RATE)?.toIntOrNull() ?: 48000
        val frames = am.getProperty(AudioManager.PROPERTY_OUTPUT_FRAMES_PER_BUFFER)?.toIntOrNull() ?: 0
        val kt = JSONObject()
            .put("app_oncreate_to_start_ms", SystemClock.uptimeMillis() - ChordNotepadApp.createdAtUptimeMs)
            .put("load_fluidsynth_ms", (t1 - t0) / 1e6)
            .put("python_start_ms", (t2 - t1) / 1e6)
            .put("sf2_copy_ms", (t3 - t2) / 1e6)
            .put("spike_module_import_ms", (t4 - t3) / 1e6)
        val res = JSONObject(spike.callAttr("init", app.filesDir.path, sf2.path, rate, frames).toString())
        res.put("kotlin", kt)
        Log.i(TAG, "init ${res}")
        res
    }

    /** Copies the SoundFont asset to filesDir once (FluidSynth needs a real path). */
    private fun copySoundfont(context: Context): File {
        val dest = File(context.filesDir, "soundfont/GeneralUser-GS.sf2")
        if (dest.exists()) return dest
        dest.parentFile?.mkdirs()
        val tmp = File(dest.path + ".part")
        context.assets.open("soundfont/GeneralUser-GS.sf2").use { input ->
            tmp.outputStream().use { input.copyTo(it, 1 shl 16) }
        }
        tmp.renameTo(dest)
        return dest
    }

    suspend fun detect(text: String): JSONObject = withContext(dispatcher) {
        JSONObject(spike.callAttr("detect", text).toString())
    }

    suspend fun measureRender(): JSONObject = withContext(dispatcher) {
        JSONObject(spike.callAttr("measure_render").toString())
    }

    suspend fun playSong(clickNs: Long): JSONObject = withContext(dispatcher) {
        JSONObject(spike.callAttr("play_song", clickNs).toString())
    }

    suspend fun playDense(clickNs: Long, seconds: Long, metronome: Boolean, load: Boolean): JSONObject =
        withContext(dispatcher) {
            JSONObject(spike.callAttr("play_dense", clickNs, seconds, metronome, load).toString())
        }

    suspend fun setSwitchInterval(ms: Double): JSONObject = withContext(dispatcher) {
        JSONObject(spike.callAttr("set_switch_interval", ms).toString())
    }

    suspend fun playChordAt(codePointOffset: Int, clickNs: Long): JSONObject = withContext(dispatcher) {
        JSONObject(spike.callAttr("play_chord_at", codePointOffset, clickNs).toString())
    }

    suspend fun stop(): JSONObject = withContext(dispatcher) {
        JSONObject(spike.callAttr("stop").toString())
    }

    suspend fun report(): JSONObject = withContext(dispatcher) {
        JSONObject(spike.callAttr("report").toString())
    }

    suspend fun opBuffer(): JSONObject = withContext(dispatcher) {
        JSONObject(spike.callAttr("op_buffer").toString())
    }
}
