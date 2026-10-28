package io.github.chibicitiberiu.chordnotepad

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import io.github.chibicitiberiu.chordnotepad.spike.SpikeScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        // M2 spike: the throwaway test screen. M4 replaces it with the real UI.
        val auto = intent?.getStringExtra("spike_auto")
        setContent {
            SpikeScreen(autoRun = auto, onFullyDrawn = { reportFullyDrawn() })
        }
    }
}
