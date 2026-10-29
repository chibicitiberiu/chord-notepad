package io.github.chibicitiberiu.chordnotepad.text

/**
 * Converts between the session's offsets (Unicode code points) and Kotlin's
 * (UTF-16 units) for one version of a text. The only place in the app that
 * does this conversion.
 *
 * Text without supplementary characters (no surrogate pairs; nearly every
 * song) maps one to one and costs nothing. Otherwise the mapper keeps the
 * UTF-16 start of each pair and converts with a binary search.
 *
 * A lone surrogate counts as one code point, as in Java and in Python.
 * Offsets outside the text are clamped to it; a UTF-16 offset in the middle
 * of a pair maps to the code point the pair starts.
 */
class OffsetMapper private constructor(
    /** Length of the text in UTF-16 units. */
    val utf16Length: Int,
    // UTF-16 index of each surrogate pair's high half, ascending.
    private val pairStarts: IntArray,
) {
    /** Length of the text in code points. */
    val codePointLength: Int = utf16Length - pairStarts.size

    /** True when both offset systems agree for this text. */
    val isIdentity: Boolean get() = pairStarts.isEmpty()

    /** The UTF-16 offset of code point [codePoint]. */
    fun toUtf16(codePoint: Int): Int {
        val cp = codePoint.coerceIn(0, codePointLength)
        if (isIdentity) return cp
        // Pair i sits at code point pairStarts[i] - i; count pairs before cp.
        var lo = 0
        var hi = pairStarts.size
        while (lo < hi) {
            val mid = (lo + hi) ushr 1
            if (pairStarts[mid] - mid < cp) lo = mid + 1 else hi = mid
        }
        return cp + lo
    }

    /** The code-point offset of UTF-16 offset [utf16]. */
    fun toCodePoint(utf16: Int): Int {
        val u = utf16.coerceIn(0, utf16Length)
        if (isIdentity) return u
        // Each pair starting before u counts one code point fewer. That also
        // holds when u is mid-pair: it maps to the pair's own code point.
        var lo = 0
        var hi = pairStarts.size
        while (lo < hi) {
            val mid = (lo + hi) ushr 1
            if (pairStarts[mid] < u) lo = mid + 1 else hi = mid
        }
        return u - lo
    }

    companion object {
        /** A mapper for [text] as it is now (rebuild it after every change). */
        fun of(text: CharSequence): OffsetMapper {
            var starts = EMPTY
            var count = 0
            var i = 0
            val n = text.length
            while (i < n - 1) {
                if (Character.isHighSurrogate(text[i]) && Character.isLowSurrogate(text[i + 1])) {
                    if (count == starts.size) starts = starts.copyOf(maxOf(8, count * 2))
                    starts[count++] = i
                    i += 2
                } else {
                    i++
                }
            }
            return OffsetMapper(n, if (count == 0) EMPTY else starts.copyOf(count))
        }

        private val EMPTY = IntArray(0)
    }
}
