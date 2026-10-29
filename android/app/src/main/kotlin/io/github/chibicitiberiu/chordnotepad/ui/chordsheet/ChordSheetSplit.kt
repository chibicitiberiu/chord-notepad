package io.github.chibicitiberiu.chordnotepad.ui.chordsheet

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import io.github.chibicitiberiu.chordnotepad.bridge.PyHost
import io.github.chibicitiberiu.chordnotepad.ui.UiTags
import io.github.chibicitiberiu.chordnotepad.ui.theme.appColors
import kotlin.math.roundToInt

/** The smallest chord sheet the handle allows, in dp (header + a usable strip). */
const val MIN_CHORD_SHEET_HEIGHT_DP = 120f

/** The largest share of the window height the chord sheet may take. */
private const val MAX_SCREEN_FRACTION = 0.6f

/** The editor keeps at least this much height, whatever the sheet's stored height (keyboard up, landscape). */
internal const val MIN_EDITOR_HEIGHT_DP = 96f

/** Below this height the sheet is hidden instead (a phone in landscape with the keyboard up). */
internal const val MIN_SHOWN_CHORD_SHEET_HEIGHT_DP = 80f

/** What the split's neighbours below the sheet take: the handle (16), the divider and the status line. */
private const val RESERVED_BELOW_DP = 16f + 40f

/**
 * The sheet's height in dp, or null when there's no room for it (the editor
 * then keeps the screen: a soft keyboard on a phone leaves little, and so does a phone in landscape).
 *
 * @param wanted The stored height.
 * @param availableDp The height left for the editor and the sheet (the column
 *   below the toolbar, after the keyboard).
 * @param windowHeightDp The window's full height.
 */
internal fun chordSheetHeightDp(wanted: Float, availableDp: Float, windowHeightDp: Float): Float? {
    val cap = minOf(windowHeightDp * MAX_SCREEN_FRACTION, availableDp - MIN_EDITOR_HEIGHT_DP - RESERVED_BELOW_DP)
    if (cap < MIN_SHOWN_CHORD_SHEET_HEIGHT_DP) return null
    return wanted.coerceIn(minOf(MIN_CHORD_SHEET_HEIGHT_DP, cap), cap)
}

/**
 * The chord sheet as the lower half of a resizable split: a drag handle, then
 * [ChordSheetPane] at the session's stored height (`ChordSheetState.height`,
 * dp on Android). Dragging resizes live; releasing stores the height with
 * `set_chord_sheet_height`. Nothing at all while the sheet is hidden.
 * Put it under the editor, which takes the remaining space (`weight(1f)`).
 */
@Composable
fun ChordSheetSplit(host: PyHost, modifier: Modifier = Modifier) {
    val state by host.repository.chordSheet.collectAsState()
    val current = state ?: return
    if (!current.visible) return
    val density = LocalDensity.current.density
    val windowHeightDp = LocalWindowInfo.current.containerSize.height / density
    // The height while dragging, and after until the session echoes it back.
    var dragged by remember { mutableStateOf<Float?>(null) }

    LaunchedEffect(current.height) {
        if (dragged?.roundToInt() == current.height) dragged = null
    }

    BoxWithConstraints(modifier) {
        val height = chordSheetHeightDp(dragged ?: current.height.toFloat(), maxHeight.value, windowHeightDp)
            ?: return@BoxWithConstraints
        val maxDrag = minOf(windowHeightDp * MAX_SCREEN_FRACTION, maxHeight.value - MIN_EDITOR_HEIGHT_DP - RESERVED_BELOW_DP)
        val minDrag = minOf(MIN_CHORD_SHEET_HEIGHT_DP, maxDrag)
        Column {
            SplitHandle(
                onDrag = { dy -> dragged = ((dragged ?: height) - dy / density).coerceIn(minDrag, maxDrag) },
                onDragEnd = { dragged?.let { host.commands.setChordSheetHeight(it.roundToInt()) } },
            )
            ChordSheetPane(host, Modifier.fillMaxWidth().height(height.dp))
        }
    }
}

/** The split's grab bar: a pill on a thin strip at the top of the sheet, dragged vertically. */
@Composable
private fun SplitHandle(onDrag: (Float) -> Unit, onDragEnd: () -> Unit) {
    val colors = appColors
    Box(
        Modifier
            .fillMaxWidth()
            .height(14.dp)
            .testTag(UiTags.CHORD_SHEET_HANDLE)
            .background(colors.surfaceLow)
            .semantics { contentDescription = "Resize the chord sheet" }
            .draggable(
                state = rememberDraggableState(onDrag),
                orientation = Orientation.Vertical,
                onDragStopped = { onDragEnd() },
            ),
        contentAlignment = Alignment.Center,
    ) {
        Box(Modifier.align(Alignment.TopCenter).fillMaxWidth().height(1.dp).background(colors.line))
        Box(
            Modifier
                .size(width = 36.dp, height = 4.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(colors.grip),
        )
    }
}
