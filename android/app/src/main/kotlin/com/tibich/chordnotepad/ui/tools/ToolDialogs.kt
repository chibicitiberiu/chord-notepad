package com.tibich.chordnotepad.ui.tools

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AlertDialogDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.bridge.CapoAdviceState
import com.tibich.chordnotepad.bridge.CapoRow
import com.tibich.chordnotepad.bridge.DirectiveCheck
import com.tibich.chordnotepad.bridge.InsertDirectiveRequest
import com.tibich.chordnotepad.ui.KeyboardSafeAlertDialog
import com.tibich.chordnotepad.ui.moreBelowFade
import com.tibich.chordnotepad.ui.icons.AppIcons

/**
 * Tools › Transpose…: −11..+11 semitones for the selection or, with none,
 * the whole song (the desktop's dialog). [onApply] gets the semitones.
 *
 * @param hasSelection Whether the editor had a selection when it opened.
 */
@Composable
fun TransposeDialog(hasSelection: Boolean, onApply: (semitones: Int) -> Unit, onDismiss: () -> Unit) {
    var semitones by rememberSaveable { mutableIntStateOf(0) }
    val form = TransposeForm(semitones)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.transpose_title)) },
        text = {
            Column {
                Text(stringResource(if (hasSelection) R.string.transpose_selection else R.string.transpose_whole_song))
                Text(stringResource(R.string.transpose_hint), Modifier.padding(top = 8.dp, bottom = 12.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(stringResource(R.string.transpose_semitones), Modifier.weight(1f))
                    Stepper(
                        value = if (semitones > 0) "+$semitones" else semitones.toString(),
                        onDown = { semitones = form.down().semitones },
                        onUp = { semitones = form.up().semitones },
                        canDown = semitones > TransposeForm.RANGE.first,
                        canUp = semitones < TransposeForm.RANGE.last,
                        downLabel = stringResource(R.string.transpose_down),
                        upLabel = stringResource(R.string.transpose_up),
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onApply(semitones) }) { Text(stringResource(android.R.string.ok)) }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) }
        },
    )
}

/**
 * Suggest Capo (Insert › Capo › Suggest): the session's [CapoAdviceState].
 * The voicing at the top ([onVoicing] scores again for another), a spinner
 * while the capos are scored, then the ranked rows, the recommended one
 * first and chosen. Apply sends the chosen row's capo ([onApply]); it waits
 * while a song plays, with a hint, since the session refuses the edit then.
 * Cancel or dismiss is [onCancel].
 */
