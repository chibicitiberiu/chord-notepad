package com.tibich.chordnotepad.support

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** The Play product id of the one-time supporter purchase (Play Console > One-time products). */
const val SUPPORTER_PRODUCT_ID = "supporter"

/** A Play Billing response code, reduced to the cases [SupporterLogic] treats differently. */
enum class BillingCode {
    OK,
    USER_CANCELED,
    ITEM_ALREADY_OWNED,

    /** Play is there but can't answer now (service down, timeout, network, disconnected). */
    TRANSIENT,

    /** No billing on this device (no Play Store, old Play Store, unsupported country). */
    BILLING_UNAVAILABLE,

    /** Anything else: developer error, item unavailable, generic error. */
    ERROR,
}

/** Where Play says a purchase stands. */
enum class PurchaseStatus { PURCHASED, PENDING, UNSPECIFIED }

/** The parts of a Play `Purchase` the logic needs. */
data class PurchaseInfo(
    val token: String,
    val products: List<String>,
    val status: PurchaseStatus,
    val acknowledged: Boolean,
)

/**
 * The calls [SupporterLogic] makes to Play Billing, as plain callbacks so tests
 * can answer them by hand. [PlayBilling] implements it over `BillingClient`.
 */
interface BillingGateway {
    /** Starts the connection; [onSetup] gets the setup result. */
    fun connect(onSetup: (BillingCode) -> Unit)

    /** All the user's in-app purchases (Play's cached list; works offline). */
    fun queryPurchases(onResult: (BillingCode, List<PurchaseInfo>) -> Unit)

    /** The product's localized price; null when Play has no offer for it. */
    fun queryPrice(productId: String, onResult: (BillingCode, String?) -> Unit)

    fun acknowledge(token: String, onResult: (BillingCode) -> Unit)
}

/**
 * The supporter purchase's state machine, free of Android and Play classes so
 * the JVM tests drive it directly.
 *
 * Rules (docs/ANDROID.md, "Startup screen and support prompt"):
 * - one [process] path for purchase updates and purchase queries: PURCHASED
 *   makes the user a supporter and is acknowledged if it isn't yet; PENDING is
 *   shown as pending and never granted; nothing is ever consumed;
 * - the supporter flag goes false only after a purchase query that answered OK
 *   without the purchase (a refund); never on an error;
 * - ITEM_ALREADY_OWNED re-queries; USER_CANCELED goes back to idle quietly;
 * - the thank-you shows when a purchase completes while the app runs: from a
 *   purchase update, or from a query that finds a purchase this process saw
 *   pending.
 */
