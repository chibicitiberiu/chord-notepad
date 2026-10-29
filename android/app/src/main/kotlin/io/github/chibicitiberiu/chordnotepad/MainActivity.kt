package io.github.chibicitiberiu.chordnotepad

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import io.github.chibicitiberiu.chordnotepad.lifecycle.DraftHook
import io.github.chibicitiberiu.chordnotepad.lifecycle.DraftPolicy
import io.github.chibicitiberiu.chordnotepad.spike.SpikeScreen
import io.github.chibicitiberiu.chordnotepad.ui.PlaceholderScreen
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

        // M3 placeholder over the repository's states; M4 replaces it.
        setContent { PlaceholderScreen(graph, onCloseApproved = ::finish) }
    }
}
