package io.github.chibicitiberiu.chordnotepad.ui.sheets

import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLinkStyles
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.withLink
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.ui.icons.IconTints
import io.github.chibicitiberiu.chordnotepad.ui.icons.MdiIcon
import io.github.chibicitiberiu.chordnotepad.ui.theme.appColors

/** One value a song starts with: as written in a directive (`90`, `3/4`, `G`), and where it comes from. */
data class SongDefaultValue(val value: String, val fromDirective: Boolean, val directiveOffset: Int? = null)

/**
 * What the Song defaults sheet and the player's pill show. [lockedReason]:
 * while a song plays or is paused, why the tempo and Write into song are off.
 */
data class SongDefaults(
    val tempo: SongDefaultValue,
    val time: SongDefaultValue,
    val key: SongDefaultValue,
    val summary: String,
    val lockedReason: String? = null,
) {
    /** Whether "Write into song" has anything to write (a value no directive sets). */
    val anythingToWrite: Boolean get() = !tempo.fromDirective || !time.fromDirective || (!key.fromDirective && key.value.isNotEmpty())

    /** Whether "Write into song" can be pressed now. */
    val canWrite: Boolean get() = lockedReason == null && anythingToWrite

    companion object {
        /** The pill's text: the values joined by " · ", an empty key left out. */
        fun summaryOf(tempo: String, time: String, key: String): String =
            listOf(tempo, time, key).filter { it.isNotEmpty() }.joinToString(" · ")
    }
}

/** The three rows of the sheet. */
enum class SongDefaultKind(val directive: String) { TEMPO("bpm"), TIME("time"), KEY("key") }

/** The directive that sets [value] for [kind]: `{bpm: 90}`, `{time: 3/4}`, `{key: G}`. */
fun directiveCode(kind: SongDefaultKind, value: String): String = "{${kind.directive}: $value}"

/** What the Song defaults sheet does. */
interface SongDefaultsActions {
    /** A typed tempo default (`set_bpm_text`). */
    fun setTempoText(text: String)

    /** A time signature default. */
    fun setTime(beats: Int, unit: Int)

    /** A key default. */
    fun setKey(key: String)

    /** Edit: switch to Edit mode with the cursor at the directive ([offset], code points). */
    fun editDirective(offset: Int)

    /** Write the values no directive sets into the top of the song. */
    fun writeIntoSong()
}

/** The time signatures the default offers (the common ones; any other is a directive). */
val TIME_CHOICES: List<Pair<Int, Int>> = listOf(2 to 4, 3 to 4, 4 to 4, 5 to 4, 6 to 4, 7 to 4, 2 to 2, 3 to 8, 6 to 8, 7 to 8, 9 to 8, 12 to 8)

/**
 * Song defaults (the player's song pill): Tempo, Time signature and Key.
 * A value set by a directive is read-only with "Set by `{bpm: 90}` in the
 * song · Edit"; the others are editable defaults (not saved with the file).
 * **Write into song** inserts the missing directives at the top. While a
 * song plays or is paused the tempo and Write into song are off and the
 * sheet says why ([SongDefaults.lockedReason]).
 */
@Composable
fun SongDefaultsSheet(defaults: SongDefaults, keys: List<String>, actions: SongDefaultsActions, onDismiss: () -> Unit) {
    var tempoDialog by remember { mutableStateOf(false) }
    PickerSheet(
        title = stringResource(R.string.song_defaults_title),
        subtitle = stringResource(R.string.song_defaults_subtitle),
        onDismiss = onDismiss,
        actions = {
            SheetTextButton(stringResource(R.string.song_defaults_write), { actions.writeIntoSong(); onDismiss() }, enabled = defaults.canWrite)
            ActionsSpacer()
            SheetDoneButton(stringResource(R.string.sheet_done), onDismiss)
        },
    ) {
        defaults.lockedReason?.let { reason ->
            Text(
                reason,
                Modifier.fillMaxWidth().padding(bottom = 4.dp),
                fontSize = 12.sp,
                lineHeight = 16.sp,
                color = appColors.muted,
            )
        }
        DefaultRow(
            SongDefaultKind.TEMPO, R.drawable.mdi_metronome, IconTints.Tempo, stringResource(R.string.insert_tempo),
            defaults.tempo, display = stringResource(R.string.song_defaults_bpm, defaults.tempo.value),
            onEdit = actions::editDirective,
            enabled = defaults.lockedReason == null,
        ) { tempoDialog = true }
        DefaultRow(
            SongDefaultKind.TIME, R.drawable.ic_time_signature, IconTints.Time, stringResource(R.string.insert_time),
            defaults.time, display = defaults.time.value, onEdit = actions::editDirective,
            choices = TIME_CHOICES.map { "${it.first}/${it.second}" },
            onChoose = { v -> v.split('/').let { actions.setTime(it[0].toInt(), it[1].toInt()) } },
        )
        DefaultRow(
            SongDefaultKind.KEY, R.drawable.mdi_music_clef_treble, IconTints.Key, stringResource(R.string.insert_key),
            defaults.key, display = defaults.key.value.ifEmpty { stringResource(R.string.song_defaults_no_key) },
            onEdit = actions::editDirective,
            choices = keys,
            onChoose = actions::setKey,
        )
    }
    if (tempoDialog && defaults.lockedReason == null) {
        TempoDialog(defaults.tempo.value, onApply = { actions.setTempoText(it); tempoDialog = false }, onDismiss = { tempoDialog = false })
    }
}

