package io.github.chibicitiberiu.chordnotepad.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.bridge.DocumentRef
import io.github.chibicitiberiu.chordnotepad.ui.icons.AppIcons

/** The submenus of the overflow menu (the desktop's menu bar, as far as M4 goes). */
private enum class MenuPage { ROOT, FILE, RECENT, EDIT, VIEW }

/**
 * The app bar's overflow menu: File, Edit and View as on the desktop, each a
 * page of its own (Android menus don't cascade). Playback, Tools and Help
 * come with their milestones (pickers in M4, the rest in M5).
 *
 * @param recent The Recent Files submenu.
 * @param canUndo Whether Edit › Undo does anything now.
 * @param canRedo Whether Edit › Redo does anything now.
 * @param onSelectAll Select the whole text in the editor.
 */
@Composable
fun OverflowMenu(
    actions: MainActions,
    recent: List<DocumentRef>,
    canUndo: Boolean,
    canRedo: Boolean,
    onSelectAll: () -> Unit,
) {
    var open by remember { mutableStateOf(false) }
    var page by remember { mutableStateOf(MenuPage.ROOT) }
    fun close() {
        open = false
        page = MenuPage.ROOT
    }
    fun run(action: () -> Unit): () -> Unit = {
        close()
        action()
    }

    Box {
        IconButton(onClick = { open = true }) {
            Icon(AppIcons.MoreVert, contentDescription = stringResource(R.string.menu_more))
        }
        DropdownMenu(expanded = open, onDismissRequest = ::close) {
            when (page) {
                MenuPage.ROOT -> {
                    Submenu(stringResource(R.string.menu_file)) { page = MenuPage.FILE }
                    Submenu(stringResource(R.string.menu_edit)) { page = MenuPage.EDIT }
                    Submenu(stringResource(R.string.menu_view)) { page = MenuPage.VIEW }
                }
                MenuPage.FILE -> {
                    Back(stringResource(R.string.menu_file)) { page = MenuPage.ROOT }
                    Item(stringResource(R.string.menu_new), "Ctrl+N", run(actions::newDocument))
                    Item(stringResource(R.string.menu_open), "Ctrl+O", run(actions::openDocument))
                    Item(stringResource(R.string.menu_save), "Ctrl+S", run(actions::save))
                    Item(stringResource(R.string.menu_save_as), "Ctrl+Shift+S", run(actions::saveAs))
                    Item(stringResource(R.string.menu_export_midi), null, run(actions::exportMidi))
                    HorizontalDivider()
                    Submenu(stringResource(R.string.menu_recent)) { page = MenuPage.RECENT }
                }
                MenuPage.RECENT -> {
                    Back(stringResource(R.string.menu_recent)) { page = MenuPage.FILE }
                    if (recent.isEmpty()) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.menu_no_recent)) },
                            onClick = {},
                            enabled = false,
                        )
                    }
                    for (ref in recent) {
                        DropdownMenuItem(
                            text = { Text(ref.displayName) },
                            onClick = run { actions.openRecent(ref) },
                        )
                    }
                }
                MenuPage.EDIT -> {
                    Back(stringResource(R.string.menu_edit)) { page = MenuPage.ROOT }
                    Item(stringResource(R.string.menu_undo), "Ctrl+Z", run(actions::undo), enabled = canUndo)
                    Item(stringResource(R.string.menu_redo), "Ctrl+Y", run(actions::redo), enabled = canRedo)
                    HorizontalDivider()
                    Item(stringResource(R.string.menu_select_all), "Ctrl+A", run(onSelectAll))
                }
                MenuPage.VIEW -> {
                    Back(stringResource(R.string.menu_view)) { page = MenuPage.ROOT }
                    Item(stringResource(R.string.menu_font_bigger), "Ctrl+Plus", run { actions.stepFontSize(1) })
                    Item(stringResource(R.string.menu_font_smaller), "Ctrl+Minus", run { actions.stepFontSize(-1) })
                    Item(stringResource(R.string.menu_font_reset), "Ctrl+0", run(actions::resetFontSize))
                }
            }
        }
    }
}

@Composable
private fun Item(label: String, shortcut: String?, onClick: () -> Unit, enabled: Boolean = true) {
    DropdownMenuItem(
        text = { Text(label) },
        onClick = onClick,
        enabled = enabled,
        trailingIcon = shortcut?.let {
            { Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        },
    )
}

@Composable
private fun Submenu(label: String, onOpen: () -> Unit) {
    DropdownMenuItem(
        text = { Text(label) },
        onClick = onOpen,
        trailingIcon = { Icon(AppIcons.ChevronRight, contentDescription = null) },
    )
}

@Composable
private fun Back(label: String, onBack: () -> Unit) {
    DropdownMenuItem(
        text = { Text(label, style = MaterialTheme.typography.titleSmall) },
        onClick = onBack,
        leadingIcon = { Icon(AppIcons.ChevronLeft, contentDescription = stringResource(R.string.menu_back)) },
    )
    HorizontalDivider()
}
