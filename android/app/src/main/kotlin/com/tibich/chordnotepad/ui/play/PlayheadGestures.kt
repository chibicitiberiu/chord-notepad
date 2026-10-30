package com.tibich.chordnotepad.ui.play

import com.tibich.chordnotepad.bridge.SpanKind
import com.tibich.chordnotepad.ui.editor.PaintedSpan

// Play mode's touch rules (docs/design/android-ui-spec.md, "Modes"), as plain
// geometry so they can be tested without a device: a tap on a chord moves the
// playhead there and plays it, a tap elsewhere moves it to the nearest chord,
// and a drag that starts on the playhead marker scrubs it chord by chord.

/**
 * Where one chord sits on screen, in the text layout's pixels: its UTF-16
 * range and the box from its first to its last character on its line.
 */
data class ChordBox(val start: Int, val end: Int, val left: Float, val top: Float, val right: Float, val bottom: Float) {
    /** Whether ([x], [y]) is inside the box, grown by [slop] on every side. */
    fun contains(x: Float, y: Float, slop: Float = 0f): Boolean =
        x >= left - slop && x <= right + slop && y >= top - slop && y <= bottom + slop
}

/** What a tap in Play mode does. */
sealed interface PlayTap {
    /** The tap landed on a chord: move the playhead there and play it (`tap_chord_at`). */
    data class OnChord(val start: Int) : PlayTap

    /** The tap missed every chord: move the playhead to the nearest one (`set_playhead`). */
    data class Nearest(val start: Int) : PlayTap
}

/** The chords the playhead can stop at: the valid chord spans, in text order. */
fun playableChords(spans: List<PaintedSpan>): List<PaintedSpan> =
    spans.filter { it.kind == SpanKind.CHORD && it.end > it.start }.sortedBy { it.start }

/**
 * The chord nearest to ([x], [y]), preferring the same line: the distance is
 * the vertical gap × 4 plus the horizontal gap (zero inside a box), as the
 * agreed mockup measures it. Null when there are no chords.
 */
fun nearestChord(boxes: List<ChordBox>, x: Float, y: Float): ChordBox? {
    var best: ChordBox? = null
    var bestDistance = Float.POSITIVE_INFINITY
    for (b in boxes) {
        val dy = when {
            y < b.top -> b.top - y
            y > b.bottom -> y - b.bottom
            else -> 0f
        }
        val dx = when {
            x < b.left -> b.left - x
            x > b.right -> x - b.right
            else -> 0f
        }
        val d = dy * 4f + dx
        if (d < bestDistance) {
            bestDistance = d
            best = b
        }
    }
    return best
}

/**
 * What a tap at ([x], [y]) does: [PlayTap.OnChord] when it lands on a chord
 * (within [slop] px), else [PlayTap.Nearest]; null without chords.
 */
fun resolveTap(boxes: List<ChordBox>, x: Float, y: Float, slop: Float): PlayTap? {
    val hit = boxes.firstOrNull { it.contains(x, y) } ?: boxes.firstOrNull { it.contains(x, y, slop) }
    if (hit != null) return PlayTap.OnChord(hit.start)
    return nearestChord(boxes, x, y)?.let { PlayTap.Nearest(it.start) }
}

/**
 * Whether a touch at ([x], [y]) grabs the playhead marker drawn before
 * [marker]: a strip [grabWidth] px wide centred on the chord's left edge,
 * from [grabWidth] / 2 above the line (the marker's triangle) to its bottom.
 */
fun grabsMarker(marker: ChordBox?, x: Float, y: Float, grabWidth: Float): Boolean {
    if (marker == null) return false
    val half = grabWidth / 2f
    return x >= marker.left - half && x <= marker.left + half && y >= marker.top - half && y <= marker.bottom + half / 2f
}

/**
 * The chord a scrub at ([x], [y]) moves the playhead to, or null when it
 * stays on [current] (the start of the chord it's on now).
 */
fun scrubTarget(boxes: List<ChordBox>, current: Int?, x: Float, y: Float): Int? =
    nearestChord(boxes, x, y)?.start?.takeIf { it != current }

/**
 * The chord the playhead marker sits before: the playable chord that starts
 * at [playhead] (UTF-16), else the first one after it, else none.
 */
fun markerChord(chords: List<PaintedSpan>, playhead: Int?): PaintedSpan? {
    if (playhead == null) return null
    return chords.firstOrNull { playhead >= it.start && playhead < it.end } ?: chords.firstOrNull { it.start >= playhead }
}

/**
 * The directives a long-press explains in Play mode: the invalid (red) and
 * the redundant (faded) ones, in text order.
 */
fun explainableDirectives(spans: List<PaintedSpan>): List<PaintedSpan> =
    spans.filter {
        (it.kind == SpanKind.DIRECTIVE_INVALID || it.kind == SpanKind.DIRECTIVE_REDUNDANT) && it.end > it.start
    }.sortedBy { it.start }

/** The explainable directive under ([x], [y]) (within [slop] px), or null. */
fun explainableAt(boxes: List<ChordBox>, x: Float, y: Float, slop: Float): ChordBox? =
    boxes.firstOrNull { it.contains(x, y) } ?: boxes.firstOrNull { it.contains(x, y, slop) }
