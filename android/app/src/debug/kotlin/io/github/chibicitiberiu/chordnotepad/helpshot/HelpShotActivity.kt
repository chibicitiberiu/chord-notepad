package io.github.chibicitiberiu.chordnotepad.helpshot

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ActivityInfo
import android.os.Bundle
import android.util.Base64
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.ExperimentalComposeUiApi
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId
import androidx.compose.ui.text.TextRange
import androidx.core.content.ContextCompat
import io.github.chibicitiberiu.chordnotepad.AppGraph
import io.github.chibicitiberiu.chordnotepad.appGraph
import io.github.chibicitiberiu.chordnotepad.bridge.DocumentRef
import io.github.chibicitiberiu.chordnotepad.bridge.HostStatus
import io.github.chibicitiberiu.chordnotepad.bridge.PlaybackStatus
import io.github.chibicitiberiu.chordnotepad.bridge.RecentDocumentsState
import io.github.chibicitiberiu.chordnotepad.bridge.SessionOutput
import io.github.chibicitiberiu.chordnotepad.bridge.SpanKind
import io.github.chibicitiberiu.chordnotepad.ui.MainScreen
import io.github.chibicitiberiu.chordnotepad.ui.main.AppMode
import io.github.chibicitiberiu.chordnotepad.ui.requests.RequestPickers
import io.github.chibicitiberiu.chordnotepad.ui.theme.ChordNotepadTheme
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.filterNotNull
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.int
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/**
 * DEBUG BUILDS ONLY (src/debug): the main screen, set up from a scene for the
 * user guide's screenshots (android/tools/help_screenshots.py). It is
 * MainActivity's screen with Compose test tags exposed as resource ids (so
 * `uiautomator dump` finds the controls), no draft restore and no Quick Start
 * at launch, plus a list of actions applied once the session runs:
 *
 * ```
 * adb shell am start -S -n io.github.chibicitiberiu.chordnotepad/.helpshot.HelpShotActivity \
 *     --es orientation portrait --es actions_b64 <base64 of a JSON array of actions>
 * adb shell am broadcast -a io.github.chibicitiberiu.chordnotepad.HELP_SHOT \
 *     --es actions_b64 <...> --es token <id>
 * ```
 *
 * Each batch logs `HelpShot: done <token>` (tag `HelpShot`) when applied, or
 * `HelpShot: failed <token> <reason>`. The actions are in [apply]; they run
 * in the app scope, so a rotation doesn't cut a scene short. Format and use:
 * android/tools/HELP_SHOTS.md.
 */
