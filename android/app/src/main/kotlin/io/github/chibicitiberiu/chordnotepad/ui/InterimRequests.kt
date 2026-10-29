package io.github.chibicitiberiu.chordnotepad.ui

// INTERIM (M4b replaces this): the M3 placeholder's minimal request handling,
// moved here unchanged so New/Open/Save/Export keep working until the real
// dialogs and pickers land. Capo and directive requests are cancelled (M5).

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import io.github.chibicitiberiu.chordnotepad.AppGraph
import io.github.chibicitiberiu.chordnotepad.R
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

/** Presents the session's pending request (interim; see the file comment). */
@Composable
fun InterimRequests(graph: AppGraph) {
    val repo = graph.repository
    val commands = graph.commands
    val pending by repo.pendingRequest.collectAsState()
    val document by repo.document.collectAsState()

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
            // Not before M5: cancel.
            is CapoChoiceRequest -> commands.respondCapo(r.requestId, null)
            is InsertDirectiveRequest -> commands.respondDirective(r.requestId, null)
            is ConfirmDiscardRequest, null -> Unit
        }
    }

    (pending as? ConfirmDiscardRequest)?.let { r ->
        AlertDialog(
            onDismissRequest = { commands.respondDiscard(r.requestId, DiscardChoice.CANCEL) },
            title = { Text(stringResource(R.string.unsaved_title)) },
            text = { Text(stringResource(R.string.unsaved_message, document?.displayName.orEmpty())) },
            confirmButton = {
                TextButton(onClick = { commands.respondDiscard(r.requestId, DiscardChoice.SAVE) }) {
                    Text(stringResource(R.string.unsaved_save))
                }
            },
            dismissButton = {
                TextButton(onClick = { commands.respondDiscard(r.requestId, DiscardChoice.DISCARD) }) {
                    Text(stringResource(R.string.unsaved_discard))
                }
            },
        )
    }
}
