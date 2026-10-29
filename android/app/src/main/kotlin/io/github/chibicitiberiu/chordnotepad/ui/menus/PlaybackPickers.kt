package io.github.chibicitiberiu.chordnotepad.ui.menus

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.ui.icons.AppIcons

// Playback › Voicing and Playback › Instrument. Phones get bottom sheets
// (long lists, big touch targets); wider screens get pages of the overflow
// dropdown, like the desktop's cascading menus.

// -- bottom sheets (phones) ---------------------------------------------------

/** Playback › Voicing as a bottom sheet; choosing a voicing closes it. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VoicingSheet(rows: List<VoicingRow>, onChoose: (String) -> Unit, onDismiss: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        SheetTitle(stringResource(R.string.menu_voicing))
        LazyColumn {
            items(rows) { row ->
                when (row) {
                    VoicingRow.Divider -> HorizontalDivider(Modifier.padding(vertical = 4.dp))
                    is VoicingRow.Choice -> RadioRow(row.label, row.selected) {
                        onChoose(row.value)
                        onDismiss()
                    }
                }
            }
        }
    }
}

/**
 * Playback › Instrument as a bottom sheet: the 16 families, the current one
 * marked; one family at a time is open (the current one at first) and shows
 * its programs. Choosing a program closes the sheet.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InstrumentSheet(families: List<FamilyRow>, onChoose: (Int) -> Unit, onDismiss: () -> Unit) {
    var open by rememberSaveable { mutableIntStateOf(initialFamilyIndex(families)) }
    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)) {
        SheetTitle(stringResource(R.string.menu_instrument))
        LazyColumn {
            families.forEachIndexed { index, family ->
                familyItems(family, expanded = index == open, onToggle = { open = if (open == index) -1 else index }) {
                    onChoose(it)
                    onDismiss()
                }
            }
        }
    }
}

private fun LazyListScope.familyItems(
    family: FamilyRow,
    expanded: Boolean,
    onToggle: () -> Unit,
    onChoose: (Int) -> Unit,
) {
    item(key = "family:${family.name}") {
        Row(
            Modifier
                .fillMaxWidth()
                .heightIn(min = 48.dp)
                .clickable(onClickLabel = family.name, onClick = onToggle)
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            CurrentMarker(family.isCurrent)
            Spacer(Modifier.width(16.dp))
            Text(family.name, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
            Icon(if (expanded) AppIcons.ExpandLess else AppIcons.ExpandMore, contentDescription = null)
        }
    }
    if (expanded) {
        items(family.programs, key = { "program:${it.program}" }) { program ->
            RadioRow(program.label, program.selected, indent = 24.dp) { onChoose(program.program) }
        }
    }
}

@Composable
private fun SheetTitle(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.titleMedium,
        modifier = Modifier.padding(start = 24.dp, end = 24.dp, bottom = 8.dp),
    )
}

@Composable
private fun RadioRow(label: String, selected: Boolean, indent: Dp = 0.dp, onClick: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .selectable(selected = selected, role = Role.RadioButton, onClick = onClick)
            .padding(start = 8.dp + indent, end = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = null, modifier = Modifier.padding(horizontal = 12.dp))
        Text(label, style = MaterialTheme.typography.bodyLarge)
    }
}

/** The desktop's current-family dot, or a blank of the same size. */
@Composable
fun CurrentMarker(current: Boolean) {
    Box(Modifier.size(24.dp), contentAlignment = Alignment.Center) {
        if (current) Box(Modifier.size(8.dp).background(MaterialTheme.colorScheme.onSurface, CircleShape))
    }
}

// -- dropdown pages (tablets) ---------------------------------------------------

/** The Voicing page's items: radio entries with dividers between the groups. */
@Composable
fun VoicingMenuItems(rows: List<VoicingRow>, onChoose: (String) -> Unit) {
    for (row in rows) {
        when (row) {
            VoicingRow.Divider -> HorizontalDivider()
            is VoicingRow.Choice -> RadioMenuItem(row.label, row.selected) { onChoose(row.value) }
        }
    }
}

/** The Instrument page's items: one entry per family, marked if current, opening its page. */
@Composable
fun FamilyMenuItems(families: List<FamilyRow>, onOpen: (Int) -> Unit) {
    families.forEachIndexed { index, family ->
        DropdownMenuItem(
            text = { Text(family.name) },
            onClick = { onOpen(index) },
            leadingIcon = { CurrentMarker(family.isCurrent) },
            trailingIcon = { Icon(AppIcons.ChevronRight, contentDescription = null) },
        )
    }
}

/** A family page's items: its programs as radio entries. */
@Composable
fun ProgramMenuItems(family: FamilyRow, onChoose: (Int) -> Unit) {
    for (program in family.programs) {
        RadioMenuItem(program.label, program.selected) { onChoose(program.program) }
    }
}

@Composable
private fun RadioMenuItem(label: String, selected: Boolean, onClick: () -> Unit) {
    DropdownMenuItem(
        text = { Text(label) },
        onClick = onClick,
        leadingIcon = { RadioButton(selected = selected, onClick = null) },
        modifier = Modifier.semantics { this.selected = selected },
    )
}
