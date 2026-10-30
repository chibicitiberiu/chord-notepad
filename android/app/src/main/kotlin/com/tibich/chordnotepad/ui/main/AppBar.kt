package com.tibich.chordnotepad.ui.main

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.material3.ripple
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.ui.UiTags
import com.tibich.chordnotepad.ui.icons.IconTints
import com.tibich.chordnotepad.ui.icons.MdiIcon
import com.tibich.chordnotepad.ui.theme.appColors

/**
 * The 48 dp app bar: ☰, the song's title (• while modified; tap to
 * rename), the Edit / Play tabs and Save. [trailing] fills the rest of the
 * line after Save (phone landscape: the Edit ribbon, the title hidden).
 */
@Composable
fun AppBar(
    title: String,
    modified: Boolean,
    mode: AppMode,
    showTitle: Boolean,
    onMenu: () -> Unit,
    onRename: () -> Unit,
    onMode: (AppMode) -> Unit,
    onSave: () -> Unit,
    modifier: Modifier = Modifier,
    trailing: (@Composable RowScope.() -> Unit)? = null,
) {
    val colors = appColors
    Row(
        modifier.height(BAR_HEIGHT_DP.dp).background(colors.surface).padding(start = 2.dp).testTag(UiTags.APP_BAR),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        BarIconButton(R.drawable.mdi_menu, stringResource(R.string.drawer_open), colors.muted, onMenu, Modifier.testTag(UiTags.MENU))
        if (showTitle) {
            SongTitle(title, modified, onRename, Modifier.weight(1f).testTag(UiTags.TITLE))
        }
        ModeTabs(mode, onMode)
        if (!showTitle && trailing == null) Box(Modifier.weight(1f))
        BarIconButton(R.drawable.mdi_content_save, stringResource(R.string.menu_save), IconTints.Save, onSave, Modifier.testTag(UiTags.SAVE))
        trailing?.invoke(this)
    }
}

/** The title button: the name, ellipsized, with a primary • while there are unsaved changes. */
@Composable
private fun SongTitle(title: String, modified: Boolean, onRename: () -> Unit, modifier: Modifier) {
    val colors = appColors
    val renameLabel = stringResource(R.string.rename_title)
    val text = remember(title, modified, colors.primary) {
        buildAnnotatedString {
            append(title)
            if (modified) withStyle(SpanStyle(color = colors.primary)) { append(" •") }
        }
    }
    Box(
        modifier
            .padding(end = 4.dp)
            .clip(RoundedCornerShape(8.dp))
            .clickable(onClickLabel = renameLabel, onClick = onRename)
            .padding(start = 2.dp, end = 6.dp, top = 8.dp, bottom = 8.dp),
    ) {
        Text(
            text,
            color = colors.text,
            fontSize = 17.sp,
            fontWeight = FontWeight.Medium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/** Edit / Play: Material tabs with an underline indicator. */
@Composable
fun ModeTabs(mode: AppMode, onMode: (AppMode) -> Unit, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxHeight().selectableGroup()) {
        ModeTab(AppMode.EDIT, R.drawable.mdi_pencil, stringResource(R.string.mode_edit), mode == AppMode.EDIT, onMode)
        ModeTab(AppMode.PLAY, R.drawable.mdi_play_circle, stringResource(R.string.mode_play), mode == AppMode.PLAY, onMode)
    }
}

@Composable
private fun ModeTab(target: AppMode, icon: Int, label: String, selected: Boolean, onMode: (AppMode) -> Unit) {
    val colors = appColors
    val color = if (selected) colors.primary else colors.muted
    Box(
        Modifier
            .fillMaxHeight()
            .testTag(if (target == AppMode.EDIT) UiTags.TAB_EDIT else UiTags.TAB_PLAY)
            .selectable(selected = selected, role = Role.Tab, onClick = { onMode(target) })
            .padding(horizontal = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            MdiIcon(icon, color, size = 19.dp)
            Text(label, color = color, fontSize = 14.sp, fontWeight = FontWeight.Medium, letterSpacing = 0.28.sp)
        }
        if (selected) {
            // Under the label, the tab's width minus its padding.
            Box(Modifier.matchParentSize()) {
                Box(
                    Modifier
                        .align(Alignment.BottomCenter)
                        .fillMaxWidth()
                        .height(3.dp)
                        .clip(RoundedCornerShape(topStart = 3.dp, topEnd = 3.dp))
                        .background(colors.primary),
                )
            }
        }
    }
}

/** A round 44 dp icon button in the app bar. */
@Composable
fun BarIconButton(icon: Int, description: String, tint: Color, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Box(
        modifier
            .size(44.dp)
            .clip(CircleShape)
            .clickable(
                interactionSource = null,
                indication = ripple(bounded = true),
                role = Role.Button,
                onClick = onClick,
            )
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        MdiIcon(icon, tint)
    }
}
