package com.tibich.chordnotepad.ui.editor

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.text.input.InputTransformation
import androidx.compose.foundation.text.input.TextFieldBuffer

/**
 * The desktop's paste normalization (`utils/text_normalization.py`,
 * `normalize_song_text`): CRLF and lone CR become LF, non-breaking spaces
 * become spaces, zero-width spaces and BOMs are dropped. Keep the two in
 * step; `PasteNormalizationTest` lists the same cases as
 * `tests/test_paste_normalization.py`.
 */
fun normalizeSongText(text: CharSequence): String {
    val sb = StringBuilder(text.length)
    var i = 0
    while (i < text.length) {
        when (val c = text[i]) {
            '\r' -> {
                sb.append('\n')
                if (i + 1 < text.length && text[i + 1] == '\n') i++
            }
            '\u00a0' -> sb.append(' ')
            '\u200b', '\ufeff' -> Unit
            else -> sb.append(c)
        }
        i++
    }
    return sb.toString()
}

/** Whether [normalizeSongText] would change [text]. */
fun needsNormalizing(text: CharSequence): Boolean =
    text.any { it == '\r' || it == '\u00a0' || it == '\u200b' || it == '\ufeff' }

/**
 * Normalizes what the user adds to the editor, as the desktop does on paste.
 * Compose has no separate paste hook for a `TextFieldState`, so this runs on
 * every user edit; only the inserted text is touched, and typing never
 * produces these characters except a keyboard's non-breaking space, which
 * would break chord detection anyway.
 */
object PasteNormalization : InputTransformation {
    @OptIn(ExperimentalFoundationApi::class)
    override fun TextFieldBuffer.transformInput() {
        // Last change first, so earlier ranges stay valid while we replace.
        for (i in changes.changeCount - 1 downTo 0) {
            val range = changes.getRange(i)
            if (range.collapsed) continue
            val inserted = asCharSequence().subSequence(range.min, range.max)
            if (needsNormalizing(inserted)) replace(range.min, range.max, normalizeSongText(inserted))
        }
    }
}
