package com.tibich.chordnotepad.ui.support

import androidx.activity.compose.LocalActivity
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.support.PurchaseState
import com.tibich.chordnotepad.support.SupportBilling
import com.tibich.chordnotepad.ui.icons.MdiIcon

/** What the Settings support card shows. */
enum class SupportCardKind {
    /** No card: a build without the purchase, or billing that can't sell it (no Play, no price). */
    HIDDEN,

    /** "Support Chord Notepad" and the Support button. */
    OFFER,

    /** A payment Google Play hasn't confirmed yet. */
    PENDING,

    /** The badge. */
    SUPPORTER,
    ;

    companion object {
        /** The card for a [SupportBilling]'s current values. */
        fun of(available: Boolean, isSupporter: Boolean, price: String?, state: PurchaseState): SupportCardKind = when {
            !available -> HIDDEN
            isSupporter -> SUPPORTER
            state == PurchaseState.PENDING -> PENDING
            price == null -> HIDDEN
            else -> OFFER
        }
    }
}

/**
 * The card at the top of Settings' pages list (play flavour): the offer with
 * its price, a pending payment, or the supporter badge. Nothing when [billing]
 * can't sell the purchase.
 */
@Composable
fun SupportCard(billing: SupportBilling, modifier: Modifier = Modifier) {
    val supporter by billing.isSupporter.collectAsState()
    val price by billing.price.collectAsState()
    val state by billing.purchaseState.collectAsState()
    val kind = SupportCardKind.of(billing.available, supporter, price, state)
    if (kind == SupportCardKind.HIDDEN) return
    val activity = LocalActivity.current
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
    ) {
        Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            MdiIcon(R.drawable.mdi_heart, tint = MaterialTheme.colorScheme.primary)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    stringResource(
                        if (kind == SupportCardKind.SUPPORTER) R.string.support_card_supporter else R.string.support_prompt_title,
                    ),
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.semantics { heading() },
                )
                Text(
                    stringResource(
                        when (kind) {
                            SupportCardKind.SUPPORTER -> R.string.support_card_thanks
                            SupportCardKind.PENDING -> R.string.support_pending
                            else -> R.string.support_card_offer
                        },
                    ),
                    style = MaterialTheme.typography.bodyMedium,
                )
                if (kind == SupportCardKind.OFFER && state == PurchaseState.ERROR) {
                    Text(
                        stringResource(R.string.support_card_error),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
                if (kind == SupportCardKind.OFFER) {
                    Button(
                        onClick = { activity?.let(billing::launchPurchase) },
                        modifier = Modifier.align(Alignment.End),
                    ) { Text(supportLabel(price)) }
                }
            }
        }
    }
}

/** "Support · €4,99", or plain "Support" before the price is known. */
@Composable
fun supportLabel(price: String?): String =
    if (price != null) stringResource(R.string.support_prompt_support_price, price) else stringResource(R.string.support_prompt_support)
