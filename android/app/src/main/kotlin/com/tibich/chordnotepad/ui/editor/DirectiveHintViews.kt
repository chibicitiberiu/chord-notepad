package com.tibich.chordnotepad.ui.editor

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.tibich.chordnotepad.ui.UiTags
import com.tibich.chordnotepad.ui.theme.appColors

/**
 * Edit mode's hint strip, under the text (so just above the keyboard when
 * it's open): the reason, in the error colour for an invalid directive, then
 * the syntax in monospace. The floating undo chip's family: surface-high,
 * muted text.
 */
@Composable
fun DirectiveHintStrip(card: HintCard, modifier: Modifier = Modifier) {
    val colors = appColors
    Column(modifier.background(colors.surfaceHigh).testTag(UiTags.HINT_STRIP)) {
        HorizontalDivider(color = colors.line)
        HintText(card, Modifier.padding(horizontal = 12.dp, vertical = 5.dp))
    }
}

/**
 * Play mode's explanation of a long-pressed directive: a small card by the
 * directive, in the hint strip's look (the caller places it).
 */
@Composable
fun DirectiveHintCard(card: HintCard, modifier: Modifier = Modifier) {
    Surface(
        modifier.widthIn(max = 340.dp).testTag(UiTags.HINT_POPUP),
        shape = RoundedCornerShape(12.dp),
        color = appColors.surfaceHigh,
        shadowElevation = 4.dp,
    ) {
        HintText(card, Modifier.padding(horizontal = 12.dp, vertical = 8.dp))
    }
}

@Composable
private fun HintText(card: HintCard, modifier: Modifier) {
    val colors = appColors
    Column(modifier.semantics { liveRegion = LiveRegionMode.Polite }) {
        if (card.reason.isNotEmpty()) {
            Text(
                card.reason,
                color = if (card.error) MaterialTheme.colorScheme.error else colors.muted,
                fontSize = 12.sp,
                lineHeight = 16.sp,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Text(
            card.syntax,
            color = colors.muted,
            fontFamily = FontFamily.Monospace,
            fontSize = 12.sp,
            lineHeight = 16.sp,
            maxLines = 4,
            overflow = TextOverflow.Ellipsis,
        )
    }
}
