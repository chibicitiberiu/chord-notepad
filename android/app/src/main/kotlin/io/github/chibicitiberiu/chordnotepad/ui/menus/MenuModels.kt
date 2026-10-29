package io.github.chibicitiberiu.chordnotepad.ui.menus

import io.github.chibicitiberiu.chordnotepad.bridge.DocumentRef
import io.github.chibicitiberiu.chordnotepad.bridge.InstrumentMenuState
import io.github.chibicitiberiu.chordnotepad.bridge.RecentDocumentsState
import io.github.chibicitiberiu.chordnotepad.bridge.VoicingMenuState

// What the Playback and Recent Files menus list, from the session's states.
// The menus (dropdown pages or bottom sheets) only draw these rows.

/** One row of Playback › Voicing. */
sealed interface VoicingRow {
    /** A voicing; choosing it sends `set_voicing` with [value]. */
    data class Choice(val label: String, val value: String, val selected: Boolean) : VoicingRow

    /** The separator between two groups (piano, fretboards, ensembles, user voicings). */
    data object Divider : VoicingRow
}

/** The Voicing menu's rows: the groups in order, a divider between two, the selected one marked. */
fun voicingRows(state: VoicingMenuState): List<VoicingRow> = buildList {
    state.groups.filter { it.isNotEmpty() }.forEachIndexed { index, group ->
        if (index > 0) add(VoicingRow.Divider)
        group.forEach { add(VoicingRow.Choice(it.label, it.value, it.value == state.selected)) }
    }
}

/** One General MIDI program in an instrument family; choosing it sends `set_instrument`. */
data class ProgramRow(val label: String, val program: Int, val selected: Boolean)

/** One family of Playback › Instrument, marked when it holds the instrument in use. */
data class FamilyRow(val name: String, val isCurrent: Boolean, val programs: List<ProgramRow>)

/**
 * The Instrument menu: the 16 families, each with its programs. Labels lose
 * the desktop's column padding (`" 24 - Nylon Guitar"`); an item whose value
 * isn't a program number is skipped.
 */
fun instrumentFamilies(state: InstrumentMenuState): List<FamilyRow> = state.families.map { family ->
    FamilyRow(
        name = family.name,
        isCurrent = family.isCurrent,
        programs = family.items.mapNotNull { item ->
            item.value.trim().toIntOrNull()?.let { ProgramRow(item.label.trim(), it, it == state.current) }
        },
    )
}

/** The family to show first in the instrument picker: the current one, else the first. */
fun initialFamilyIndex(families: List<FamilyRow>): Int = families.indexOfFirst { it.isCurrent }.coerceAtLeast(0)

/**
 * File › Recent Files: the documents, newest first (the session already
 * capped the list at `max_recent_files`); empty shows "(No recent files)".
 */
fun recentEntries(state: RecentDocumentsState?): List<DocumentRef> = state?.items.orEmpty()
