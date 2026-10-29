package io.github.chibicitiberiu.chordnotepad.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.bridge.SessionRepository
import io.github.chibicitiberiu.chordnotepad.ui.icons.AppIcons
import io.github.chibicitiberiu.chordnotepad.ui.menus.FamilyMenuItems
import io.github.chibicitiberiu.chordnotepad.ui.menus.InstrumentSheet
import io.github.chibicitiberiu.chordnotepad.ui.menus.ProgramMenuItems
import io.github.chibicitiberiu.chordnotepad.ui.menus.VoicingMenuItems
import io.github.chibicitiberiu.chordnotepad.ui.menus.VoicingSheet
import io.github.chibicitiberiu.chordnotepad.ui.menus.instrumentFamilies
import io.github.chibicitiberiu.chordnotepad.ui.menus.recentEntries
import io.github.chibicitiberiu.chordnotepad.ui.menus.voicingRows
import io.github.chibicitiberiu.chordnotepad.ui.tools.ConvertPageItems
import io.github.chibicitiberiu.chordnotepad.ui.tools.InsertPageItems
import io.github.chibicitiberiu.chordnotepad.ui.tools.ToolActions
import io.github.chibicitiberiu.chordnotepad.ui.tools.ToolPopup
import io.github.chibicitiberiu.chordnotepad.ui.tools.ToolPopups
import io.github.chibicitiberiu.chordnotepad.ui.tools.ToolsPageItems

/** The submenus of the overflow menu (the desktop's menu bar, as far as M4 goes). */
private enum class MenuPage { ROOT, FILE, RECENT, EDIT, VIEW, PLAYBACK, VOICING, INSTRUMENT, FAMILY, HELP, TOOLS, INSERT, CONVERT }

/** What the overflow menu opened outside itself. */
private enum class MenuPopup { NONE, VOICING_SHEET, INSTRUMENT_SHEET, FONT }

/**
 * The app bar's overflow menu: File, Edit, View and Playback as on the
 * desktop, each a page of its own (Android menus don't cascade). On phones
 * ([compact]) Voicing and Instrument open bottom sheets instead of pages.
 * Tools comes with M5; Help has About so far, with User Guide and Quick
 * Start to join it. There is no File › Exit: Back closes the app, asking
 * about unsaved changes first (`MainScreen`).
 *
 * @param repo The session's states the menus show.
 * @param canUndo Whether Edit › Undo does anything now.
 * @param canRedo Whether Edit › Redo does anything now.
 * @param onSelectAll Select the whole text in the editor.
 * @param compact Phone-sized window: pickers as bottom sheets.
 * @param onAbout Open Help › About.
 * @param tools What Tools does (its pages are in `ui/tools/ToolsMenu.kt`).
 */
