package io.github.chibicitiberiu.chordnotepad.ui.chordsheet

import androidx.compose.ui.graphics.Color
import io.github.chibicitiberiu.chordnotepad.ui.theme.AppColors
import kotlin.math.max
import kotlin.math.min

// The chord sheet's colours come from the op buffer (the desktop renderers'
// palette, src/chord_sheet/). The Android sheet keeps them in the light theme
// and maps them for the dark one (docs/design/android-ui-spec.md, "Chord
// sheet"): the strip takes the surface-low background, the playing column is
// translucent yellow, the hands' bars keep their blue and brown a little
// lighter, neutral inks and grids flip their lightness, and the other
// colours (voice parts, marker flags) are lifted to stay readable.

/** `renderer_interface.HAND_COLORS`: the right and left hands' bars. */
private const val HAND_RH = "#2a6f8a"
private const val HAND_LH = "#8a5a3a"

/** The piano-roll gutter's keys keep their look (an inverted keyboard reads wrong). */
private const val GUTTER_WHITE = "#ffffff"
private const val GUTTER_BLACK = "#31424a"

private val DarkRh = Color(0xFF78A6D8)
private val DarkLh = Color(0xFFD09A6C)
private val DarkGutterWhite = Color(0xFFD3D6DD)

/** Below this HSL saturation a colour counts as neutral (ink, grid, shading). */
private const val NEUTRAL_SATURATION = 0.3f

/** A buffer colour as the sheet paints it in [colors]' theme. */
fun themedSheetColor(spec: String, parsed: Color, colors: AppColors): Color {
    if (!colors.dark) return parsed
    return when (spec.lowercase()) {
        HAND_RH -> DarkRh
        HAND_LH -> DarkLh
        GUTTER_WHITE -> DarkGutterWhite
        GUTTER_BLACK -> parsed
        else -> darkVariant(parsed)
    }
}

/** [color] for a dark background: neutrals flip their lightness, hues get lighter. */
fun darkVariant(color: Color): Color {
    val r = color.red
    val g = color.green
    val b = color.blue
    val hi = max(r, max(g, b))
    val lo = min(r, min(g, b))
    val l = (hi + lo) / 2f
    val d = hi - lo
    val s = if (d == 0f) 0f else d / (1f - kotlin.math.abs(2f * l - 1f))
    val h = when {
        d == 0f -> 0f
        hi == r -> 60f * (((g - b) / d) % 6f)
        hi == g -> 60f * ((b - r) / d + 2f)
        else -> 60f * ((r - g) / d + 4f)
    }.let { if (it < 0f) it + 360f else it }
    val newL = if (s < NEUTRAL_SATURATION) 0.92f - 0.82f * l else max(l, 0.66f)
    return Color.hsl(h, s.coerceIn(0f, 1f), newL.coerceIn(0f, 1f), color.alpha)
}