class HelpShotActivity : ComponentActivity() {
    private val receiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            run(intent.getStringExtra("actions_b64"), intent.getStringExtra("token") ?: "broadcast")
        }
    }

    @OptIn(ExperimentalComposeUiApi::class)
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // The shot's orientation, whatever the launcher below asks for.
        when (intent.getStringExtra("orientation")) {
            "landscape" -> requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
            "portrait" -> requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
        }
        val graph = appGraph
        // The tour only opens when a scene asks for it (through the drawer).
        graph.quickStartShown = true
        graph.pyHost.start()
        RequestPickers(this, graph.repository.pendingRequest, graph.requests).attach()
        setContent {
            ChordNotepadTheme {
                Box(Modifier.fillMaxSize().semantics { testTagsAsResourceId = true }) {
                    MainScreen(graph, onCloseApproved = ::finish)
                }
            }
        }
        ContextCompat.registerReceiver(this, receiver, IntentFilter(ACTION), ContextCompat.RECEIVER_EXPORTED)
        if (savedInstanceState == null) run(intent.getStringExtra("actions_b64"), intent.getStringExtra("token") ?: "launch")
    }

    override fun onDestroy() {
        unregisterReceiver(receiver)
        super.onDestroy()
    }

    private fun run(actionsB64: String?, token: String) {
        val actions = actionsB64?.let {
            Json.parseToJsonElement(String(Base64.decode(it, Base64.DEFAULT), Charsets.UTF_8)).jsonArray
        } ?: JsonArray(emptyList())
        // App scope: an orientation change recreating the activity must not cancel a scene.
        val graph = appGraph
        graph.scope.launch {
            try {
                withTimeout(HOST_TIMEOUT_MS) { graph.repository.hostStatus.first { it == HostStatus.Running } }
                withTimeout(HOST_TIMEOUT_MS) { graph.repository.toolbar.filterNotNull().first() }
                for (a in actions) apply(graph, a.jsonObject)
                Log.i(TAG, "done $token")
            } catch (e: Exception) {
                Log.e(TAG, "failed $token ${e.javaClass.simpleName}: ${e.message}", e)
            }
        }
    }

    /**
     * One action, by its `do`:
     * - `song` {text, name?, location?, modified?}: the text as the open
     *   document (a draft restore; with a name it looks saved, without it's Untitled)
     * - `mode` {mode: edit|play}
     * - `sheet` {visible, view?}: the chord sheet
     * - `playhead` {chord}: the playhead on the n-th valid chord (0-based)
     * - `freeze` {chord, state: playing|paused}: play from that chord, pause
     *   as soon as it sounds; for `playing`, the states seen while it
     *   played are published again, so the screen shows it playing, silent
     * - `metronome` {on}
     * - `recent` {names: [..]}: the drawer's recent list (display only)
     * - `select` {text, occurrence?, cursor?}: select that text in the editor
     *   (or with cursor=true put the cursor after it)
     * - `wait` {ms}
     */
    private suspend fun apply(graph: AppGraph, a: JsonObject) {
        val repo = graph.repository
        val cmd = graph.commands
        fun str(k: String) = a[k]?.jsonPrimitive?.content
        when (val what = str("do")) {
            "song" -> {
                val text = str("text").orEmpty()
                val name = str("name")
                val ref = name?.let { DocumentRef("content://helpshot/document/$it", it, str("location") ?: "Downloads/$it") }
                cmd.restoreDraft(text, ref, a["modified"]?.jsonPrimitive?.booleanOrNull ?: false)
                withTimeout(STEP_TIMEOUT_MS) {
                    while (graph.editor.currentText() != text || repo.highlight.value == null) delay(50)
                }
                delay(300)
            }
            "mode" -> {
                val target = if (str("mode") == "edit") AppMode.EDIT else AppMode.PLAY
                if (graph.mode.select(target, repo.playback.value?.status)) cmd.stop()
            }
            "sheet" -> {
                a["visible"]?.jsonPrimitive?.boolean?.let(cmd::setChordSheetVisible)
                str("view")?.let(cmd::setChordSheetView)
                withTimeout(STEP_TIMEOUT_MS) {
                    repo.chordSheet.first { s ->
                        s != null && (a["visible"] == null || s.visible == a["visible"]!!.jsonPrimitive.boolean) &&
                            (str("view") == null || s.activeView == str("view"))
                    }
                }
            }
            "playhead" -> {
                val offset = chordStart(graph, a["chord"]!!.jsonPrimitive.int)
                cmd.setPlayhead(offset)
                withTimeout(STEP_TIMEOUT_MS) { repo.playback.first { it?.playheadOffset == offset } }
            }
            "freeze" -> freeze(graph, a["chord"]!!.jsonPrimitive.int, str("state") ?: "playing")
            "metronome" -> {
                val on = a["on"]!!.jsonPrimitive.boolean
                if (repo.toolbar.value?.metronome != on) cmd.toggleMetronome()
                withTimeout(STEP_TIMEOUT_MS) { repo.toolbar.first { it?.metronome == on } }
            }
            "recent" -> {
                val names = a["names"]!!.jsonArray.map { it.jsonPrimitive.content }
                repo.publish(
                    RecentDocumentsState(names.map { DocumentRef("content://helpshot/document/$it", it, "Downloads/$it") }),
                )
            }
            "select" -> {
                val text = graph.editor.currentText()
                val needle = str("text")!!
                var at = -1
                repeat((a["occurrence"]?.jsonPrimitive?.intOrNull ?: 0) + 1) { at = text.indexOf(needle, at + 1) }
                require(at >= 0) { "\"$needle\" not in the text" }
                val cursor = a["cursor"]?.jsonPrimitive?.booleanOrNull == true
                graph.editor.state.edit {
                    selection = if (cursor) TextRange(at + needle.length) else TextRange(at, at + needle.length)
                }
            }
            "wait" -> delay(a["ms"]!!.jsonPrimitive.int.toLong())
            else -> error("unknown action $what")
        }
    }

    /** Start (code points) of the n-th valid chord in the highlight. */
    private fun chordStart(graph: AppGraph, n: Int): Int {
        val spans = graph.repository.highlight.value?.spans.orEmpty()
            .filter { it.kind == SpanKind.CHORD }
            .sortedBy { it.start }
        require(n in spans.indices) { "chord $n of ${spans.size}" }
        return spans[n].start
    }

    private suspend fun freeze(graph: AppGraph, chord: Int, state: String) {
        val repo = graph.repository
        val cmd = graph.commands
        val offset = chordStart(graph, chord)
        cmd.setPlayhead(offset)
        withTimeout(STEP_TIMEOUT_MS) { repo.playback.first { it?.playheadOffset == offset } }
        cmd.playPause()
        // Rendering the song comes first (the starting ring), then the chord sounds.
        val playing = withTimeout(RENDER_TIMEOUT_MS) {
            repo.playback.filterNotNull().first { it.status == PlaybackStatus.PLAYING && it.chordIndex != null }
        }
        val status = withTimeoutOrNull(2_000) { repo.status.filterNotNull().first { "Bar" in it.text } }
        val toolbar = repo.toolbar.value
        val voicing = repo.voicingMenu.value
        val sheet = withTimeoutOrNull(3_000) { repo.chordSheet.filterNotNull().first { !it.visible || it.currentIndex != null } }
            ?: repo.chordSheet.value
        cmd.pause()
        withTimeout(STEP_TIMEOUT_MS) { repo.playback.first { it?.status == PlaybackStatus.PAUSED } }
        delay(500)
        // The strip's chord: the one the text highlights. Playback started
        // from a playhead mid-song reports the strip's index one chord
        // ahead (seen on the emulator, 2026-10-30), so it is set from the
        // playback state, the same rendered-song index.
        val pausedSheet = (repo.chordSheet.value ?: sheet)?.copy(currentIndex = playing.chordIndex)
        if (state == "playing") {
            listOfNotNull<SessionOutput>(toolbar, voicing, pausedSheet, status, playing).forEach(repo::publish)
        }
        Log.i(
            TAG,
            "froze at chord ${playing.chordIndex} (sheet ${sheet?.currentIndex} -> ${pausedSheet?.currentIndex}): ${status?.text}",
        )
    }

    private companion object {
        const val TAG = "HelpShot"
        const val ACTION = "io.github.chibicitiberiu.chordnotepad.HELP_SHOT"
        // A first start after an install unpacks Python first.
        const val HOST_TIMEOUT_MS = 180_000L
        const val STEP_TIMEOUT_MS = 20_000L
        const val RENDER_TIMEOUT_MS = 60_000L
    }
}
