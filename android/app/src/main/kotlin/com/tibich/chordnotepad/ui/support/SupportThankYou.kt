package com.tibich.chordnotepad.ui.support

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.support.SupportBilling

/**
 * The thank-you after a supporter purchase completes while the app runs
 * ([SupportBilling.showThankYou]; app-scoped, so it survives rotation and
 * shows on whichever screen is up). OK, Back or a tap outside closes it.
 */
@Composable
fun SupportThankYou(billing: SupportBilling) {
    val show by billing.showThankYou.collectAsState()
    if (!show) return
    AlertDialog(
        onDismissRequest = billing::dismissThankYou,
        icon = { Icon(painterResource(R.drawable.mdi_heart), contentDescription = null) },
        title = { Text(stringResource(R.string.support_thanks_title), Modifier.semantics { heading() }) },
        text = { Text(stringResource(R.string.support_thanks_message)) },
        confirmButton = { TextButton(onClick = billing::dismissThankYou) { Text(stringResource(android.R.string.ok)) } },
    )
}
