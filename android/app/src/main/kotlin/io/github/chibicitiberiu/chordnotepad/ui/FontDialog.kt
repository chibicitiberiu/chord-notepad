package io.github.chibicitiberiu.chordnotepad.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.ui.editor.EditorFontKind
import io.github.chibicitiberiu.chordnotepad.ui.editor.fontKindFor
import kotlin.math.roundToInt

/** The editor font sizes the desktop's Font dialog offers (`MIN_FONT_SIZE`..`MAX_FONT_SIZE`). */
val FONT_SIZES = 6..72

/**
 * The configured family to send for [kind]. Keeps [current] when it already
 * maps to [kind] (a desktop config's `Consolas` stays as it is); otherwise
 * the desktop default `TkFixedFont` for Monospace, `Sans` or `Serif`. The
 * settings visibility rule: Monospace, Sans or Serif only.
 */
fun configFamilyFor(kind: EditorFontKind, current: String): String = when {
    fontKindFor(current) == kind -> current
    kind == EditorFontKind.MONOSPACE -> "TkFixedFont"
    kind == EditorFontKind.SANS -> "Sans"
    else -> "Serif"
}

/**
 * View › Font…: family (Monospace, Sans, Serif) and size (6-72). OK sends
 * `set_font` through [onApply]; the choices survive a rotation.
 *
 * @param family The configured family (`EditorState.fontFamily`).
 * @param size The current size in points.
 */
@Composable
fun FontDialog(family: String, size: Int, onApply: (family: String, size: Int) -> Unit, onDismiss: () -> Unit) {
    var kind by rememberSaveable { mutableStateOf(fontKindFor(family)) }
    var chosenSize by rememberSaveable { mutableIntStateOf(size.coerceIn(FONT_SIZES)) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.font_title)) },
        text = {
            Column {
                Text(stringResource(R.string.font_family), style = MaterialTheme.typography.labelLarge)
                Column(Modifier.selectableGroup()) {
                    for (k in EditorFontKind.entries) {
                        FamilyChoice(k, selected = k == kind) { kind = k }
                    }
                }
                Text(
                    stringResource(R.string.font_size),
                    style = MaterialTheme.typography.labelLarge,
                    modifier = Modifier.padding(top = 12.dp),
                )
                SizeChooser(chosenSize) { chosenSize = it }
            }
        },
        confirmButton = {
            TextButton(onClick = { onApply(configFamilyFor(kind, family), chosenSize) }) {
                Text(stringResource(android.R.string.ok))
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) }
        },
    )
}

@Composable
private fun FamilyChoice(kind: EditorFontKind, selected: Boolean, onSelect: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .selectable(selected = selected, role = Role.RadioButton, onClick = onSelect),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = null, modifier = Modifier.padding(end = 12.dp))
        Text(
            stringResource(
                when (kind) {
                    EditorFontKind.MONOSPACE -> R.string.font_monospace
                    EditorFontKind.SANS -> R.string.font_sans
                    EditorFontKind.SERIF -> R.string.font_serif
                },
            ),
            fontFamily = kind.family,
        )
    }
}

/** −/+ for single steps, a slider for big jumps. */
@Composable
private fun SizeChooser(size: Int, onChange: (Int) -> Unit) {
    val smaller = stringResource(R.string.menu_font_smaller)
    val bigger = stringResource(R.string.menu_font_bigger)
    Row(verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClick = { onChange((size - 1).coerceIn(FONT_SIZES)) }, enabled = size > FONT_SIZES.first) {
            Text("−", style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { contentDescription = smaller })
        }
        Text(size.toString(), Modifier.width(32.dp), textAlign = TextAlign.Center, style = MaterialTheme.typography.titleMedium)
        IconButton(onClick = { onChange((size + 1).coerceIn(FONT_SIZES)) }, enabled = size < FONT_SIZES.last) {
            Text("+", style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { contentDescription = bigger })
        }
    }
    Slider(
        value = size.toFloat(),
        onValueChange = { onChange(it.roundToInt().coerceIn(FONT_SIZES)) },
        // No steps: 65 tick marks would be noise; the value is rounded instead.
        valueRange = FONT_SIZES.first.toFloat()..FONT_SIZES.last.toFloat(),
    )
}
