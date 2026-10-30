package com.tibich.chordnotepad.spike

// M2 SPIKE CODE (throwaway): a text field with Python-driven chord highlighting
// and Play / Stop / Chord buttons, plus an "auto" mode driven by an intent
// extra so measurements can be scripted over adb. M4 replaces all of this.

import android.util.Log
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.input.OutputTransformation
import androidx.compose.foundation.text.input.rememberTextFieldState
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.drop
import kotlinx.coroutines.launch
import org.json.JSONObject

/** A highlight span in UTF-16 offsets (converted from Python code points). */
data class Span(val start: Int, val end: Int, val kind: String)

private val styles = mapOf(
    "chord" to SpanStyle(color = Color(0xFF0000FF), textDecoration = TextDecoration.Underline),
    "invalid" to SpanStyle(color = Color.Gray),
    "comment" to SpanStyle(color = Color.Gray),
    "directive" to SpanStyle(color = Color(0xFF8B4789)),
    "directive_invalid" to SpanStyle(color = Color.Red),
)

/** Python offsets are code points; Kotlin strings index UTF-16 units. */
private fun parseSpans(text: String, result: JSONObject): List<Span> {
    val arr = result.getJSONArray("spans")
    val cpCount = text.codePointCount(0, text.length)
    fun toUtf16(cp: Int): Int = text.offsetByCodePoints(0, cp.coerceIn(0, cpCount))
    return List(arr.length()) { i ->
        val s = arr.getJSONArray(i)
        Span(toUtf16(s.getInt(0)), toUtf16(s.getInt(1)), s.getString(2))
    }
}

@OptIn(FlowPreview::class)
@Composable
fun SpikeScreen(autoRun: String?, onFullyDrawn: () -> Unit) {
    val context = LocalContext.current
    val sample = remember {
        context.assets.open("spike/sample.txt").bufferedReader().use { it.readText() }
    }
    val state = rememberTextFieldState(sample)
    var spans by remember { mutableStateOf(emptyList<Span>()) }
    var status by remember { mutableStateOf("Starting Python…") }
    var ready by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    val highlight = remember {
        OutputTransformation {
            for (s in spans) {
                if (s.end <= length && s.start < s.end) {
                    styles[s.kind]?.let { addStyle(it, s.start, s.end) }
                }
            }
        }
    }

    LaunchedEffect(Unit) {
        val r = SpikePython.start(context)
        status = "Python ready (${r.optString("summary")})"
        ready = true
    }

    LaunchedEffect(ready) {
        if (!ready) return@LaunchedEffect
        val text0 = state.text.toString()
        val r0 = SpikePython.detect(text0)
        spans = parseSpans(text0, r0)
        status = "detect ${"%.1f".format(r0.getDouble("ms"))} ms, ${r0.getInt("chords")} chords"
        onFullyDrawn()
        if (autoRun != null) scope.launch { runAuto(autoRun, sample) { status = it } }
        snapshotFlow { state.text.toString() }.drop(1).debounce(300).collectLatest { text ->
            val r = SpikePython.detect(text)
            spans = parseSpans(text, r)
            status = "detect ${"%.1f".format(r.getDouble("ms"))} ms, ${r.getInt("chords")} chords"
        }
    }

    MaterialTheme {
        Surface(Modifier.fillMaxSize()) {
            Column(Modifier.fillMaxSize().safeDrawingPadding().padding(8.dp)) {
                Text("M2 spike (throwaway)", style = MaterialTheme.typography.labelSmall)
                Row {
                    Button(enabled = ready, onClick = {
                        val click = System.nanoTime()
                        scope.launch { status = "play: ${SpikePython.playSong(click)}" }
                    }) { Text("Play") }
                    Spacer(Modifier.width(4.dp))
                    Button(enabled = ready, onClick = {
                        scope.launch { status = "stop: ${SpikePython.stop()}" }
                    }) { Text("Stop") }
                    Spacer(Modifier.width(4.dp))
                    Button(enabled = ready, onClick = {
                        val click = System.nanoTime()
                        val text = state.text.toString()
                        val sel = state.selection.start.coerceIn(0, text.length)
                        val cp = text.codePointCount(0, sel)
                        scope.launch { status = "chord: ${SpikePython.playChordAt(cp, click)}" }
                    }) { Text("Chord") }
                    Spacer(Modifier.width(4.dp))
                    Button(enabled = ready, onClick = {
                        scope.launch { status = "report: ${SpikePython.report()}" }
                    }) { Text("Stats") }
                }
                Text(status, style = MaterialTheme.typography.bodySmall, maxLines = 4)
                BasicTextField(
                    state = state,
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    textStyle = TextStyle(fontFamily = FontFamily.Monospace, fontSize = 13.sp),
                    outputTransformation = highlight,
                )
            }
        }
    }
}

/**
 * Scripted measurement run, started with
 * `am start ... --es spike_auto <mode>:<seconds>[:metro][:load]` where mode is
 * `play` (the sample song) or `dense` (4 chords/s; `metro` unmutes the click,
 * `load` re-renders the sample on another Python thread meanwhile).
 */
private suspend fun runAuto(spec: String, sample: String, setStatus: (String) -> Unit) {
    val parts = spec.split(":")
    val mode = parts.getOrElse(0) { "play" }
    val seconds = parts.getOrNull(1)?.toLongOrNull() ?: 60L
    val metro = "metro" in parts
    val load = "load" in parts
    parts.firstOrNull { it.startsWith("si=") }?.let {
        Log.i(TAG, "AUTO switch ${SpikePython.setSwitchInterval(it.removePrefix("si=").toDouble())}")
    }
    delay(1500)
    val render = SpikePython.measureRender()
    Log.i(TAG, "AUTO render $render")
    val play = if (mode == "dense") {
        SpikePython.playDense(System.nanoTime(), seconds, metro, load)
    } else {
        SpikePython.playSong(System.nanoTime())
    }
    Log.i(TAG, "AUTO play $play")
    // The song renders on a background thread before the player starts.
    var waited = 0L
    while (waited < 20_000 && SpikePython.report().isNull("play_to_first_note_ms")) {
        delay(100)
        waited += 100
    }
    waited = 0L
    while (waited < seconds * 1000) {
        delay(1000)
        waited += 1000
        if (!SpikePython.report().optBoolean("playing", true)) break
    }
    val stopped = SpikePython.stop()
    val songReport = SpikePython.report()
    Log.i(TAG, "AUTO song-report $songReport stop=$stopped")
    delay(500)
    // Tap -> sound: the first chord of the song.
    val firstChord = sample.indexOf("G ")
    for (i in 0 until 5) {
        val chord = SpikePython.playChordAt(sample.codePointCount(0, firstChord), System.nanoTime())
        Log.i(TAG, "AUTO chord $chord")
        delay(700)
    }
    val ops = runCatching { SpikePython.opBuffer() }.getOrElse { JSONObject().put("error", it.toString()) }
    Log.i(TAG, "AUTO opbuffer $ops")
    val final = SpikePython.report()
    Log.i(TAG, "AUTO-DONE $final")
    setStatus("auto done: $final")
}
