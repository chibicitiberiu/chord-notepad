package com.tibich.chordnotepad.support

import android.content.Context
import kotlinx.coroutines.CoroutineScope

/** The play build: the supporter purchase through Google Play Billing. */
fun createSupportBilling(context: Context, scope: CoroutineScope): SupportBilling = NoSupportBilling()
