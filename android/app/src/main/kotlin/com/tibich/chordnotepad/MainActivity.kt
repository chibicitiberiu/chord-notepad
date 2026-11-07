package com.tibich.chordnotepad

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.tibich.chordnotepad.bridge.PickMode
import com.tibich.chordnotepad.lifecycle.DraftHook
import com.tibich.chordnotepad.lifecycle.DraftPolicy
import com.tibich.chordnotepad.lifecycle.LaunchRules
import com.tibich.chordnotepad.ui.MainScreen
import com.tibich.chordnotepad.ui.main.AppMode
import com.tibich.chordnotepad.ui.requests.RequestPickers
import com.tibich.chordnotepad.ui.theme.ChordNotepadTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val graph = appGraph
        // After process death the app-scoped tab is gone; the saved one comes back.
        savedInstanceState?.getString(KEY_MODE)?.let { name ->
            AppMode.entries.firstOrNull { it.name == name }?.let(graph.mode::restore)
        }
        graph.pyHost.start()
        val restored = savedInstanceState != null
        val launch = intent // openFrom replaces it
        DraftHook(
            source = graph::currentDraft,
            onRestore = { draft ->
                // App scope: the restore must not die with this activity.
                graph.queueDocumentWork { DraftPolicy.restore(draft, graph.documents::refFor, graph.commands) }
            },
        ).attach(savedStateRegistry)
        // After the draft restore, so a restored draft can't replace the file.
        openFrom(launch, restored)
        graph.reportLaunch(LaunchRules.classify(restored, launch?.action, launch?.flags ?: 0), launch)
        RequestPickers(this, graph.repository.pendingRequest, graph.requests).attach()

        setContent { ChordNotepadTheme { MainScreen(graph, onCloseApproved = ::finish) } }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        outState.putString(KEY_MODE, appGraph.mode.mode.value.name)
    }

    override fun onResume() {
        super.onResume()
        // A purchase may have completed or been refunded meanwhile.
        appGraph.supportBilling.refresh()
    }

    // singleTask: Open with while the app runs comes here, not to a new activity.
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        openFrom(intent, restored = false)
    }

    /**
     * Open the file an Open with [intent] carries, once: the intent is then
     * replaced, so a rotation doesn't open it again. The session asks about
     * unsaved changes first, as for File > Open. A file the grant doesn't let
     * the app write opens read-only (Save runs Save As).
     */
    private fun openFrom(intent: Intent?, restored: Boolean) {
        val uri = intent?.data
        if (!LaunchRules.shouldOpen(restored, intent?.action, intent?.flags ?: 0, uri?.scheme)) return
        setIntent(Intent(Intent.ACTION_MAIN))
        val graph = appGraph
        // The song lands in Play, over any page (P1); the session asks about
        // unsaved changes first.
        val id = uri.toString()
        graph.editor.syncNow()
        graph.mode.expectOpen(target = id, current = graph.repository.document.value)
        graph.queueDocumentWork {
            val ref = graph.documents.adopt(id, PickMode.OPEN)
            graph.commands.openDocument(ref, readOnly = !graph.documents.canWrite(id))
        }
    }

    private companion object {
        /** The Edit/Play tab, for a process that was killed (L13). */
        const val KEY_MODE = "chordnotepad.mode"
    }
}
