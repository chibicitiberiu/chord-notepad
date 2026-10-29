package io.github.chibicitiberiu.chordnotepad.ui.help

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.viewinterop.AndroidView
import androidx.webkit.WebViewAssetLoader
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.ui.about.openLink
import io.github.chibicitiberiu.chordnotepad.ui.icons.AppIcons

/**
 * Help › User Guide: the Sphinx guide built into `assets/help/`, shown in a
 * WebView that can only reach those assets (served over an https origin by
 * `WebViewAssetLoader`; the app has no INTERNET permission). Links to other
 * sites open in the browser when tapped. Back goes back through the guide's
 * pages first and leaves the screen when there is nothing to go back to.
 *
 * JavaScript is on because the guide's theme needs it for its menu and
 * search; no file or content access is allowed and nothing is loaded from
 * the network.
 *
 * @param onClose Leave the screen.
 */
@OptIn(ExperimentalMaterial3Api::class)
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun UserGuideScreen(onClose: () -> Unit) {
    val context = LocalContext.current
    val linkFailed = stringResource(R.string.about_open_failed)
    // The page shown, kept over rotation (the WebView's own history is not).
    var lastUrl by rememberSaveable { mutableStateOf(HelpLinks.START_URL) }
    val webView = remember { arrayOfNulls<WebView>(1) }

    BackHandler {
        val view = webView[0]
        if (view != null && view.canGoBack()) view.goBack() else onClose()
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.user_guide_title)) },
                navigationIcon = {
                    IconButton(onClick = onClose) {
                        Icon(AppIcons.ArrowBack, contentDescription = stringResource(R.string.licences_back))
                    }
                },
            )
        },
    ) { padding ->
        AndroidView(
            modifier = Modifier.fillMaxSize().padding(padding),
            factory = { ctx ->
                val loader = WebViewAssetLoader.Builder()
                    .setDomain(HelpLinks.HOST)
                    .addPathHandler("/assets/", WebViewAssetLoader.AssetsPathHandler(ctx))
                    .build()
                WebView(ctx).apply {
                    settings.javaScriptEnabled = true
                    settings.allowFileAccess = false
                    settings.allowContentAccess = false
                    settings.setGeolocationEnabled(false)
                    webViewClient = object : WebViewClient() {
                        override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
                            val url = request.url.toString()
                            if (!HelpLinks.isInternal(url)) return blocked()
                            return loader.shouldInterceptRequest(request.url) ?: blocked(404)
                        }

                        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                            val url = request.url.toString()
                            if (HelpLinks.isInternal(url)) return false
                            if (HelpLinks.isExternal(url) && !openLink(ctx, url)) {
                                Toast.makeText(ctx, linkFailed, Toast.LENGTH_SHORT).show()
                            }
                            return true
                        }

                        override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
                            if (HelpLinks.isInternal(url)) lastUrl = url
                        }
                    }
                    webView[0] = this
                    loadUrl(lastUrl)
                }
            },
            onRelease = { webView[0] = null; it.destroy() },
        )
    }
}

private fun blocked(status: Int = 403): WebResourceResponse =
    WebResourceResponse("text/plain", "utf-8", status, "Blocked", emptyMap(), "".byteInputStream())
