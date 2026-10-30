package com.tibich.chordnotepad.ui.support

import android.app.Activity
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.tibich.chordnotepad.support.PurchaseState
import com.tibich.chordnotepad.support.SupportBilling
import com.tibich.chordnotepad.ui.theme.ChordNotepadTheme
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * DEBUG BUILDS ONLY (src/debug): the support UI over a fake billing state, for
 * emulator screenshots. The emulator has no Play Store, so the real Settings
 * card never shows there.
 *
 * ```
 * adb shell am start -n com.tibich.chordnotepad/.ui.support.SupportDebugActivity \
 *     --es state offer|pending|supporter|error --es show card|prompt|thanks
 * ```
 *
 * The card is drawn twice: at the two-pane pages list's width (240 dp) and full width.
 */
class SupportDebugActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val state = intent.getStringExtra("state") ?: "offer"
        val show = intent.getStringExtra("show") ?: "card"
        val billing = FakeSupportBilling(state, thanks = show == "thanks")
        setContent {
            ChordNotepadTheme {
                Surface(Modifier.fillMaxSize()) {
                    Column(
                        Modifier.fillMaxSize().safeDrawingPadding().padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(16.dp),
                    ) {
                        Text("Support UI (debug): state=$state", style = MaterialTheme.typography.labelMedium)
                        SupportCard(billing, Modifier.width(240.dp))
                        SupportCard(billing)
                    }
                    when (show) {
                        "prompt" -> SupportPrompt("€4,99", onSupport = {}, onDismiss = {})
                        "thanks" -> SupportThankYou(billing)
                    }
                }
            }
        }
    }
}

/** A [SupportBilling] frozen in one state. */
private class FakeSupportBilling(state: String, thanks: Boolean) : SupportBilling {
    override val available = true
    override val isSupporter: StateFlow<Boolean> = MutableStateFlow(state == "supporter")
    override val price: StateFlow<String?> = MutableStateFlow("€4,99")
    override val purchaseState: StateFlow<PurchaseState> = MutableStateFlow(
        when (state) {
            "pending" -> PurchaseState.PENDING
            "error" -> PurchaseState.ERROR
            else -> PurchaseState.IDLE
        },
    )
    override val showThankYou = MutableStateFlow(thanks)
    override val supportUrl: String? = null
    override suspend fun awaitReady(timeoutMs: Long) = true
    override fun canAskForSupport() = false
    override fun launchPurchase(activity: Activity) {}
    override fun refresh() {}
    override fun dismissThankYou() {
        showThankYou.value = false
    }
}
