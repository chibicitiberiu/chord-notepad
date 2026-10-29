package io.github.chibicitiberiu.chordnotepad.ui.settings

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.addPathNodes
import androidx.compose.ui.unit.dp

// The Settings screen's icons, drawn like ui/icons/AppIcons (Material Design
// paths, Apache 2.0, on a 24 × 24 grid; no icon library).

private fun icon(name: String, path: String): ImageVector =
    ImageVector.Builder(name, 24.dp, 24.dp, 24f, 24f)
        .apply { addPath(addPathNodes(path), fill = SolidColor(Color.Black)) }
        .build()

/** Icons of the Settings screen. */
object SettingsIcons {
    /** Add (a voicing, a voice). */
    val Add: ImageVector = icon("Add", "M19,13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z")

    /** Decrease (a spinner). */
    val Remove: ImageVector = icon("Remove", "M19,13H5v-2h14v2z")

    /** Delete (a voicing). */
    val Delete: ImageVector = icon(
        "Delete",
        "M6,19c0,1.1 0.9,2 2,2h8c1.1,0 2,-0.9 2,-2V7H6v12zM19,4h-3.5l-1,-1h-5l-1,1H5v2h14V4z",
    )

    /** Rename. */
    val Edit: ImageVector = icon(
        "Edit",
        "M3,17.25V21h3.75L17.81,9.94l-3.75,-3.75L3,17.25zM20.71,7.04c0.39,-0.39 0.39,-1.02 0,-1.41" +
            "l-2.34,-2.34c-0.39,-0.39 -1.02,-0.39 -1.41,0l-1.83,1.83 3.75,3.75 1.83,-1.83z",
    )

    /** An invalid voicing. */
    val Error: ImageVector = icon(
        "Error",
        "M12,2C6.48,2 2,6.48 2,12s4.48,10 10,10 10,-4.48 10,-10S17.52,2 12,2zM13,17h-2v-2h2v2zM13,13h-2V7h2v6z",
    )

    /** Remove a row. */
    val Close: ImageVector = icon(
        "Close",
        "M19,6.41L17.59,5 12,10.59 6.41,5 5,6.41 10.59,12 5,17.59 6.41,19 12,13.41 17.59,19 19,17.59 13.41,12z",
    )
}
