package com.tibich.chordnotepad.ui.main

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.ui.theme.appColors

/**
 * Rename (tap the title): the name without its extension, selected, and
 * "Saved as name.txt" under it. [onRename] gets the typed name (the session
 * keeps the extension); the dialog stays until the caller closes it, showing
 * [error] when the session refused the name.
 */
@Composable
fun RenameDialog(displayName: String, error: String?, onRename: (String) -> Unit, onDismiss: () -> Unit) {
    val colors = appColors
    val initial = remember(displayName) { renameFieldText(displayName) }
    var name by rememberSaveable(displayName) { mutableStateOf(initial) }
    var field by remember { mutableStateOf(TextFieldValue(name, TextRange(0, name.length))) }
    val problem = renameProblem(field.text, displayName)
    val focus = remember { FocusRequester() }
    val submit = { if (problem == null) onRename(field.text.trim()) else if (problem == RenameProblem.UNCHANGED) onDismiss() }
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = colors.surfaceHigh,
        title = { Text(stringResource(R.string.rename_title)) },
        text = {
            Column {
                OutlinedTextField(
                    value = field,
                    onValueChange = {
                        field = it
                        name = it.text
                    },
                    singleLine = true,
                    isError = problem == RenameProblem.BAD_CHARACTER || error != null,
                    keyboardOptions = KeyboardOptions(
                        capitalization = KeyboardCapitalization.Sentences,
                        imeAction = ImeAction.Done,
                        autoCorrectEnabled = false,
                    ),
                    keyboardActions = KeyboardActions(onDone = { submit() }),
                    modifier = Modifier.fillMaxWidth().focusRequester(focus),
                )
                val hint = when {
                    error != null -> error
                    else -> when (problem) {
                    RenameProblem.BAD_CHARACTER -> stringResource(R.string.rename_bad_character)
                    RenameProblem.EMPTY -> stringResource(R.string.rename_empty)
                    else -> stringResource(R.string.rename_saved_as, renamedFileName(field.text, displayName))
                    }
                }
                Text(
                    hint,
                    Modifier.padding(top = 6.dp, start = 2.dp),
                    fontSize = 12.sp,
                    color = if (problem == RenameProblem.BAD_CHARACTER || error != null) MaterialTheme.colorScheme.error else colors.muted,
                )
            }
            LaunchedEffect(Unit) { focus.requestFocus() }
        },
        confirmButton = {
            TextButton(onClick = submit, enabled = problem == null || problem == RenameProblem.UNCHANGED) {
                Text(stringResource(R.string.rename_button))
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } },
    )
}

/**
 * The storage couldn't rename: say why, and offer Save As under the name
 * when that's the way out ([RenameFailure.canSaveAs]).
 */
@Composable
fun RenameFailedDialog(failure: RenameFailure, onSaveAs: (String) -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = appColors.surfaceHigh,
        title = { Text(stringResource(R.string.rename_failed_title)) },
        text = {
            Text(
                if (failure.canSaveAs) stringResource(R.string.rename_failed_save_as, failure.reason)
                else failure.reason,
            )
        },
        confirmButton = {
            if (failure.canSaveAs) {
                TextButton(onClick = { onSaveAs(failure.name) }) { Text(stringResource(R.string.drawer_save_as)) }
            } else {
                TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.ok)) }
            }
        },
        dismissButton = if (failure.canSaveAs) {
            { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } }
        } else null,
    )
}
