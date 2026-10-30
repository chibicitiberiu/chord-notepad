package com.tibich.chordnotepad.support

import android.app.Activity
import android.content.Context
import android.util.Log
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClient.BillingResponseCode
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withTimeoutOrNull

private const val TAG = "CNBilling"

/**
 * The play flavour's [SupportBilling]: the one-time [SUPPORTER_PRODUCT_ID]
 * purchase through Google Play Billing. Connects as soon as it's created
 * (AppGraph, at app start); the decisions are in [SupporterLogic].
 */
class PlayBilling(context: Context) : SupportBilling {
    private val gateway = ClientGateway(context.applicationContext)
    private val logic = SupporterLogic(gateway)

    init {
        gateway.onPurchasesUpdated = logic::onPurchasesUpdated
        logic.start()
    }

    override val available = true
    override val isSupporter: StateFlow<Boolean> get() = logic.isSupporter
    override val price: StateFlow<String?> get() = logic.price
    override val purchaseState: StateFlow<PurchaseState> get() = logic.purchaseState
    override val showThankYou: StateFlow<Boolean> get() = logic.showThankYou
    override val supportUrl: String? = null

    override suspend fun awaitReady(timeoutMs: Long): Boolean {
        withTimeoutOrNull(timeoutMs) { logic.settled.first { it } }
        return logic.ready
    }

    override fun canAskForSupport() = logic.canAskForSupport()

    override fun launchPurchase(activity: Activity) {
        logic.purchase { gateway.launch(activity) }
    }

    override fun refresh() = logic.refresh()

    override fun dismissThankYou() = logic.dismissThankYou()
}

/** [BillingGateway] over a real `BillingClient`. */
private class ClientGateway(context: Context) : BillingGateway {
    /** Set before the first connect; Play's PurchasesUpdatedListener forwards here. */
    var onPurchasesUpdated: (BillingCode, List<PurchaseInfo>) -> Unit = { _, _ -> }

    @Volatile private var product: ProductDetails? = null
    @Volatile private var offerToken: String? = null

    private val client: BillingClient = BillingClient.newBuilder(context)
        .setListener { result, purchases ->
            onPurchasesUpdated(result.toCode("purchase update"), purchases.orEmpty().map { it.toInfo() })
        }
        .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
        .enableAutoServiceReconnection()
        .build()

    override fun connect(onSetup: (BillingCode) -> Unit) {
        client.startConnection(object : BillingClientStateListener {
            override fun onBillingSetupFinished(result: BillingResult) {
                onSetup(result.toCode("setup"))
            }

            // With automatic reconnection the next call reconnects by itself.
            override fun onBillingServiceDisconnected() {
                Log.i(TAG, "billing service disconnected")
            }
        })
    }

    override fun queryPurchases(onResult: (BillingCode, List<PurchaseInfo>) -> Unit) {
        val params = QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.INAPP).build()
        client.queryPurchasesAsync(params) { result, purchases ->
            onResult(result.toCode("purchase query"), purchases.map { it.toInfo() })
        }
    }

    override fun queryPrice(productId: String, onResult: (BillingCode, String?) -> Unit) {
        val params = QueryProductDetailsParams.newBuilder()
            .setProductList(
                listOf(
                    QueryProductDetailsParams.Product.newBuilder()
                        .setProductId(productId)
                        .setProductType(BillingClient.ProductType.INAPP)
                        .build(),
                ),
            )
            .build()
        client.queryProductDetailsAsync(params) { result, details ->
            val found = details.productDetailsList.firstOrNull { it.productId == productId }
            val offer = found?.oneTimePurchaseOfferDetailsList?.firstOrNull()
            if (offer != null) {
                product = found
                offerToken = offer.offerToken
            } else if (result.responseCode == BillingResponseCode.OK) {
                Log.w(TAG, "no one-time offer for '$productId'")
            }
            onResult(result.toCode("product lookup"), offer?.formattedPrice)
        }
    }

    override fun acknowledge(token: String, onResult: (BillingCode) -> Unit) {
        val params = AcknowledgePurchaseParams.newBuilder().setPurchaseToken(token).build()
        client.acknowledgePurchase(params) { result -> onResult(result.toCode("acknowledge")) }
    }

    /** Opens Play's purchase screen; must run on the main thread. */
    fun launch(activity: Activity): BillingCode {
        val details = product ?: return BillingCode.ERROR.also { Log.w(TAG, "purchase without product details") }
        val flow = BillingFlowParams.newBuilder()
            .setProductDetailsParamsList(
                listOf(
                    BillingFlowParams.ProductDetailsParams.newBuilder()
                        .setProductDetails(details)
                        .apply { offerToken?.let(::setOfferToken) }
                        .build(),
                ),
            )
            .build()
        return client.launchBillingFlow(activity, flow).toCode("launch")
    }
}

private fun Purchase.toInfo() = PurchaseInfo(
    token = purchaseToken,
    products = products,
    status = when (purchaseState) {
        Purchase.PurchaseState.PURCHASED -> PurchaseStatus.PURCHASED
        Purchase.PurchaseState.PENDING -> PurchaseStatus.PENDING
        else -> PurchaseStatus.UNSPECIFIED
    },
    acknowledged = isAcknowledged,
)

private fun BillingResult.toCode(what: String): BillingCode {
    val code = when (responseCode) {
        BillingResponseCode.OK -> BillingCode.OK
        BillingResponseCode.USER_CANCELED -> BillingCode.USER_CANCELED
        BillingResponseCode.ITEM_ALREADY_OWNED -> BillingCode.ITEM_ALREADY_OWNED
        BillingResponseCode.SERVICE_UNAVAILABLE,
        BillingResponseCode.SERVICE_DISCONNECTED,
        BillingResponseCode.NETWORK_ERROR,
        @Suppress("DEPRECATION") BillingResponseCode.SERVICE_TIMEOUT,
        -> BillingCode.TRANSIENT
        BillingResponseCode.BILLING_UNAVAILABLE -> BillingCode.BILLING_UNAVAILABLE
        else -> BillingCode.ERROR
    }
    if (code != BillingCode.OK && code != BillingCode.USER_CANCELED) {
        Log.i(TAG, "$what: $responseCode $debugMessage")
    }
    return code
}
