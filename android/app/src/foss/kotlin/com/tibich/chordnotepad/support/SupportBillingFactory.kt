package com.tibich.chordnotepad.support

import android.content.Context
import kotlinx.coroutines.CoroutineScope

/** The foss build's donation page, shown in About. The play build has none (Play policy). */
private const val SUPPORT_URL = "https://ko-fi.com/tiberiualexandruchibici"

/** The foss build (GitHub APK, F-Droid): no purchase, a donation link instead. */
fun createSupportBilling(context: Context, scope: CoroutineScope): SupportBilling =
    NoSupportBilling(supportUrl = SUPPORT_URL)
