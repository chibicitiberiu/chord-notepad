package com.tibich.chordnotepad.support

import android.app.Activity
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Where a supporter purchase stands. */
enum class PurchaseState { IDLE, PENDING, ERROR }

/**
 * The optional "support Chord Notepad" purchase. The play flavour implements
 * it with Google Play Billing; the foss flavour has no purchase and offers
 * [supportUrl] instead. One instance lives in [com.tibich.chordnotepad.AppGraph],
 * so purchase results survive activity recreation.
 *
 * Design: docs/design/android-support-plan.md.
 */
interface SupportBilling {
    /** True when this build can sell the supporter purchase at all. */
    val available: Boolean

    /** True once Play reports a completed (PURCHASED) supporter purchase. */
    val isSupporter: StateFlow<Boolean>

    /** The localized price, e.g. "€4,99"; null until Play returns it. */
    val price: StateFlow<String?>

    val purchaseState: StateFlow<PurchaseState>

    /** True after a purchase completes in this process, until [dismissThankYou]. */
    val showThankYou: StateFlow<Boolean>

    /** A donation page for builds without a purchase (foss); null in the play build. */
    val supportUrl: String?

    /**
     * Waits until billing has connected and answered both the purchase query
     * and the product lookup, or [timeoutMs] passes. Returns whether it did.
     */
    suspend fun awaitReady(timeoutMs: Long): Boolean

    /** Whether to ask this user for support: billing works, the price is known, no purchase. */
    fun canAskForSupport(): Boolean

    /** Starts Play's purchase screen. */
    fun launchPurchase(activity: Activity)

    /** Re-queries purchases (on resume). */
    fun refresh()

    fun dismissThankYou()
}

/** A build or device with no purchase to offer. */
open class NoSupportBilling(override val supportUrl: String? = null) : SupportBilling {
    override val available = false
    override val isSupporter: StateFlow<Boolean> = MutableStateFlow(false).asStateFlow()
    override val price: StateFlow<String?> = MutableStateFlow<String?>(null).asStateFlow()
    override val purchaseState: StateFlow<PurchaseState> = MutableStateFlow(PurchaseState.IDLE).asStateFlow()
    override val showThankYou: StateFlow<Boolean> = MutableStateFlow(false).asStateFlow()
    override suspend fun awaitReady(timeoutMs: Long) = true
    override fun canAskForSupport() = false
    override fun launchPurchase(activity: Activity) {}
    override fun refresh() {}
    override fun dismissThankYou() {}
}
