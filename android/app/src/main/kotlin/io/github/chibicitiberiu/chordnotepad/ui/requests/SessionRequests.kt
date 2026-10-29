package io.github.chibicitiberiu.chordnotepad.ui.requests

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.bridge.ConfirmDiscardRequest
import io.github.chibicitiberiu.chordnotepad.bridge.DiscardChoice
import io.github.chibicitiberiu.chordnotepad.bridge.SessionRequest
import kotlinx.coroutines.flow.StateFlow

/**
 * The dialogs for the session's pending request. The request is app-scoped
 * state, so a dialog comes back after a rotation until it's answered.
 * Pickers are launched by the activity ([RequestPickers]); requests without
 * a UI yet are cancelled there ([RequestPresentation.NotYetSupported]).
 */
@Composable
fun SessionRequests(pending: StateFlow<SessionRequest?>, controller: RequestController) {
    val request by pending.collectAsState()
    val dialog = request?.let(::presentationOf) as? RequestPresentation.Dialog ?: return
    when (val r = dialog.request) {
        is ConfirmDiscardRequest -> ConfirmDiscardDialog { controller.answerDiscard(r, it) }
        // M5 adds the Capo choice and Insert directive dialogs here.
        else -> Unit
    }
}

/**
 * The desktop's unsaved-changes question (`formatting.CONFIRM_DISCARD_*`),
 * with Save / Don't save / Cancel for its Yes / No / Cancel. Dismissing is
 * Cancel.
 */
@Composable
fun ConfirmDiscardDialog(onAnswer: (DiscardChoice) -> Unit) {
    AlertDialog(
        onDismissRequest = { onAnswer(DiscardChoice.CANCEL) },
        title = { Text(stringResource(R.string.unsaved_title)) },
        text = { Text(stringResource(R.string.unsaved_message)) },
        // Both slots go into one flow row, so the three buttons wrap on narrow screens.
        dismissButton = {
            TextButton(onClick = { onAnswer(DiscardChoice.DISCARD) }) { Text(stringResource(R.string.unsaved_discard)) }
            TextButton(onClick = { onAnswer(DiscardChoice.CANCEL) }) { Text(stringResource(android.R.string.cancel)) }
        },
        confirmButton = {
            TextButton(onClick = { onAnswer(DiscardChoice.SAVE) }) { Text(stringResource(R.string.unsaved_save)) }
        },
    )
}