class SupporterLogic(
    private val gateway: BillingGateway,
    private val productId: String = SUPPORTER_PRODUCT_ID,
) {
    private val lock = Any()

    private val _isSupporter = MutableStateFlow(false)
    val isSupporter: StateFlow<Boolean> = _isSupporter.asStateFlow()

    private val _price = MutableStateFlow<String?>(null)
    val price: StateFlow<String?> = _price.asStateFlow()

    private val _purchaseState = MutableStateFlow(PurchaseState.IDLE)
    val purchaseState: StateFlow<PurchaseState> = _purchaseState.asStateFlow()

    private val _showThankYou = MutableStateFlow(false)
    val showThankYou: StateFlow<Boolean> = _showThankYou.asStateFlow()

    private val _settled = MutableStateFlow(false)

    /**
     * True once the startup lookups have an answer: setup failed, or it worked
     * and both the purchase query and the price lookup came back (OK or not).
     */
    val settled: StateFlow<Boolean> = _settled.asStateFlow()

    private var connected = false
    private var connecting = false
    private var purchasesKnown = false
    private var purchasesAnswered = false
    private var priceAnswered = false
    private val pendingSeen = mutableSetOf<String>()
    private val acknowledging = mutableSetOf<String>()

    /** True when billing connected and both startup lookups answered OK. */
    val ready: Boolean get() = synchronized(lock) { connected && purchasesKnown && _price.value != null }

    /** Billing works, the price is known, and there's no purchase (completed or pending). */
    fun canAskForSupport(): Boolean = synchronized(lock) {
        connected && purchasesKnown && _price.value != null && !_isSupporter.value &&
            _purchaseState.value != PurchaseState.PENDING
    }

    /** Connects, then queries purchases and the price. */
    fun start() {
        synchronized(lock) {
            if (connected || connecting) return
            connecting = true
        }
        gateway.connect(::onSetup)
    }

    /** Re-queries purchases (on resume); reconnects first if setup failed earlier. */
    fun refresh() {
        val isConnected = synchronized(lock) { connected }
        if (isConnected) queryPurchases() else start()
    }

    private fun onSetup(code: BillingCode) {
        synchronized(lock) {
            connecting = false
            connected = code == BillingCode.OK
            if (!connected) {
                // Nothing more will come from this attempt; startup can go on.
                _settled.value = true
                return
            }
        }
        queryPurchases()
        val needPrice = synchronized(lock) { _price.value == null }
        if (needPrice) {
            gateway.queryPrice(productId, ::onPrice)
        } else {
            synchronized(lock) { priceAnswered = true }
        }
    }

    private fun queryPurchases() {
        gateway.queryPurchases(::onPurchasesQueried)
    }

    private fun onPrice(code: BillingCode, price: String?) {
        synchronized(lock) {
            if (code == BillingCode.OK && price != null) _price.value = price
            priceAnswered = true
            updateSettled()
        }
    }

    private fun onPurchasesQueried(code: BillingCode, purchases: List<PurchaseInfo>) {
        val toAcknowledge = synchronized(lock) {
            purchasesAnswered = true
            val result = if (code == BillingCode.OK) {
                purchasesKnown = true
                process(purchases, complete = true)
            } else {
                emptyList()
            }
            updateSettled()
            result
        }
        toAcknowledge.forEach(::acknowledge)
    }

    /** Play's PurchasesUpdatedListener: the result of a purchase flow, or a pending one completing. */
    fun onPurchasesUpdated(code: BillingCode, purchases: List<PurchaseInfo>) {
        when (code) {
            BillingCode.OK -> {
                val toAcknowledge = synchronized(lock) { process(purchases, complete = false) }
                toAcknowledge.forEach(::acknowledge)
            }
            BillingCode.USER_CANCELED -> synchronized(lock) {
                if (_purchaseState.value != PurchaseState.PENDING) _purchaseState.value = PurchaseState.IDLE
            }
            BillingCode.ITEM_ALREADY_OWNED -> {
                synchronized(lock) { _purchaseState.value = PurchaseState.IDLE }
                queryPurchases()
            }
            else -> synchronized(lock) { _purchaseState.value = PurchaseState.ERROR }
        }
    }

    /**
     * Called when the user taps Support: [launch] opens Play's purchase screen
     * and returns its immediate result; the outcome arrives in [onPurchasesUpdated].
     */
    fun purchase(launch: () -> BillingCode) {
        synchronized(lock) { _purchaseState.value = PurchaseState.IDLE }
        when (launch()) {
            BillingCode.OK, BillingCode.USER_CANCELED -> Unit
            BillingCode.ITEM_ALREADY_OWNED -> queryPurchases()
            else -> synchronized(lock) { _purchaseState.value = PurchaseState.ERROR }
        }
    }

    fun dismissThankYou() {
        _showThankYou.value = false
    }

    /**
     * The one path for purchases from either source. [complete] is true for a
     * query's answer (the whole list) and false for an update (only what changed).
     * Returns the tokens to acknowledge. Call with [lock] held.
     */
    private fun process(purchases: List<PurchaseInfo>, complete: Boolean): List<String> {
        val mine = purchases.filter { productId in it.products }
        val purchased = mine.filter { it.status == PurchaseStatus.PURCHASED }
        val pending = mine.filter { it.status == PurchaseStatus.PENDING }
        when {
            purchased.isNotEmpty() -> {
                val completedHere = !complete || purchased.any { it.token in pendingSeen }
                if (!_isSupporter.value && completedHere) _showThankYou.value = true
                _isSupporter.value = true
                _purchaseState.value = PurchaseState.IDLE
                purchased.forEach { pendingSeen.remove(it.token) }
            }
            pending.isNotEmpty() -> {
                pendingSeen += pending.map { it.token }
                _purchaseState.value = PurchaseState.PENDING
            }
            complete -> {
                // Play answered with the whole list and the purchase isn't in it:
                // never bought, refunded, or a pending payment that was cancelled.
                _isSupporter.value = false
                if (_purchaseState.value == PurchaseState.PENDING) _purchaseState.value = PurchaseState.IDLE
                pendingSeen.clear()
            }
        }
        return purchased.filter { !it.acknowledged && acknowledging.add(it.token) }.map { it.token }
    }

    private fun acknowledge(token: String) {
        // Whatever the result: on failure the purchase stays unacknowledged, and
        // the next query (startup, resume) finds it and tries again. Play refunds
        // a purchase that stays unacknowledged for three days.
        gateway.acknowledge(token) { synchronized(lock) { acknowledging.remove(token) } }
    }

    private fun updateSettled() {
        if (purchasesAnswered && priceAnswered) _settled.value = true
    }
}