@Composable
fun CapoDialog(
    state: CapoAdviceState,
    onVoicing: (String) -> Unit,
    onApply: (Int) -> Unit,
    onCancel: () -> Unit,
) {
    var picked by rememberSaveable(state.voicing, state.rows) { mutableStateOf(capoChoice(state, null)) }
    val chosen = capoChoice(state, picked)
    val scroll = rememberScrollState()
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text(stringResource(R.string.capo_title)) },
        text = {
            // A fade while the rows go on below the edge (L9).
            Column(Modifier.moreBelowFade(scroll, AlertDialogDefaults.containerColor).verticalScroll(scroll)) {
                Text(stringResource(R.string.capo_hint), Modifier.padding(bottom = 12.dp))
                if (state.scope.isNotEmpty()) {
                    Text(state.scope, Modifier.padding(bottom = 12.dp), fontWeight = FontWeight.Bold)
                }
                Picker(
                    label = stringResource(R.string.capo_voicing),
                    value = state.voicings.firstOrNull { it.value == state.voicing }?.label ?: state.voicing,
                    options = state.voicings.map { it.label },
                ) { label -> state.voicings.firstOrNull { it.label == label }?.let { onVoicing(it.value) } }
                Spacer(Modifier.height(12.dp))
                if (state.computing) {
                    Row(Modifier.padding(vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(24.dp), strokeWidth = 3.dp)
                        Text(stringResource(R.string.capo_finding), Modifier.padding(start = 12.dp))
                    }
                }
                Column(Modifier.selectableGroup()) {
                    for (row in state.rows) {
                        CapoRadioRow(row, selected = row.capo == chosen) { picked = row.capo }
                    }
                }
                if (state.message.isNotEmpty()) {
                    Text(
                        state.message,
                        Modifier.padding(top = 8.dp),
                        color = if (state.status == CapoAdviceState.ERROR) {
                            MaterialTheme.colorScheme.error
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    )
                }
                if (state.playing) {
                    Text(
                        stringResource(R.string.capo_stop_to_apply),
                        Modifier.padding(top = 8.dp),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { chosen?.let(onApply) }, enabled = capoCanApply(state, picked)) {
                Text(stringResource(R.string.capo_apply))
            }
        },
        dismissButton = {
            TextButton(onClick = onCancel) { Text(stringResource(android.R.string.cancel)) }
        },
    )
}

/**
 * One capo position: a radio, the capo as the headline with its ease at the
 * right, the shapes as the main line below, then the Recommended / Current tags.
 */
@Composable
private fun CapoRadioRow(row: CapoRow, selected: Boolean, onSelect: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 56.dp)
            .selectable(selected = selected, role = Role.RadioButton, onClick = onSelect)
            .padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = null, modifier = Modifier.padding(end = 12.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    if (row.capo > 0) stringResource(R.string.capo_row_capo, row.capo) else stringResource(R.string.capo_row_none),
                    Modifier.weight(1f),
                    style = MaterialTheme.typography.titleSmall,
                )
                // "No capo" is the headline already; it has nothing to compare with.
                if (row.capo > 0) {
                    Text(
                        row.ease,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Text(
                row.shapes,
                Modifier.padding(top = 2.dp),
                style = MaterialTheme.typography.bodyLarge,
            )
            val tags = listOfNotNull(
                stringResource(R.string.capo_recommended).takeIf { row.recommended },
                stringResource(R.string.capo_current).takeIf { row.current },
            )
            if (tags.isNotEmpty()) {
                Text(
                    tags.joinToString(" · "),
                    Modifier.padding(top = 2.dp),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}

/**
 * Tools › Insert ▸ …: the fields of one directive, as the desktop's dialogs
 * have them. Python checks the fields as they change ([onCheck], reply
 * [check]; rules aren't repeated here): what's wrong shows under the fields
 * and Insert stays disabled, so the dialog stays open until the values are
 * valid. Insert answers with [DirectiveForm.answer]. Cancel or dismiss
 * answers null.
 *
 * @param keys The key choices of the request's notation ([keyChoices]).
 * @param units The beat units the time signature offers (`SettingsState`).
 */
@Composable
fun InsertDirectiveDialog(
    request: InsertDirectiveRequest,
    keys: List<String>,
    units: List<Int>,
    check: DirectiveCheck?,
    onCheck: (Map<String, String>) -> Unit,
    onSuggestCapo: () -> Unit = {},
    onAnswer: (Map<String, String>?) -> Unit,
) {
    val kind = DirectiveKind.of(request.kind)
    if (kind == null) {
        LaunchedEffect(request.requestId) { onAnswer(null) }
        return
    }
    var saved by rememberSaveable(request.requestId) { mutableStateOf(DirectiveForm.initial(kind, keys).save()) }
    val form = DirectiveForm.restore(saved) ?: DirectiveForm.initial(kind, keys)
    fun update(f: DirectiveForm) {
        saved = f.save()
    }
    val answer = form.answer()
    // Python checks the fields as they change; Insert waits for a clean reply.
    LaunchedEffect(request.requestId, answer) { onCheck(answer) }
    val changed = form != DirectiveForm.initial(kind, keys)
    val verdict = DirectiveVerdict.of(request.kind, request.requestId, answer, check, showErrors = changed)
    val submit = { if (verdict.canInsert) onAnswer(answer) }
    KeyboardSafeAlertDialog(
        onDismissRequest = { onAnswer(null) },
        title = { Text(stringResource(kind.title)) },
        text = {
            Column {
                Text(stringResource(kind.hint), Modifier.padding(bottom = 12.dp))
                DirectiveFields(form, request, keys, units, ::update, submit)
                for (message in verdict.messages) {
                    Text(
                        message,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(top = 8.dp),
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = submit, enabled = verdict.canInsert) { Text(stringResource(R.string.insert_button)) }
        },
        dismissButton = {
            Row {
                if (kind == DirectiveKind.CAPO) {
                    // Suggest: drop this request and let Suggest Capo pick (and insert) the fret.
                    TextButton(onClick = {
                        onAnswer(null)
                        onSuggestCapo()
                    }) { Text(stringResource(R.string.insert_capo_suggest)) }
                }
                TextButton(onClick = { onAnswer(null) }) { Text(stringResource(android.R.string.cancel)) }
            }
        },
    )
}

private val DirectiveKind.title: Int
    get() = when (this) {
        DirectiveKind.BPM -> R.string.insert_bpm_title
        DirectiveKind.TIME -> R.string.insert_time_title
        DirectiveKind.KEY -> R.string.insert_key_title
        DirectiveKind.LABEL -> R.string.insert_label_title
        DirectiveKind.LOOP -> R.string.insert_loop_title
        DirectiveKind.CAPO -> R.string.insert_capo_title
    }

private val DirectiveKind.hint: Int
    get() = when (this) {
        DirectiveKind.BPM -> R.string.insert_bpm_hint
        DirectiveKind.TIME -> R.string.insert_time_hint
        DirectiveKind.KEY -> R.string.insert_key_hint
        DirectiveKind.LABEL -> R.string.insert_label_hint
        DirectiveKind.LOOP -> R.string.insert_loop_hint
        DirectiveKind.CAPO -> R.string.insert_capo_hint
    }

@Composable
private fun DirectiveFields(
    form: DirectiveForm,
    request: InsertDirectiveRequest,
    keys: List<String>,
    units: List<Int>,
    onChange: (DirectiveForm) -> Unit,
    onSubmit: () -> Unit,
) {
    when (form.kind) {
        DirectiveKind.BPM -> TypedField(stringResource(R.string.insert_bpm_field), form.bpm, KeyboardType.Ascii, onSubmit) {
            onChange(form.copy(bpm = it))
        }
        DirectiveKind.TIME -> Row(verticalAlignment = Alignment.CenterVertically) {
            Picker(stringResource(R.string.insert_time_beats), form.beats.toString(), DirectiveForm.BEATS_RANGE.map { "$it" }) {
                onChange(form.copy(beats = it.toInt()))
            }
            Text("/", style = MaterialTheme.typography.titleLarge, modifier = Modifier.padding(horizontal = 12.dp))
            Picker(stringResource(R.string.insert_time_unit), form.unit.toString(), units.map { "$it" }) {
                onChange(form.copy(unit = it.toInt()))
            }
        }
        DirectiveKind.KEY -> Picker(stringResource(R.string.insert_key_field), form.key, keys) {
            onChange(form.copy(key = it))
        }
        DirectiveKind.LABEL -> TypedField(stringResource(R.string.insert_label_field), form.label, KeyboardType.Ascii, onSubmit) {
            onChange(form.copy(label = it))
        }
        DirectiveKind.CAPO -> TypedField(stringResource(R.string.insert_capo_field), form.capo, KeyboardType.Number, onSubmit) {
            onChange(form.copy(capo = it))
        }
        DirectiveKind.LOOP -> Column {
            Picker(stringResource(R.string.insert_loop_label), form.loopLabel, loopChoices(request)) {
                onChange(form.copy(loopLabel = it))
            }
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
                Text(stringResource(R.string.insert_loop_count), Modifier.weight(1f))
                Stepper(
                    value = form.count.toString(),
                    onDown = { onChange(form.fewerRepeats()) },
                    onUp = { onChange(form.moreRepeats()) },
                    canDown = form.count > DirectiveForm.COUNT_RANGE.first,
                    canUp = form.count < DirectiveForm.COUNT_RANGE.last,
                    downLabel = stringResource(R.string.insert_loop_fewer),
                    upLabel = stringResource(R.string.insert_loop_more),
                )
            }
        }
    }
}

/**
 * A one-line text field that has the keyboard up at once; Done submits. The
 * cursor and selection are saved with the text, so a rotation leaves the
 * cursor where it was, not at the start (L6).
 */
@Composable
private fun TypedField(label: String, value: String, type: KeyboardType, onDone: () -> Unit, onChange: (String) -> Unit) {
    val focus = remember { FocusRequester() }
    var field by rememberSaveable(stateSaver = TextFieldValue.Saver) { mutableStateOf(fieldValueFor(null, value)) }
    val shown = fieldValueFor(field, value)
    OutlinedTextField(
        value = shown,
        onValueChange = {
            field = it
            if (it.text != value) onChange(it.text)
        },
        label = { Text(label) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = type, imeAction = ImeAction.Done, autoCorrectEnabled = false),
        keyboardActions = KeyboardActions(onDone = { onDone() }),
        modifier = Modifier.fillMaxWidth().focusRequester(focus),
    )
    LaunchedEffect(Unit) { focus.requestFocus() }
}

/** A labelled dropdown over [options] (the desktop's read-only comboboxes and spinboxes). */
@Composable
private fun Picker(label: String, value: String, options: List<String>, onPick: (String) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Column {
        Text(label, style = MaterialTheme.typography.labelLarge)
        Box {
            OutlinedButton(onClick = { open = true }, enabled = options.isNotEmpty()) {
                Text(value, Modifier.heightIn(min = 20.dp))
                Icon(AppIcons.ArrowDropDown, contentDescription = null)
            }
            DropdownMenu(expanded = open, onDismissRequest = { open = false }, modifier = Modifier.heightIn(max = 320.dp)) {
                for (option in options) {
                    DropdownMenuItem(
                        text = { Text(option) },
                        onClick = {
                            open = false
                            onPick(option)
                        },
                    )
                }
            }
        }
    }
}

/** −/+ around a value. */
@Composable
private fun Stepper(
    value: String,
    onDown: () -> Unit,
    onUp: () -> Unit,
    canDown: Boolean,
    canUp: Boolean,
    downLabel: String,
    upLabel: String,
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClick = onDown, enabled = canDown) {
            Text("−", style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { contentDescription = downLabel })
        }
        Text(value, Modifier.width(40.dp), textAlign = TextAlign.Center, style = MaterialTheme.typography.titleMedium)
        IconButton(onClick = onUp, enabled = canUp) {
            Text("+", style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { contentDescription = upLabel })
        }
    }
}
