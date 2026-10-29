package io.github.chibicitiberiu.chordnotepad.ui.main

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.bridge.DocumentRef
import io.github.chibicitiberiu.chordnotepad.ui.UiTags
import io.github.chibicitiberiu.chordnotepad.ui.icons.IconTints
import io.github.chibicitiberiu.chordnotepad.ui.icons.MdiIcon
import io.github.chibicitiberiu.chordnotepad.ui.sheets.SheetSection
import io.github.chibicitiberiu.chordnotepad.ui.theme.appColors

/** What the drawer's entries do. */
interface DrawerActions {
    fun newSong()
    fun open()
    fun openRecent(ref: DocumentRef)
    fun saveAs()
    fun exportMidi()
    fun settings()
    fun userGuide()
    fun quickStart()
    fun about()
}

/**
 * The ☰ drawer, which replaces the old ⋮ menu: Documents (New song, Open…,
 * the recent songs inline, Save as…, Export MIDI…) and App (Settings, User
 * guide, Quick start, About). Each entry closes the drawer first ([close]).
 */
@Composable
fun AppDrawer(recent: List<DocumentRef>, actions: DrawerActions, close: () -> Unit) {
    val colors = appColors
    fun run(action: () -> Unit): () -> Unit = {
        close()
        action()
    }
    ModalDrawerSheet(
        modifier = Modifier.widthIn(max = 300.dp).fillMaxHeight().testTag(UiTags.DRAWER),
        drawerContainerColor = colors.surfaceLow,
        drawerContentColor = colors.text,
        drawerShape = RoundedCornerShape(topEnd = 16.dp, bottomEnd = 16.dp),
    ) {
        Column(
            Modifier.fillMaxHeight().verticalScroll(rememberScrollState()).systemBarsPadding()
                .padding(start = 10.dp, end = 10.dp, top = 24.dp, bottom = 10.dp),
        ) {
            Text(
                stringResource(R.string.app_name),
                Modifier.padding(start = 14.dp, end = 14.dp, top = 4.dp, bottom = 10.dp),
                fontSize = 18.sp,
                fontWeight = FontWeight.Medium,
            )
            DrawerItem(R.drawable.mdi_file_plus, IconTints.NewSong, stringResource(R.string.drawer_new), run(actions::newSong))
            DrawerItem(R.drawable.mdi_folder_open, IconTints.Open, stringResource(R.string.menu_open), run(actions::open))
            SheetSection(stringResource(R.string.drawer_recent), Modifier.padding(start = 8.dp))
            if (recent.isEmpty()) {
                Text(
                    stringResource(R.string.drawer_no_recent),
                    Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                    fontSize = 13.sp,
                    color = colors.muted,
                )
            }
            for (ref in recent) {
                DrawerItem(R.drawable.mdi_file_music, IconTints.Recent, ref.displayName, run { actions.openRecent(ref) })
            }
            DrawerSeparator()
            DrawerItem(R.drawable.mdi_content_save_edit, IconTints.Save, stringResource(R.string.drawer_save_as), run(actions::saveAs))
            DrawerItem(R.drawable.mdi_export, IconTints.Export, stringResource(R.string.menu_export_midi), run(actions::exportMidi))
            DrawerSeparator()
            DrawerItem(R.drawable.mdi_cog, IconTints.Settings, stringResource(R.string.menu_settings), run(actions::settings))
            DrawerItem(R.drawable.mdi_book_open_variant, IconTints.Guide, stringResource(R.string.drawer_user_guide), run(actions::userGuide))
            DrawerItem(R.drawable.mdi_school, IconTints.QuickStart, stringResource(R.string.drawer_quick_start), run(actions::quickStart))
            DrawerItem(R.drawable.mdi_information, IconTints.About, stringResource(R.string.drawer_about), run(actions::about))
        }
    }
}

@Composable
private fun DrawerItem(icon: Int, tint: Color, label: String, onClick: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 46.dp)
            .clip(RoundedCornerShape(23.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        MdiIcon(icon, tint)
        Text(label, fontSize = 14.sp, color = appColors.text, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun DrawerSeparator() {
    Box(Modifier.padding(horizontal = 10.dp, vertical = 8.dp).fillMaxWidth().height(1.dp).background(appColors.line))
}
