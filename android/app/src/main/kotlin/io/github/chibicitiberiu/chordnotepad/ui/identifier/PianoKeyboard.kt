package io.github.chibicitiberiu.chordnotepad.ui.identifier

/**
 * One key of the chord identifier's piano. [name] is spelled with sharps,
 * as the session sends notes back; [midi] is 60 for C4 (middle C).
 */
data class PianoKey(
    val name: String,
    val octave: Int,
    val midi: Int,
    val isBlack: Boolean,
    /** Left edge in white-key widths from the keyboard's left edge. */
    val left: Float,
    /** Width in white-key widths (1 for white keys). */
    val width: Float,
)

/**
 * The desktop identifier's keyboard (`ui/chord_identifier.py`, `PianoRoll`):
 * [octaves] octaves from C of [baseOctave], seven white keys each, the black
 * keys two thirds as wide and two thirds as tall as a white key, their left
 * edges 0.7 white keys past C, D, F, G and A.
 */
class PianoKeyboard(val baseOctave: Int = 4, val octaves: Int = 2) {
    /** Every key, white keys first (left to right), then black keys (left to right). */
    val keys: List<PianoKey> = buildList {
        for (o in 0 until octaves) {
            WHITE.forEachIndexed { i, step ->
                add(key(step, baseOctave + o, (o * 7 + i).toFloat(), 1f, black = false))
            }
        }
        for (o in 0 until octaves) {
            BLACK.forEach { (pos, step) ->
                add(key(step, baseOctave + o, o * 7 + pos, BLACK_WIDTH, black = true))
            }
        }
    }

    /** The number of white keys across. */
    val whiteKeyCount: Int = octaves * 7

    /**
     * The key at ([x], [y]) on a keyboard [width] × [height] px, black keys
     * first (they lie on top, over the upper [BLACK_HEIGHT] of the keyboard);
     * null outside it.
     */
    fun keyAt(x: Float, y: Float, width: Float, height: Float): PianoKey? {
        if (width <= 0f || height <= 0f || x < 0f || y < 0f || x >= width || y >= height) return null
        val unit = width / whiteKeyCount
        val u = x / unit
        if (y < height * BLACK_HEIGHT) {
            keys.firstOrNull { it.isBlack && u >= it.left && u < it.left + it.width }?.let { return it }
        }
        return keys.firstOrNull { !it.isBlack && u >= it.left && u < it.left + it.width }
    }

    /** The keys whose MIDI numbers are in [midi] (selected notes outside the keyboard are skipped). */
    fun selected(midi: Collection<Int>): Set<PianoKey> = keys.filterTo(mutableSetOf()) { it.midi in midi }

    companion object {
        /** Note names by semitone above C, spelled with sharps (the desktop's `NOTE_NAMES`). */
        val NOTE_NAMES: List<String> = listOf("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

        /** A black key's width, in white-key widths (20 px of 30 on the desktop). */
        const val BLACK_WIDTH: Float = 2f / 3f

        /** A black key's height, as a fraction of the keyboard's (80 px of 120). */
        const val BLACK_HEIGHT: Float = 2f / 3f

        /** MIDI number of [step] semitones above C in [octave] (C4 = 60). */
        fun midiOf(step: Int, octave: Int): Int = (octave + 1) * 12 + step

        private val WHITE = listOf(0, 2, 4, 5, 7, 9, 11)
        private val BLACK = listOf(0.7f to 1, 1.7f to 3, 3.7f to 6, 4.7f to 8, 5.7f to 10)

        private fun key(step: Int, octave: Int, left: Float, width: Float, black: Boolean) =
            PianoKey(NOTE_NAMES[step], octave, midiOf(step, octave), black, left, width)
    }
}
