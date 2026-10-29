package io.github.chibicitiberiu.chordnotepad.ui.tools

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
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
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.bridge.CapoChoiceRequest
import io.github.chibicitiberiu.chordnotepad.bridge.DirectiveCheck
import io.github.chibicitiberiu.chordnotepad.bridge.InsertDirectiveRequest
import io.github.chibicitiberiu.chordnotepad.ui.icons.AppIcons

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
 * Tools › Suggest Capo…: which fretboard voicing to optimize for (the
 * request's options, its default chosen). [onAnswer] gets an option's value,
 * or null for Cancel.
 */
@Composable
fun CapoDialog(request: CapoChoiceRequest, onAnswer: (String?) -> Unit) {
    var chosen by rememberSaveable(request.requestId) { mutableStateOf(initialCapoChoice(request)) }
    AlertDialog(
        onDismissRequest = { onAnswer(null) },
        title = { Text(stringResource(R.string.capo_title)) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
                Text(stringResource(R.string.capo_hint), Modifier.padding(bottom = 12.dp))
                Text(stringResource(R.string.capo_voicing), style = MaterialTheme.typography.labelLarge)
                Column(Modifier.selectableGroup()) {
                    for (option in request.options) {
                        RadioRow(option.label, selected = option.value == chosen) { chosen = option.value }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onAnswer(chosen) }, enabled = chosen != null) {
                Text(stringResource(android.R.string.ok))
            }
        },
        dismissButton = {
            TextButton(onClick = { onAnswer(null) }) { Text(stringResource(android.R.string.cancel)) }
        },
    )
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
    AlertDialog(
        onDismissRequest = { onAnswer(null) },
        title = { Text(stringResource(kind.title)) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState())) {
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

/** A one-line text field that has the keyboard up at once; Done submits. */
@Composable
private fun TypedField(label: String, value: String, type: KeyboardType, onDone: () -> Unit, onChange: (String) -> Unit) {
    val focus = remember { FocusRequester() }
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
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

@Composable
private fun RadioRow(label: String, selected: Boolean, onSelect: () -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 48.dp)
            .selectable(selected = selected, role = Role.RadioButton, onClick = onSelect),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = null, modifier = Modifier.padding(end = 12.dp))
        Text(label)
    }
}
