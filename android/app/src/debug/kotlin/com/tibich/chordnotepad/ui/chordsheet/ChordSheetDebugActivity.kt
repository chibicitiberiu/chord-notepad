package com.tibich.chordnotepad.ui.chordsheet

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.tibich.chordnotepad.appGraph
import com.tibich.chordnotepad.lifecycle.LaunchKind
import com.tibich.chordnotepad.bridge.HostStatus

/**
 * DEBUG BUILDS ONLY (src/debug): the chord sheet pane on its own, with the
 * sample song (examples/02_american_complete.txt, copied into debug builds' assets
 * as debug/sample.txt) loaded
 * into the session, for emulator checks:
 *
 * ```
 * adb shell am start -n com.tibich.chordnotepad/.ui.chordsheet.ChordSheetDebugActivity \
 *     --ei height 240 --es view staff --es voicing guitar:standard
 * ```
 */
class ChordSheetDebugActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val graph = appGraph
        graph.pyHost.start()
        // A debug screen: a later MainActivity in this process shows no startup screen.
        graph.reportLaunch(LaunchKind.RESTORE, intent)
        val heightDp = intent.getIntExtra("height", 240)
        val view = intent.getStringExtra("view")
        val voicing = intent.getStringExtra("voicing")
        val sample = assets.open("debug/sample.txt").use { it.readBytes().decodeToString() }

        setContent {
            val host by graph.repository.hostStatus.collectAsState()
            val playback by graph.repository.playback.collectAsState()
            val status by graph.repository.status.collectAsState()
            LaunchedEffect(host) {
                if (host == HostStatus.Running) {
                    voicing?.let(graph.commands::setVoicing)
                    graph.commands.setText(sample, 1)
                    graph.commands.setChordSheetVisible(true)
                    view?.let(graph.commands::setChordSheetView)
                }
            }
            MaterialTheme {
                Surface(Modifier.fillMaxSize()) {
                    Column(Modifier.fillMaxSize().safeDrawingPadding(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Chord sheet (debug): $host", Modifier.padding(8.dp))
                        Text("${playback?.status ?: "-"} bar ${playback?.bar ?: 0}  ${status?.text.orEmpty()}", Modifier.padding(horizontal = 8.dp))
                        Row(Modifier.padding(horizontal = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(onClick = { graph.commands.playPause() }) { Text("Play/Pause") }
                            OutlinedButton(onClick = graph.commands::stop) { Text("Stop") }
                        }
                        ChordSheetPane(graph.pyHost, Modifier.fillMaxWidth().height(heightDp.dp))
                    }
                }
            }
        }
    }
}
