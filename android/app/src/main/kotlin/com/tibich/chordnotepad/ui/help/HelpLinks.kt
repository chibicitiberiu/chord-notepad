package com.tibich.chordnotepad.ui.help

/**
 * Where the bundled User Guide lives. `androidx.webkit.WebViewAssetLoader`
 * serves `assets/help/` over this https origin; nothing else is ever loaded
 * and the app has no INTERNET permission.
 */
object HelpLinks {
    /** The host WebViewAssetLoader answers for. */
    const val HOST = "appassets.androidplatform.net"

    /** The asset path prefix the guide is served under (assets/help/). */
    const val PATH = "/assets/help/"

    /** The guide's first page. */
    const val START_URL = "https://$HOST${PATH}index.html"

    /** True when [url] is a page of the bundled guide (loads in the WebView). */
    fun isInternal(url: String): Boolean = url.startsWith("https://$HOST$PATH")

    /** True when [url] should open in another app (a web link the guide mentions). */
    fun isExternal(url: String): Boolean = !isInternal(url) &&
        (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("mailto:"))
}
