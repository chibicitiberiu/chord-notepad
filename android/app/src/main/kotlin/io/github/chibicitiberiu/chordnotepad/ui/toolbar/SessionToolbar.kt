package io.github.chibicitiberiu.chordnotepad.ui.toolbar

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.bridge.ToolbarState
import io.github.chibicitiberiu.chordnotepad.ui.MainActions
import io.github.chibicitiberiu.chordnotepad.ui.icons.AppIcons

// Desktop metronome tints (main_window.py: METRONOME_OFF/ON and the on tint).
private val MetronomeOff = Color(0xFF8C8C8C)
private val MetronomeOn = Color(0xFFD96640)
private val MetronomeOnTint = Color(0xFFFFE4CF)

/**
 * The desktop toolbar minus the transport (which sits in the app bar):
 * notation, speed (BPM × multiplier), key, time signature, metronome. One
 * row that scrolls sideways when it doesn't fit (phones).
 */
@Composable
fun SessionToolbar(state: ToolbarState, actions: MainActions, modifier: Modifier = Modifier) {
    Row(
        modifier
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 8.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        NotationToggle(state.notation, actions::setNotation)
        Separator()
        Muted(stringResource(R.string.toolbar_speed))
        Scrubber(
            text = if (state.bpmEditable) state.bpm.toString() else state.bpmDisplay.toString(),
            value = state.bpm.toDouble(),
            editable = state.bpmEditable,
            onDrag = actions::setBpm,
            onTyped = actions::setBpmText,
            onReset = actions::resetBpm,
            description = stringResource(R.string.toolbar_bpm_description),
        )
        Text(stringResource(R.string.toolbar_bpm_unit), style = MaterialTheme.typography.bodyMedium)
        Muted("×")
        Scrubber(
            text = formatPct(state.multiplierPct),
            value = state.multiplierPct,
            editable = true,
            onDrag = actions::setMultiplierPct,
            onTyped = actions::setMultiplierText,
            onReset = actions::resetMultiplier,
            description = stringResource(R.string.toolbar_speed_description),
        )
        Text("%", style = MaterialTheme.typography.bodyMedium)
        Separator()
        Muted(stringResource(R.string.toolbar_key))
        Choice(state.key, state.keyOptions, actions::setKey, stringResource(R.string.toolbar_key_description))
        Separator()
        Muted(stringResource(R.string.toolbar_time))
        Choice(
            state.beats.toString(), TIME_SIGNATURE_BEATS.map(Int::toString),
            { actions.setTimeSignature(it.toInt(), state.unit) },
            stringResource(R.string.toolbar_beats_description),
        )
        Muted("/")
        Choice(
            state.unit.toString(), TIME_SIGNATURE_UNITS.map(Int::toString),
            { actions.setTimeSignature(state.beats, it.toInt()) },
            stringResource(R.string.toolbar_unit_description),
        )
        Separator()
        MetronomeToggle(state.metronome, actions::toggleMetronome)
    }
}

@Composable
private fun Muted(text: String) {
    Text(text, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun Separator() {
    VerticalDivider(Modifier.height(24.dp).padding(horizontal = 4.dp))
}

/** AB / Do: which notation chords are detected in. */
@Composable
private fun NotationToggle(notation: String, onSelect: (String) -> Unit) {
    val options = listOf(
        "american" to stringResource(R.string.notation_american),
        "european" to stringResource(R.string.notation_european),
    )
    SingleChoiceSegmentedButtonRow(Modifier.height(36.dp)) {
        options.forEachIndexed { i, (value, label) ->
            SegmentedButton(
                selected = notation == value,
                onClick = { if (notation != value) onSelect(value) },
                shape = SegmentedButtonDefaults.itemShape(i, options.size),
                icon = {},
                label = { Text(label) },
            )
        }
    }
}

/** A value picked from a short list (key, beats, unit). */
@Composable
private fun Choice(current: String, options: List<String>, onPick: (String) -> Unit, description: String) {
    var open by remember { mutableStateOf(false) }
    Box {
        TextButton(
            onClick = { open = true },
            modifier = Modifier.height(36.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(start = 8.dp, end = 2.dp),
        ) {
            Text(current)
            Icon(AppIcons.ArrowDropDown, contentDescription = description, Modifier.size(20.dp))
        }
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            for (option in options) {
                DropdownMenuItem(
                    text = { Text(option) },
                    onClick = {
                        open = false
                        if (option != current) onPick(option)
                    },
                )
            }
        }
    }
}

/** The click track toggle, tinted while on. */
@Composable
private fun MetronomeToggle(on: Boolean, onToggle: () -> Unit) {
    IconButton(
        onClick = onToggle,
        modifier = Modifier.background(if (on) MetronomeOnTint else Color.Transparent, CircleShape),
        colors = IconButtonDefaults.iconButtonColors(contentColor = if (on) MetronomeOn else MetronomeOff),
    ) {
        Icon(
            AppIcons.Metronome,
            contentDescription = stringResource(if (on) R.string.metronome_on else R.string.metronome_off),
        )
    }
    Spacer(Modifier.width(2.dp))
}
