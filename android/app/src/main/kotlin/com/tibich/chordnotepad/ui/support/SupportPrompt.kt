package com.tibich.chordnotepad.ui.support

import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import com.tibich.chordnotepad.R

/**
 * The startup request for the optional supporter purchase
 * (`StartupState.screen == support_prompt`). Back, a tap outside and
 * "Not now" all dismiss it. The heart is decorative, the title is a heading
 * and the message scrolls on a small or zoomed screen. The localized price is
 * only on the button.
 *
 * @param price The localized price for the Support button, or null.
 * @param onSupport The user chose to buy (start Play's purchase screen).
 * @param onDismiss The prompt closed (also after [onSupport]).
 */
@Composable
fun SupportPrompt(price: String?, onSupport: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(painterResource(R.drawable.mdi_heart), contentDescription = null) },
        title = { Text(stringResource(R.string.support_prompt_title), Modifier.semantics { heading() }) },
        text = {
            Text(stringResource(R.string.support_prompt_message), Modifier.verticalScroll(rememberScrollState()))
        },
        confirmButton = {
            TextButton(onClick = {
                onSupport()
                onDismiss()
            }) { Text(supportLabel(price)) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(R.string.support_prompt_not_now)) } },
    )
}
