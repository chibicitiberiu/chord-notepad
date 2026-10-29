package io.github.chibicitiberiu.chordnotepad.ui.chordsheet

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import io.github.chibicitiberiu.chordnotepad.bridge.PyHost
import kotlin.math.roundToInt

/** The smallest chord sheet the handle allows, in dp (header + a usable strip). */
const val MIN_CHORD_SHEET_HEIGHT_DP = 120f

/** The largest share of the window height the chord sheet may take. */
private const val MAX_SCREEN_FRACTION = 0.6f

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
    val maxHeight = (windowHeightDp * MAX_SCREEN_FRACTION).coerceAtLeast(MIN_CHORD_SHEET_HEIGHT_DP)
    // The height while dragging, and after until the session echoes it back.
    var dragged by remember { mutableStateOf<Float?>(null) }
    val height = (dragged ?: current.height.toFloat()).coerceIn(MIN_CHORD_SHEET_HEIGHT_DP, maxHeight)

    LaunchedEffect(current.height) {
        if (dragged?.roundToInt() == current.height) dragged = null
    }

    Column(modifier) {
        SplitHandle(
            onDrag = { dy -> dragged = ((dragged ?: height) - dy / density).coerceIn(MIN_CHORD_SHEET_HEIGHT_DP, maxHeight) },
            onDragEnd = { dragged?.let { host.commands.setChordSheetHeight(it.roundToInt()) } },
        )
        ChordSheetPane(host, Modifier.fillMaxWidth().height(height.dp))
    }
}

/** The split's grab bar: a pill on a thin strip, dragged vertically. */
@Composable
private fun SplitHandle(onDrag: (Float) -> Unit, onDragEnd: () -> Unit) {
    Box(
        Modifier
            .fillMaxWidth()
            .height(16.dp)
            .semantics { contentDescription = "Resize the chord sheet" }
            .draggable(
                state = rememberDraggableState(onDrag),
                orientation = Orientation.Vertical,
                onDragStopped = { onDragEnd() },
            ),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            Modifier
                .size(width = 36.dp, height = 4.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(MaterialTheme.colorScheme.outlineVariant),
        )
    }
}
