package com.tibich.chordnotepad.ui

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.bridge.AudioUnavailable
import com.tibich.chordnotepad.bridge.UnexpectedError
import com.tibich.chordnotepad.bridge.UserError

/**
 * Shows the oldest queued error: a dialog for a [UserError] and for
 * [AudioUnavailable] (as the desktop does; the session already decided it
 * is worth showing), a snackbar for an [UnexpectedError].
 */
@Composable
fun ErrorPresenter(queue: ErrorQueue, snackbars: SnackbarHostState) {
    val items by queue.items.collectAsState()
    val head = items.firstOrNull() ?: return
    when (val e = head.error) {
        is UserError -> ErrorDialog(e.title, e.message) { queue.dismiss(head) }
        is AudioUnavailable -> ErrorDialog(stringResource(R.string.audio_error_title), e.message) { queue.dismiss(head) }
        is UnexpectedError -> {
            val text = stringResource(R.string.unexpected_error, e.message)
            LaunchedEffect(head.id) {
                snackbars.showSnackbar(text, withDismissAction = true, duration = SnackbarDuration.Long)
                queue.dismiss(head)
            }
        }
    }
}

@Composable
private fun ErrorDialog(title: String, message: String, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(message) },
        confirmButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.ok)) } },
    )
}
