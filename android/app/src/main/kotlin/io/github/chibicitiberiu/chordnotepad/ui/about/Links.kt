package io.github.chibicitiberiu.chordnotepad.ui.about

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log

/**
 * Opens [url] in whatever app handles it (the browser). The app has no
 * INTERNET permission, so this is the only way a link is followed, and only
 * when the user taps one. Returns false when nothing can open it.
 */
fun openLink(context: Context, url: String): Boolean = try {
    context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    true
} catch (e: ActivityNotFoundException) {
    Log.w("CNAbout", "Nothing opens $url", e)
    false
}
