package com.tibich.chordnotepad.ui.support

import com.tibich.chordnotepad.support.PurchaseState
import org.junit.Assert.assertEquals
import org.junit.Test

class SupportCardKindTest {
    private fun kind(available: Boolean = true, supporter: Boolean = false, price: String? = "€4,99", state: PurchaseState = PurchaseState.IDLE) =
        SupportCardKind.of(available, supporter, price, state)

    @Test
    fun `a build without the purchase never shows the card`() {
        assertEquals(SupportCardKind.HIDDEN, kind(available = false))
        assertEquals(SupportCardKind.HIDDEN, kind(available = false, supporter = true))
    }

    @Test
    fun `billing without a price hides the offer`() {
        assertEquals(SupportCardKind.HIDDEN, kind(price = null))
        assertEquals(SupportCardKind.HIDDEN, kind(price = null, state = PurchaseState.ERROR))
    }

    @Test
    fun `the offer, a failed attempt included`() {
        assertEquals(SupportCardKind.OFFER, kind())
        assertEquals(SupportCardKind.OFFER, kind(state = PurchaseState.ERROR))
    }

    @Test
    fun `a pending payment shows even before the price is known`() {
        assertEquals(SupportCardKind.PENDING, kind(state = PurchaseState.PENDING))
        assertEquals(SupportCardKind.PENDING, kind(price = null, state = PurchaseState.PENDING))
    }

    @Test
    fun `a supporter sees the badge, price or not`() {
        assertEquals(SupportCardKind.SUPPORTER, kind(supporter = true))
        assertEquals(SupportCardKind.SUPPORTER, kind(supporter = true, price = null))
    }
}
