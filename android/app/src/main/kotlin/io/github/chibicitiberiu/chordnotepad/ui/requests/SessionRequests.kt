package io.github.chibicitiberiu.chordnotepad.ui.requests

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.bridge.CapoChoiceRequest
import io.github.chibicitiberiu.chordnotepad.bridge.ConfirmDiscardRequest
import io.github.chibicitiberiu.chordnotepad.bridge.DiscardChoice
import io.github.chibicitiberiu.chordnotepad.bridge.InsertDirectiveRequest
import io.github.chibicitiberiu.chordnotepad.bridge.SessionRepository
import io.github.chibicitiberiu.chordnotepad.bridge.SessionRequest
import io.github.chibicitiberiu.chordnotepad.ui.tools.CapoDialog
import io.github.chibicitiberiu.chordnotepad.ui.tools.InsertDirectiveDialog
import io.github.chibicitiberiu.chordnotepad.ui.tools.keyChoices
import kotlinx.coroutines.flow.StateFlow

/**
 * The dialogs for the session's pending request. The request is app-scoped
 * state, so a dialog comes back after a rotation until it's answered.
 * Pickers are launched by the activity ([RequestPickers]).
 *
 * @param repo The states the Insert directive dialogs choose from (the key
 *   lists and beat units of `SettingsState`, the toolbar's keys as a fallback).
 * @param onSuggestCapo The Capo dialog's Suggest (after it cancelled its request).
 */
@Composable
fun SessionRequests(
    pending: StateFlow<SessionRequest?>,
    controller: RequestController,
    repo: SessionRepository,
    onSuggestCapo: () -> Unit = {},
) {
    val request by pending.collectAsState()
    val dialog = request?.let(::presentationOf) as? RequestPresentation.Dialog ?: return
    when (val r = dialog.request) {
        is ConfirmDiscardRequest -> ConfirmDiscardDialog { controller.answerDiscard(r, it) }
        is CapoChoiceRequest -> CapoDialog(r) { controller.answerCapo(r, it) }
        is InsertDirectiveRequest -> {
            val settings by repo.settings.collectAsState()
            val toolbar by repo.toolbar.collectAsState()
            val check by repo.directiveCheck.collectAsState()
            InsertDirectiveDialog(
                request = r,
                keys = keyChoices(r.notation, settings?.americanKeys, settings?.europeanKeys, toolbar?.keyOptions),
                units = settings?.timeSignatureUnits?.takeIf { it.isNotEmpty() } ?: DEFAULT_UNITS,
                check = check,
                onCheck = { controller.checkDirective(r, it) },
                onSuggestCapo = onSuggestCapo,
            ) { controller.answerDirective(r, it) }
        }
        else -> Unit
    }
}

// The desktop dialog's units, until SettingsState arrives (it's sent at start).
private val DEFAULT_UNITS = listOf(1, 2, 4, 8, 16)

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
