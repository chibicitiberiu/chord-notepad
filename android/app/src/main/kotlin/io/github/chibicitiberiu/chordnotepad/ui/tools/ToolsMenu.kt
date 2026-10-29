package io.github.chibicitiberiu.chordnotepad.ui.tools

import androidx.compose.material3.HorizontalDivider
import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.bridge.SessionRepository
import io.github.chibicitiberiu.chordnotepad.ui.identifier.ChordIdentifierDialog

/** What ⋮ › Tools opened outside the menu. */
enum class ToolPopup {
    NONE,

    /** Transpose…, with text selected when it opened. */
    TRANSPOSE_SELECTION,

    /** Transpose…, nothing selected: the whole song. */
    TRANSPOSE_SONG,

    /** Identify Chord…. */
    IDENTIFIER,
}

/**
 * The ⋮ › Tools page, in the desktop's order (help/interface.rst: Identify
 * Chord, Insert, Transpose, Suggest Capo, Convert notation). The desktop's
 * Tools › Settings… is ⋮ › Settings on Android (its own root entry).
 *
 * @param row Draws one menu row: label, click, whether it opens a submenu.
 * @param run Closes the menu, then runs the action.
 */
@Composable
fun ToolsPageItems(
    tools: ToolActions,
    row: @Composable (label: String, submenu: Boolean, onClick: () -> Unit) -> Unit,
    run: (() -> Unit) -> () -> Unit,
    openInsert: () -> Unit,
    openConvert: () -> Unit,
    show: (ToolPopup) -> Unit,
) {
    row(stringResource(R.string.menu_identify_chord), false) { show(ToolPopup.IDENTIFIER) }
    row(stringResource(R.string.menu_insert), true, openInsert)
    HorizontalDivider()
    row(stringResource(R.string.menu_transpose), false) {
        show(if (tools.selection() != null) ToolPopup.TRANSPOSE_SELECTION else ToolPopup.TRANSPOSE_SONG)
    }
    row(stringResource(R.string.menu_suggest_capo), false, run(tools::suggestCapo))
    HorizontalDivider()
    row(stringResource(R.string.menu_convert), true, openConvert)
}

/** ⋮ › Tools › Insert: one directive dialog each (the session asks with an `InsertDirectiveRequest`). */
@Composable
fun InsertPageItems(
    tools: ToolActions,
    row: @Composable (label: String, submenu: Boolean, onClick: () -> Unit) -> Unit,
    run: (() -> Unit) -> () -> Unit,
) {
    for ((kind, label) in INSERT_ITEMS) {
        row(stringResource(label), false, run { tools.insertDirective(kind) })
    }
}

/** ⋮ › Tools › Convert notation: rewrite every chord in American or European notation. */
@Composable
fun ConvertPageItems(
    tools: ToolActions,
    row: @Composable (label: String, submenu: Boolean, onClick: () -> Unit) -> Unit,
    run: (() -> Unit) -> () -> Unit,
) {
    row(stringResource(R.string.menu_convert_american), false, run { tools.convertNotation("american") })
    row(stringResource(R.string.menu_convert_european), false, run { tools.convertNotation("european") })
}

/** The Transpose dialog or the chord identifier, as [popup] says; [onClose] when done. */
@Composable
fun ToolPopups(popup: ToolPopup, tools: ToolActions, repo: SessionRepository, compact: Boolean, onClose: () -> Unit) {
    when (popup) {
        ToolPopup.NONE -> Unit
        ToolPopup.TRANSPOSE_SELECTION, ToolPopup.TRANSPOSE_SONG -> TransposeDialog(
            hasSelection = popup == ToolPopup.TRANSPOSE_SELECTION,
            onApply = { semitones ->
                onClose()
                // The selection is the editor's, kept app-wide, so it's the
                // one the dialog opened with (also after a rotation).
                tools.transpose(semitones, tools.selection())
            },
            onDismiss = onClose,
        )
        ToolPopup.IDENTIFIER -> ChordIdentifierDialog(
            repo = repo,
            commands = tools.screen,
            insertAtCursor = tools::insertChord,
            compact = compact,
            onClose = onClose,
        )
    }
}

/** Insert's items: the kinds and their labels, as on the desktop. */
val INSERT_ITEMS: List<Pair<DirectiveKind, Int>> = listOf(
    DirectiveKind.BPM to R.string.menu_insert_bpm,
    DirectiveKind.TIME to R.string.menu_insert_time,
    DirectiveKind.KEY to R.string.menu_insert_key,
    DirectiveKind.LABEL to R.string.menu_insert_label,
    DirectiveKind.LOOP to R.string.menu_insert_loop,
)
