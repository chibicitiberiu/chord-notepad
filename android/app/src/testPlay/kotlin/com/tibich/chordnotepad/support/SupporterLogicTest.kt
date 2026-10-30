package com.tibich.chordnotepad.support

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** A Play Billing stand-in: each call waits until the test answers it. */
private class FakeGateway : BillingGateway {
    val setups = ArrayDeque<(BillingCode) -> Unit>()
    val purchaseQueries = ArrayDeque<(BillingCode, List<PurchaseInfo>) -> Unit>()
    val priceQueries = ArrayDeque<(BillingCode, String?) -> Unit>()
    val acknowledged = mutableListOf<String>()
    var acknowledgeResult = BillingCode.OK

    override fun connect(onSetup: (BillingCode) -> Unit) {
        setups += onSetup
    }

    override fun queryPurchases(onResult: (BillingCode, List<PurchaseInfo>) -> Unit) {
        purchaseQueries += onResult
    }

    override fun queryPrice(productId: String, onResult: (BillingCode, String?) -> Unit) {
        assertEquals(SUPPORTER_PRODUCT_ID, productId)
        priceQueries += onResult
    }

    override fun acknowledge(token: String, onResult: (BillingCode) -> Unit) {
        acknowledged += token
        onResult(acknowledgeResult)
    }

    fun answerSetup(code: BillingCode = BillingCode.OK) = setups.removeFirst()(code)
    fun answerPurchases(code: BillingCode, vararg purchases: PurchaseInfo) =
        purchaseQueries.removeFirst()(code, purchases.toList())
    fun answerPrice(code: BillingCode = BillingCode.OK, price: String? = "€4,99") = priceQueries.removeFirst()(code, price)
}

private fun purchased(token: String = "t1", acknowledged: Boolean = false) =
    PurchaseInfo(token, listOf(SUPPORTER_PRODUCT_ID), PurchaseStatus.PURCHASED, acknowledged)

private fun pending(token: String = "t1") =
    PurchaseInfo(token, listOf(SUPPORTER_PRODUCT_ID), PurchaseStatus.PENDING, acknowledged = false)

class SupporterLogicTest {
    private val play = FakeGateway()
    private val logic = SupporterLogic(play)

    /** Connected, no purchase, the price known: the usual non-supporter start. */
    private fun startClean() {
        logic.start()
        play.answerSetup()
        play.answerPurchases(BillingCode.OK)
        play.answerPrice()
    }

    @Test
    fun `a clean start knows the price and may ask for support`() {
        logic.start()
        assertFalse(logic.settled.value)
        play.answerSetup()
        play.answerPurchases(BillingCode.OK)
        assertFalse("waits for the price too", logic.settled.value)
        play.answerPrice()
        assertTrue(logic.settled.value)
        assertTrue(logic.ready)
        assertEquals("€4,99", logic.price.value)
        assertFalse(logic.isSupporter.value)
        assertTrue(logic.canAskForSupport())
    }

    @Test
    fun `no billing on the device settles at once and never asks`() {
        logic.start()
        play.answerSetup(BillingCode.BILLING_UNAVAILABLE)
        assertTrue(logic.settled.value)
        assertFalse(logic.ready)
        assertFalse(logic.canAskForSupport())
        assertTrue("no lookups without a connection", play.purchaseQueries.isEmpty() && play.priceQueries.isEmpty())
    }

    @Test
    fun `without a price there is no asking`() {
        logic.start()
        play.answerSetup()
        play.answerPurchases(BillingCode.OK)
        play.answerPrice(BillingCode.OK, price = null)
        assertTrue(logic.settled.value)
        assertNull(logic.price.value)
        assertFalse(logic.canAskForSupport())
    }

    @Test
    fun `a purchased, unacknowledged purchase makes a supporter and is acknowledged`() {
        logic.start()
        play.answerSetup()
        play.answerPurchases(BillingCode.OK, purchased("t1", acknowledged = false))
        play.answerPrice()
        assertTrue(logic.isSupporter.value)
        assertEquals(listOf("t1"), play.acknowledged)
        assertFalse("found at startup: no thank-you", logic.showThankYou.value)
        assertFalse(logic.canAskForSupport())
    }

    @Test
    fun `an acknowledged purchase is not acknowledged again`() {
        logic.start()
        play.answerSetup()
        play.answerPurchases(BillingCode.OK, purchased("t1", acknowledged = true))
        assertTrue(logic.isSupporter.value)
        assertEquals(emptyList<String>(), play.acknowledged)
    }

    @Test
    fun `a failed acknowledgement is retried on the next query`() {
        play.acknowledgeResult = BillingCode.TRANSIENT
        logic.start()
        play.answerSetup()
        play.answerPurchases(BillingCode.OK, purchased("t1"))
        logic.refresh()
        play.acknowledgeResult = BillingCode.OK
        play.answerPurchases(BillingCode.OK, purchased("t1"))
        assertEquals(listOf("t1", "t1"), play.acknowledged)
    }

    @Test
    fun `a purchase in this session shows the thank-you`() {
        startClean()
        logic.purchase { BillingCode.OK }
        logic.onPurchasesUpdated(BillingCode.OK, listOf(purchased("t1")))
        assertTrue(logic.isSupporter.value)
        assertTrue(logic.showThankYou.value)
        assertEquals(listOf("t1"), play.acknowledged)
        logic.dismissThankYou()
        assertFalse(logic.showThankYou.value)
    }