@Composable
private fun DefaultRow(
    kind: SongDefaultKind,
    icon: Int,
    tint: androidx.compose.ui.graphics.Color,
    label: String,
    value: SongDefaultValue,
    display: String,
    onEdit: (Int) -> Unit,
    choices: List<String> = emptyList(),
    onChoose: (String) -> Unit = {},
    enabled: Boolean = true,
    onOpen: (() -> Unit)? = null,
) {
    val colors = appColors
    var open by remember { mutableStateOf(false) }
    Column {
        Row(
            Modifier.fillMaxWidth().height(46.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            MdiIcon(icon, tint)
            Text(label, Modifier.weight(1f), fontSize = 14.sp, color = colors.text)
            if (value.fromDirective) {
                Text(display, fontSize = 14.sp, fontWeight = FontWeight.Medium, color = colors.muted)
            } else {
                Box {
                    val shape = RoundedCornerShape(8.dp)
                    Text(
                        "$display ▾",
                        Modifier
                            .clip(shape)
                            .border(1.dp, colors.line, shape)
                            .clickable(enabled = enabled, role = Role.Button) { if (onOpen != null) onOpen() else open = true }
                            .padding(horizontal = 10.dp, vertical = 5.dp),
                        fontSize = 14.sp,
                        fontWeight = FontWeight.Medium,
                        color = if (enabled) colors.text else colors.muted,
                    )
                    DropdownMenu(expanded = open, onDismissRequest = { open = false }, modifier = Modifier.heightIn(max = 320.dp)) {
                        for (choice in choices) {
                            DropdownMenuItem(text = { Text(choice) }, onClick = {
                                open = false
                                if (choice != value.value) onChoose(choice)
                            })
                        }
                    }
                }
            }
        }
        HorizontalDivider(color = colors.line)
        Note(kind, value, onEdit)
    }
}

/** "Set by `{bpm: 90}` in the song · Edit", or "Default; the song has no `{time}`". */
@Composable
private fun Note(kind: SongDefaultKind, value: SongDefaultValue, onEdit: (Int) -> Unit) {
    val colors = appColors
    val code = SpanStyle(color = colors.directive, fontFamily = FontFamily.Monospace)
    val setBy = stringResource(R.string.song_defaults_set_by)
    val inSong = stringResource(R.string.song_defaults_in_song)
    val edit = stringResource(R.string.song_defaults_edit)
    val defaultNote = stringResource(R.string.song_defaults_default_note)
    val text = buildAnnotatedString {
        if (value.fromDirective) {
            append(setBy)
            append(' ')
            withStyle(code) { append(directiveCode(kind, value.value)) }
            append(' ')
            append(inSong)
            append(" · ")
            val offset = value.directiveOffset
            if (offset != null) {
                withLink(
                    LinkAnnotation.Clickable(
                        "edit",
                        TextLinkStyles(SpanStyle(color = colors.primary, fontWeight = FontWeight.Medium)),
                    ) { onEdit(offset) },
                ) { append(edit) }
            }
        } else {
            append(defaultNote)
            append(' ')
            withStyle(code) { append("{${kind.directive}}") }
        }
    }
    Text(text, Modifier.padding(start = 36.dp, top = 2.dp, bottom = 8.dp), fontSize = 11.sp, lineHeight = 15.sp, color = colors.muted)
}

/** The tempo default, typed (the session parses and clamps it). */
@Composable
private fun TempoDialog(current: String, onApply: (String) -> Unit, onDismiss: () -> Unit) {
    var field by remember { mutableStateOf(TextFieldValue(current, TextRange(0, current.length))) }
    val focus = remember { FocusRequester() }
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = appColors.surfaceHigh,
        title = { Text(stringResource(R.string.insert_tempo)) },
        text = {
            OutlinedTextField(
                value = field,
                onValueChange = { field = it },
                singleLine = true,
                suffix = { Text(stringResource(R.string.toolbar_bpm_unit)) },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                keyboardActions = KeyboardActions(onDone = { onApply(field.text) }),
                modifier = Modifier.width(160.dp).focusRequester(focus),
            )
            LaunchedEffect(Unit) { focus.requestFocus() }
        },
        confirmButton = { TextButton(onClick = { onApply(field.text) }, enabled = field.text.isNotBlank()) { Text(stringResource(android.R.string.ok)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } },
    )
}
