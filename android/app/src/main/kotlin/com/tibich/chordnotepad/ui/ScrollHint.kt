package com.tibich.chordnotepad.ui

import androidx.compose.foundation.ScrollState
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** Within this many px of the end counts as at the end. */
private const val END_SLOP_PX = 2

/** Whether a scroll at [value] of [max] has more below (0 when everything fits). */
fun moreBelow(value: Int, max: Int): Boolean = value < max - END_SLOP_PX

/**
 * A fade into [color] along the bottom edge while [state] has more to scroll
 * to, so a list or form cut exactly at the edge says there's more (L9: the
 * Insert sheet's Loop row, the Loop dialog's count, the Suggest Capo list).
 * Put it before the `verticalScroll` it describes, so it stays at the edge.
 */
fun Modifier.moreBelowFade(state: ScrollState, color: Color, height: Dp = 28.dp): Modifier = drawWithContent {
    drawContent()
    if (moreBelow(state.value, state.maxValue)) {
        val h = height.toPx().coerceAtMost(size.height / 2)
        drawRect(
            Brush.verticalGradient(listOf(Color.Transparent, color), startY = size.height - h, endY = size.height),
            topLeft = Offset(0f, size.height - h),
            size = Size(size.width, h),
        )
    }
}
