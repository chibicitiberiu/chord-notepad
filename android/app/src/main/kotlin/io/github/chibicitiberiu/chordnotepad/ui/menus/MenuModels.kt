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

/** The Voicing sheet's group headings. */
enum class VoicingGroupKind { PIANO, FRETTED, ENSEMBLES, YOURS }

/** One heading of the Voicing sheet and its radio rows. */
data class VoicingGroup(val kind: VoicingGroupKind, val choices: List<VoicingRow.Choice>)

/**
 * The Voicing sheet: Piano, Fretted, Ensembles and Your voicings, each with
 * its choices. The heading comes from the values (`piano`, `guitar:…`,
 * `ensemble:…`, `voicing:…`), so a group the session leaves out (no user
 * voicings) doesn't shift the others; anything unknown joins Your voicings.
 */
fun voicingGroups(state: VoicingMenuState): List<VoicingGroup> {
    val byKind = linkedMapOf<VoicingGroupKind, MutableList<VoicingRow.Choice>>()
    for (item in state.groups.flatten()) {
        val kind = when {
            item.value == "piano" -> VoicingGroupKind.PIANO
            item.value.startsWith("guitar:") -> VoicingGroupKind.FRETTED
            item.value.startsWith("ensemble:") -> VoicingGroupKind.ENSEMBLES
            else -> VoicingGroupKind.YOURS
        }
        byKind.getOrPut(kind) { mutableListOf() } += VoicingRow.Choice(item.label, item.value, item.value == state.selected)
    }
    return VoicingGroupKind.entries.mapNotNull { k -> byKind[k]?.let { VoicingGroup(k, it) } }
}

/** The label of the voicing in use, or null. */
fun selectedVoicingLabel(state: VoicingMenuState?): String? =
    state?.groups?.flatten()?.firstOrNull { it.value == state.selected }?.label

/**
 * A program's label split for the instrument sheet: `"24 - Nylon Guitar"` →
 * (`"Nylon Guitar"`, `"24"`), the number as the desktop menu shows it. A
 * label without the number keeps [ProgramRow.program].
 */
fun programParts(row: ProgramRow): Pair<String, String> {
    val m = Regex("""^\s*(\d+)\s*-\s*(.+)$""").find(row.label)
    return if (m != null) m.groupValues[2].trim() to m.groupValues[1] else row.label to row.program.toString()
}

/** The name of the instrument in use (`"Steel Guitar"`), or null. */
fun currentProgramName(families: List<FamilyRow>): String? =
    families.flatMap { it.programs }.firstOrNull { it.selected }?.let { programParts(it).first }
