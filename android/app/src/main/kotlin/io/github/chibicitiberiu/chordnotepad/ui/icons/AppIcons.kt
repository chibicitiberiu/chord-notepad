package io.github.chibicitiberiu.chordnotepad.ui.icons

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.unit.dp

// The few icons the app needs, as vectors (no icon library: material3 no
// longer ships them and the extended set is megabytes). Paths are Material
// Design icons (Apache 2.0) on a 24 × 24 grid, except the metronome, drawn
// after the desktop's resources/icons/metronome.png.

private fun icon(name: String, vararg paths: String): ImageVector =
    ImageVector.Builder(name, 24.dp, 24.dp, 24f, 24f).apply {
        for (p in paths) addPath(addPathNodes(p), fill = SolidColor(Color.Black))
    }.build()

/** App icons. */
object AppIcons {
    /** Play (also Resume). */
    val Play: ImageVector = icon("Play", "M8,5v14l11,-7z")

    /** Pause. */
    val Pause: ImageVector = icon("Pause", "M6,19h4V5H6v14zM14,5v14h4V5h-4z")

    /** Stop. */
    val Stop: ImageVector = icon("Stop", "M6,6h12v12H6z")

    /** The overflow menu. */
    val MoreVert: ImageVector = icon(
        "MoreVert",
        "M12,8c1.1,0 2,-0.9 2,-2s-0.9,-2 -2,-2 -2,0.9 -2,2 0.9,2 2,2zM12,10c-1.1,0 -2,0.9 -2,2s0.9,2 2,2 " +
            "2,-0.9 2,-2 -0.9,-2 -2,-2zM12,16c-1.1,0 -2,0.9 -2,2s0.9,2 2,2 2,-0.9 2,-2 -0.9,-2 -2,-2z",
    )

    /** Expand (show the toolbar). */
    val ExpandMore: ImageVector = icon("ExpandMore", "M16.59,8.59L12,13.17 7.41,8.59 6,10l6,6 6,-6z")

    /** Collapse (hide the toolbar). */
    val ExpandLess: ImageVector = icon("ExpandLess", "M12,8l-6,6 1.41,1.41L12,10.83l4.59,4.58L18,14z")

    /** A submenu. */
    val ChevronRight: ImageVector = icon("ChevronRight", "M10,6L8.59,7.41 13.17,12l-4.58,4.59L10,18l6,-6z")

    /** Back from a submenu. */
    val ChevronLeft: ImageVector = icon("ChevronLeft", "M15.41,7.41L14,6l-6,6 6,6 1.41,-1.41L10.83,12z")

    /** Back from a screen. */
    val ArrowBack: ImageVector = icon("ArrowBack", "M20,11H7.83l5.59,-5.59L12,4l-8,8 8,8 1.41,-1.41L7.83,13H20v-2z")

    /** Drop-down caret. */
    val ArrowDropDown: ImageVector = icon("ArrowDropDown", "M7,10l5,5 5,-5z")

    /** The metronome: an outlined pyramid, its base filled, and the pendulum. */
    val Metronome: ImageVector = ImageVector.Builder("Metronome", 24.dp, 24.dp, 24f, 24f).apply {
        val ink = SolidColor(Color.Black)
        addPath(
            addPathNodes("M9.6,3.5h4.8l4.6,16.5H5z"),
            fill = null, stroke = ink, strokeLineWidth = 1.8f, strokeLineJoin = StrokeJoin.Round,
        )
        addPath(addPathNodes("M6.6,14.5h10.8l1.6,5.5H5z"), fill = ink)
        addPath(
            addPathNodes("M11.2,15L19,6.4"),
            fill = null, stroke = ink, strokeLineWidth = 1.8f, strokeLineCap = StrokeCap.Round,
        )
    }.build()
}