@Composable
fun OverflowMenu(
    actions: MainActions,
    repo: SessionRepository,
    canUndo: Boolean,
    canRedo: Boolean,
    onSelectAll: () -> Unit,
    compact: Boolean,
    onAbout: () -> Unit,
    tools: ToolActions,
) {
    val recent by repo.recentDocuments.collectAsState()
    val voicing by repo.voicingMenu.collectAsState()
    val instrument by repo.instrumentMenu.collectAsState()
    val chordSheet by repo.chordSheet.collectAsState()
    val editor by repo.editor.collectAsState()
    var open by remember { mutableStateOf(false) }
    var page by remember { mutableStateOf(MenuPage.ROOT) }
    var family by remember { mutableIntStateOf(0) }
    var popup by rememberSaveable { mutableStateOf(MenuPopup.NONE) }
    var toolPopup by rememberSaveable { mutableStateOf(ToolPopup.NONE) }
    fun close() {
        open = false
        page = MenuPage.ROOT
    }
    fun run(action: () -> Unit): () -> Unit = {
        close()
        action()
    }
    fun show(p: MenuPopup) {
        close()
        popup = p
    }
    fun showTool(p: ToolPopup) {
        close()
        toolPopup = p
    }
    val toolRow: @Composable (String, Boolean, () -> Unit) -> Unit = { label, submenu, onClick ->
        if (submenu) Submenu(label, onOpen = onClick) else Item(label, null, onClick)
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
                    Submenu(stringResource(R.string.menu_playback)) { page = MenuPage.PLAYBACK }
                    Submenu(stringResource(R.string.menu_tools)) { page = MenuPage.TOOLS }
                    // Settings (M5c) goes here: help/*.rst names it ⋮ → Settings.
                    Submenu(stringResource(R.string.menu_help)) { page = MenuPage.HELP }
                }
                MenuPage.HELP -> {
                    Back(stringResource(R.string.menu_help)) { page = MenuPage.ROOT }
                    // M5 adds User Guide and Quick Start above About, as on the desktop.
                    Item(stringResource(R.string.menu_about), null, run(onAbout))
                }
                MenuPage.TOOLS -> {
                    Back(stringResource(R.string.menu_tools)) { page = MenuPage.ROOT }
                    ToolsPageItems(
                        tools = tools,
                        row = toolRow,
                        run = ::run,
                        openInsert = { page = MenuPage.INSERT },
                        openConvert = { page = MenuPage.CONVERT },
                        show = ::showTool,
                    )
                }
                MenuPage.INSERT -> {
                    Back(stringResource(R.string.menu_insert)) { page = MenuPage.TOOLS }
                    InsertPageItems(tools, toolRow, ::run)
                }
                MenuPage.CONVERT -> {
                    Back(stringResource(R.string.menu_convert)) { page = MenuPage.TOOLS }
                    ConvertPageItems(tools, toolRow, ::run)
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
                    val items = recentEntries(recent)
                    if (items.isEmpty()) {
                        DropdownMenuItem(
                            text = { Text(stringResource(R.string.menu_no_recent)) },
                            onClick = {},
                            enabled = false,
                        )
                    }
                    for (ref in items) {
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
                    Item(stringResource(R.string.menu_font), null, { show(MenuPopup.FONT) }, enabled = editor != null)
                    HorizontalDivider()
                    val sheet = chordSheet
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.menu_chord_sheet)) },
                        onClick = run { if (sheet != null) actions.setChordSheetVisible(!sheet.visible) },
                        enabled = sheet != null,
                        trailingIcon = { Checkbox(checked = sheet?.visible == true, onCheckedChange = null) },
                    )
                    HorizontalDivider()
                    Item(stringResource(R.string.menu_font_bigger), "Ctrl+Plus", run { actions.stepFontSize(1) })
                    Item(stringResource(R.string.menu_font_smaller), "Ctrl+Minus", run { actions.stepFontSize(-1) })
                    Item(stringResource(R.string.menu_font_reset), "Ctrl+0", run(actions::resetFontSize))
                }
                MenuPage.PLAYBACK -> {
                    Back(stringResource(R.string.menu_playback)) { page = MenuPage.ROOT }
                    Submenu(stringResource(R.string.menu_voicing), enabled = voicing != null) {
                        if (compact) show(MenuPopup.VOICING_SHEET) else page = MenuPage.VOICING
                    }
                    Submenu(stringResource(R.string.menu_instrument), enabled = instrument != null) {
                        if (compact) show(MenuPopup.INSTRUMENT_SHEET) else page = MenuPage.INSTRUMENT
                    }
                }
                MenuPage.VOICING -> {
                    Back(stringResource(R.string.menu_voicing)) { page = MenuPage.PLAYBACK }
                    voicing?.let { VoicingMenuItems(voicingRows(it)) { value ->
                            close()
                            actions.setVoicing(value)
                        } }
                }
                MenuPage.INSTRUMENT -> {
                    Back(stringResource(R.string.menu_instrument)) { page = MenuPage.PLAYBACK }
                    instrument?.let {
                        FamilyMenuItems(instrumentFamilies(it)) { index ->
                            family = index
                            page = MenuPage.FAMILY
                        }
                    }
                }
                MenuPage.FAMILY -> {
                    val row = instrument?.let { instrumentFamilies(it).getOrNull(family) }
                    Back(row?.name.orEmpty()) { page = MenuPage.INSTRUMENT }
                    row?.let { ProgramMenuItems(it) { program ->
                            close()
                            actions.setInstrument(program)
                        } }
                }
            }
        }
    }

    MenuPopups(popup, actions, repo) { popup = MenuPopup.NONE }
    ToolPopups(toolPopup, tools, repo, compact) { toolPopup = ToolPopup.NONE }
}

/** The bottom sheets and the font dialog the menu opened; [onClose] when they're done. */
@Composable
private fun MenuPopups(popup: MenuPopup, actions: MainActions, repo: SessionRepository, onClose: () -> Unit) {
    when (popup) {
        MenuPopup.NONE -> Unit
        MenuPopup.VOICING_SHEET -> {
            val state by repo.voicingMenu.collectAsState()
            state?.let { VoicingSheet(voicingRows(it), actions::setVoicing, onClose) }
        }
        MenuPopup.INSTRUMENT_SHEET -> {
            val state by repo.instrumentMenu.collectAsState()
            state?.let { InstrumentSheet(instrumentFamilies(it), actions::setInstrument, onClose) }
        }
        MenuPopup.FONT -> {
            val state by repo.editor.collectAsState()
            state?.let { editor ->
                FontDialog(
                    family = editor.fontFamily,
                    size = editor.fontSize,
                    onApply = { family, size ->
                        actions.setFont(family, size)
                        onClose()
                    },
                    onDismiss = onClose,
                )
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
private fun Submenu(label: String, enabled: Boolean = true, onOpen: () -> Unit) {
    DropdownMenuItem(
        text = { Text(label) },
        onClick = onOpen,
        enabled = enabled,
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
