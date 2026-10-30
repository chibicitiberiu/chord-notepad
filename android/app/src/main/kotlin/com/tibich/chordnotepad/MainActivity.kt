package com.tibich.chordnotepad

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.tibich.chordnotepad.lifecycle.DraftHook
import com.tibich.chordnotepad.lifecycle.DraftPolicy
import com.tibich.chordnotepad.spike.SpikeScreen
import com.tibich.chordnotepad.ui.MainScreen
import com.tibich.chordnotepad.ui.requests.RequestPickers
import com.tibich.chordnotepad.ui.theme.ChordNotepadTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // M2 spike screen (throwaway), for scripted measurements over adb:
        // `--es spike_auto <mode>` or `--ez spike true`. It drives Python on
        // its own, so the session isn't started.
        val auto = intent?.getStringExtra("spike_auto")
        if (auto != null || intent?.getBooleanExtra("spike", false) == true) {
            setContent { SpikeScreen(autoRun = auto, onFullyDrawn = { reportFullyDrawn() }) }
            return
        }

        val graph = appGraph
        graph.pyHost.start()
        DraftHook(
            source = graph::currentDraft,
            onRestore = { draft ->
                // App scope: the restore must not die with this activity.
                graph.scope.launch(Dispatchers.IO) {
                    DraftPolicy.restore(draft, graph.documents::refFor, graph.commands)
                }
            },
        ).attach(savedStateRegistry)
        RequestPickers(this, graph.repository.pendingRequest, graph.requests).attach()

        setContent { ChordNotepadTheme { MainScreen(graph, onCloseApproved = ::finish) } }
    }
}
