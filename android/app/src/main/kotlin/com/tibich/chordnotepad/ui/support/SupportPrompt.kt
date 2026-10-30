package com.tibich.chordnotepad.ui.support

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.tibich.chordnotepad.R

/**
 * The startup request for the optional supporter purchase
 * (`StartupState.screen == support_prompt`). Back, a tap outside and
 * "Not now" all dismiss it.
 *
 * @param price The localized price for the Support button, or null.
 * @param onSupport The user chose to buy (start Play's purchase screen).
 * @param onDismiss The prompt closed (also after [onSupport]).
 */
@Composable
fun SupportPrompt(price: String?, onSupport: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.support_prompt_title)) },
        confirmButton = {
            TextButton(onClick = {
                onSupport()
                onDismiss()
            }) {
                Text(
                    if (price != null) {
                        stringResource(R.string.support_prompt_support_price, price)
                    } else {
                        stringResource(R.string.support_prompt_support)
                    },
                )
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.support_prompt_not_now)) } },
    )
}
