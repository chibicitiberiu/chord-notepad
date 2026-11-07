package com.tibich.chordnotepad.ui.editor

import android.content.ClipData
import android.content.ClipboardManager
import com.tibich.chordnotepad.bridge.SpanKind

/** U+2060 WORD JOINER: no line break on either side, and it draws nothing. */
const val WORD_JOINER = '⁠'

/**
 * Where the text shown needs a word joiner so that soft wrapping never splits
 * a chord across two lines (L7: `D/F#` wrapped as `D/` and `F#`): the UTF-16
 * offsets inside a chord span right after a `/`, `-` or `+`, which the
 * platform's line breaker treats as break opportunities. Sorted, no
 * duplicates. The joiners are only in what's drawn, never in the song.
 */
fun chordJoinPoints(text: CharSequence, spans: List<PaintedSpan>): IntArray {
    val points = ArrayList<Int>()
    for (s in spans) {
        if (s.kind != SpanKind.CHORD && s.kind != SpanKind.CHORD_INVALID) continue
        val end = minOf(s.end, text.length)
        for (i in (s.start + 1) until end) {
            if (text[i - 1] in BREAKS_AFTER) points += i
        }
    }
    return points.distinct().sorted().toIntArray()
}

private const val BREAKS_AFTER = "/-+"

/**
 * The song's offsets in the text as drawn, with a [WORD_JOINER] before each
 * of [points] ([chordJoinPoints]).
 */
class JoinedText(private val points: IntArray) {
    /** No joiners. */
    val isEmpty: Boolean get() = points.isEmpty()

    /** [text] as drawn. */
    fun display(text: String): String {
        if (points.isEmpty()) return text
        val out = StringBuilder(text.length + points.size)
        var from = 0
        for (p in points) {
            if (p > text.length) break
            out.append(text, from, p).append(WORD_JOINER)
            from = p
        }
        return out.append(text, from, text.length).toString()
    }

    /**
     * Where the song's [offset] (the character there, or the boundary before
     * it) is in the drawn text: shifted by the joiners at or before it, so a
     * character keeps its own place. A span's start and end are never at a
     * joiner (they sit inside chords), so the same mapping serves both.
     */
    fun toDisplay(offset: Int): Int {
        if (points.isEmpty()) return offset
        // The number of points <= offset.
        var lo = 0
        var hi = points.size
        while (lo < hi) {
            val mid = (lo + hi) ushr 1
            if (points[mid] <= offset) lo = mid + 1 else hi = mid
        }
        return offset + lo
    }
}

/** [text] without the [WORD_JOINER]s the editor draws (what a copy from the field must hold). */
fun withoutJoiners(text: CharSequence): String = text.toString().replace(WORD_JOINER.toString(), "")

/**
 * The texts of a clip with the [WORD_JOINER]s taken out, or null when none
 * has one (nothing to rewrite). Compose copies the field's text as drawn,
 * joiners included; [JoinerFreeCopies] puts the clip back without them so
 * they don't follow into other apps.
 */
fun joinerFreeTexts(texts: List<CharSequence?>): List<String>? {
    if (texts.none { it != null && WORD_JOINER in it }) return null
    return texts.map { withoutJoiners(it ?: "") }
}

/**
 * While started, rewrites a new primary clip that holds word joiners
 * ([joinerFreeTexts]): a copy or cut from the wrapped editor. Compose's
 * `Clipboard` can't be wrapped for this (its text toolbar insists on the
 * platform's own and the app crashes on a long-press), so the system
 * clipboard is watched instead. The rewritten clip has no joiners, so it
 * doesn't trigger another rewrite.
 */
class JoinerFreeCopies(private val clipboard: ClipboardManager) : ClipboardManager.OnPrimaryClipChangedListener {
    /** Watch the clipboard. */
    fun start() = clipboard.addPrimaryClipChangedListener(this)

    /** Stop watching. */
    fun stop() = clipboard.removePrimaryClipChangedListener(this)

    override fun onPrimaryClipChanged() {
        val data = runCatching { clipboard.primaryClip }.getOrNull() ?: return
        if (data.itemCount == 0) return
        val texts = joinerFreeTexts((0 until data.itemCount).map { data.getItemAt(it).text }) ?: return
        val clean = ClipData.newPlainText(data.description.label, texts[0])
        for (i in 1 until texts.size) clean.addItem(ClipData.Item(texts[i]))
        runCatching { clipboard.setPrimaryClip(clean) }
    }
}
