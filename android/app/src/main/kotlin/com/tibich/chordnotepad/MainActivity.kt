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
import com.tibich.chordnotepad.ui.requests.RequestPickers
import com.tibich.chordnotepad.ui.theme.ChordNotepadTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val graph = appGraph
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
        val id = uri.toString()
        graph.queueDocumentWork {
            val ref = graph.documents.adopt(id, PickMode.OPEN)
            graph.commands.openDocument(ref, readOnly = !graph.documents.canWrite(id))
        }
    }
}
