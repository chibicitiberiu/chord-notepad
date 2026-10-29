package io.github.chibicitiberiu.chordnotepad.ui

// M3 PLACEHOLDER: shows the session's states and answers its requests just
// enough to exercise the bridge, SAF pickers and the document flows. The real
// UI (editor, toolbar, chord sheet, dialogs) is M4.

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import io.github.chibicitiberiu.chordnotepad.AppGraph
import io.github.chibicitiberiu.chordnotepad.bridge.CapoChoiceRequest
import io.github.chibicitiberiu.chordnotepad.bridge.ConfirmDiscardRequest
import io.github.chibicitiberiu.chordnotepad.bridge.DiscardChoice
import io.github.chibicitiberiu.chordnotepad.bridge.InsertDirectiveRequest
import io.github.chibicitiberiu.chordnotepad.bridge.PickDocumentRequest
import io.github.chibicitiberiu.chordnotepad.files.MIDI_MIME_TYPE
import io.github.chibicitiberiu.chordnotepad.files.PickerLaunch
import io.github.chibicitiberiu.chordnotepad.files.SONG_MIME_TYPE
import io.github.chibicitiberiu.chordnotepad.files.pickerFor
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

/** The M3 placeholder: the repository's states, a few commands, minimal request handling. */
@Composable
fun PlaceholderScreen(graph: AppGraph, onCloseApproved: () -> Unit) {
    val repo = graph.repository
    val commands = graph.commands
    val host by repo.hostStatus.collectAsState()
    val document by repo.document.collectAsState()
    val status by repo.status.collectAsState()
    val playback by repo.playback.collectAsState()
    val toolbar by repo.toolbar.collectAsState()
    val highlight by repo.highlight.collectAsState()
    val recent by repo.recentDocuments.collectAsState()
    val pending by repo.pendingRequest.collectAsState()
    val errors = remember { mutableStateListOf<String>() }

    LaunchedEffect(Unit) {
        repo.errors.collect { e -> errors.add(0, e.toString()); if (errors.size > 5) errors.removeAt(5) }
    }
    LaunchedEffect(Unit) { repo.closeApproved.collect { onCloseApproved() } }

    // Answer a picker: adopt the URI off Main (provider I/O), then respond.
    fun answerPick(uri: Uri?) {
        val request = repo.pendingRequest.value as? PickDocumentRequest ?: return
        graph.scope.launch(Dispatchers.IO) {
            val ref = uri?.let { graph.documents.adopt(it.toString(), request.mode) }
            commands.respondPick(request.requestId, ref)
        }
    }
    val openPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument(), ::answerPick)
    val savePicker = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument(SONG_MIME_TYPE), ::answerPick)
    val midiPicker = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument(MIDI_MIME_TYPE), ::answerPick)
    // Survives rotation, so a recreated screen doesn't open the same picker twice.
    var launchedPicker by rememberSaveable { mutableIntStateOf(-1) }

    LaunchedEffect(pending) {
        when (val r = pending) {
            is PickDocumentRequest -> if (launchedPicker != r.requestId) {
                launchedPicker = r.requestId
                when (val launch = pickerFor(r)) {
                    is PickerLaunch.Open -> openPicker.launch(launch.mimeTypes.toTypedArray())
                    is PickerLaunch.Create ->
                        (if (launch.mimeType == MIDI_MIME_TYPE) midiPicker else savePicker).launch(launch.suggestedName)
                }
            }
            // Not in the placeholder (M4/M5 dialogs): cancel.
            is CapoChoiceRequest -> commands.respondCapo(r.requestId, null)
            is InsertDirectiveRequest -> commands.respondDirective(r.requestId, null)
            is ConfirmDiscardRequest, null -> Unit
        }
    }

    (pending as? ConfirmDiscardRequest)?.let { r ->
        AlertDialog(
            onDismissRequest = { commands.respondDiscard(r.requestId, DiscardChoice.CANCEL) },
            title = { Text("Unsaved changes") },
            text = { Text("Save the changes to ${document?.displayName ?: "the song"}?") },
            confirmButton = {
                TextButton(onClick = { commands.respondDiscard(r.requestId, DiscardChoice.SAVE) }) { Text("Save") }
            },
            dismissButton = {
                TextButton(onClick = { commands.respondDiscard(r.requestId, DiscardChoice.DISCARD) }) { Text("Discard") }
            },
        )
    }

    MaterialTheme {
        Surface(Modifier.fillMaxSize()) {
            Column(
                Modifier.fillMaxSize().safeDrawingPadding().padding(12.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Text("Chord Notepad (M3 placeholder)", style = MaterialTheme.typography.titleMedium)
                Text("Python: $host")
                Text(document?.title ?: "No document state yet")
                Text("Status: ${status?.text.orEmpty()}")
                Text("Playback: ${playback?.status ?: "-"}, bar ${playback?.bar ?: 0}/${playback?.totalBars ?: 0}")
                Text("Toolbar: ${toolbar?.let { "${it.bpmDisplay} BPM, ${it.key}, ${it.beats}/${it.unit}" } ?: "-"}")
                Text("Highlight: ${highlight?.spans?.size ?: 0} spans (revision ${highlight?.textRevision ?: 0})")
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    OutlinedButton(onClick = commands::newDocument) { Text("New") }
                    OutlinedButton(onClick = { commands.openDocument() }) { Text("Open") }
                    OutlinedButton(onClick = commands::save) { Text("Save") }
                    OutlinedButton(onClick = commands::saveAs) { Text("Save as") }
                    OutlinedButton(onClick = commands::exportMidi) { Text("Export MIDI") }
                    OutlinedButton(onClick = { commands.playPause() }) { Text("Play/Pause") }
                    OutlinedButton(onClick = commands::stop) { Text("Stop") }
                }
                Text("Recent", style = MaterialTheme.typography.titleSmall)
                recent?.items.orEmpty().forEach { ref ->
                    TextButton(onClick = { commands.openRecent(ref) }) { Text("${ref.displayName}  ·  ${ref.location}") }
                }
                if (errors.isNotEmpty()) {
                    Text("Errors", style = MaterialTheme.typography.titleSmall)
                    errors.forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
                }
            }
        }
    }
}