    @Test
    fun `a pending purchase is shown as pending and not granted`() {
        startClean()
        logic.purchase { BillingCode.OK }
        logic.onPurchasesUpdated(BillingCode.OK, listOf(pending("t1")))
        assertEquals(PurchaseState.PENDING, logic.purchaseState.value)
        assertFalse(logic.isSupporter.value)
        assertEquals(emptyList<String>(), play.acknowledged)
        assertFalse(logic.showThankYou.value)
        assertFalse("no nag while a payment is pending", logic.canAskForSupport())
    }

    @Test
    fun `pending at startup, then purchased on the next query, thanks and acknowledges`() {
        logic.start()
        play.answerSetup()
        play.answerPurchases(BillingCode.OK, pending("t1"))
        play.answerPrice()
        assertEquals(PurchaseState.PENDING, logic.purchaseState.value)
        assertFalse(logic.isSupporter.value)

        logic.refresh()
        play.answerPurchases(BillingCode.OK, purchased("t1"))
        assertTrue(logic.isSupporter.value)
        assertEquals(PurchaseState.IDLE, logic.purchaseState.value)
        assertTrue("completed while the app ran", logic.showThankYou.value)
        assertEquals(listOf("t1"), play.acknowledged)
    }

    @Test
    fun `a pending payment that is cancelled goes back to idle`() {
        logic.start()
        play.answerSetup()
        play.answerPurchases(BillingCode.OK, pending("t1"))
        logic.refresh()
        play.answerPurchases(BillingCode.OK)
        assertEquals(PurchaseState.IDLE, logic.purchaseState.value)
        assertFalse(logic.isSupporter.value)
    }

    @Test
    fun `a refund clears the badge after a query that answered OK`() {
        logic.start()
        play.answerSetup()
        play.answerPurchases(BillingCode.OK, purchased("t1", acknowledged = true))
        play.answerPrice()
        assertTrue(logic.isSupporter.value)

        logic.refresh()
        play.answerPurchases(BillingCode.OK)
        assertFalse(logic.isSupporter.value)
        assertTrue(logic.canAskForSupport())
    }

    @Test
    fun `errors never clear the badge`() {
        logic.start()
        play.answerSetup()
        play.answerPurchases(BillingCode.OK, purchased("t1", acknowledged = true))
        play.answerPrice()
        for (code in listOf(BillingCode.TRANSIENT, BillingCode.BILLING_UNAVAILABLE, BillingCode.ERROR)) {
            logic.refresh()
            play.answerPurchases(code)
            assertTrue("after $code", logic.isSupporter.value)
        }
    }

    @Test
    fun `an update with other purchases only is not a refund`() {
        logic.start()
        play.answerSetup()
        play.answerPurchases(BillingCode.OK, purchased("t1", acknowledged = true))
        logic.onPurchasesUpdated(BillingCode.OK, emptyList())
        assertTrue(logic.isSupporter.value)
    }

    @Test
    fun `a failed purchase query at startup leaves the status unknown and doesn't ask`() {
        logic.start()
        play.answerSetup()
        play.answerPurchases(BillingCode.TRANSIENT)
        play.answerPrice()
        assertTrue(logic.settled.value)
        assertFalse(logic.ready)
        assertFalse(logic.isSupporter.value)
        assertFalse(logic.canAskForSupport())
    }

    @Test
    fun `cancelling the purchase screen goes back to idle without an error`() {
        startClean()
        logic.purchase { BillingCode.OK }
        logic.onPurchasesUpdated(BillingCode.USER_CANCELED, emptyList())
        assertEquals(PurchaseState.IDLE, logic.purchaseState.value)
        assertFalse(logic.isSupporter.value)
        assertTrue(logic.canAskForSupport())
    }

    @Test
    fun `item already owned re-queries and then counts as a supporter`() {
        startClean()
        logic.purchase { BillingCode.OK }
        logic.onPurchasesUpdated(BillingCode.ITEM_ALREADY_OWNED, emptyList())
        assertEquals(1, play.purchaseQueries.size)
        play.answerPurchases(BillingCode.OK, purchased("t1", acknowledged = true))
        assertTrue(logic.isSupporter.value)
        assertFalse("not a new purchase", logic.showThankYou.value)
    }

    @Test
    fun `a purchase screen that fails to open is an error, and the next try clears it`() {
        startClean()
        logic.purchase { BillingCode.ERROR }
        assertEquals(PurchaseState.ERROR, logic.purchaseState.value)
        logic.purchase { BillingCode.OK }
        assertEquals(PurchaseState.IDLE, logic.purchaseState.value)
        logic.onPurchasesUpdated(BillingCode.TRANSIENT, emptyList())
        assertEquals(PurchaseState.ERROR, logic.purchaseState.value)
    }

    @Test
    fun `other products are ignored`() {
        logic.start()
        play.answerSetup()
        play.answerPurchases(
            BillingCode.OK,
            PurchaseInfo("x", listOf("something_else"), PurchaseStatus.PURCHASED, acknowledged = false),
        )
        assertFalse(logic.isSupporter.value)
        assertEquals(emptyList<String>(), play.acknowledged)
    }

    @Test
    fun `refresh after a failed setup connects again`() {
        logic.start()
        play.answerSetup(BillingCode.TRANSIENT)
        logic.refresh()
        assertEquals(1, play.setups.size)
        play.answerSetup()
        play.answerPurchases(BillingCode.OK)
        play.answerPrice()
        assertTrue(logic.ready)
    }
}
