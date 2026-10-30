package com.tibich.chordnotepad.support

import android.content.Context
import kotlinx.coroutines.CoroutineScope

/**
 * Creates this build's [SupportBilling]. Placeholder until the play/foss
 * flavours exist; then each flavour's source set provides this function and
 * this file goes away.
 */
fun createSupportBilling(context: Context, scope: CoroutineScope): SupportBilling = NoSupportBilling()
