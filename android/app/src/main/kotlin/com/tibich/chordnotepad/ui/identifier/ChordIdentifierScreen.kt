package com.tibich.chordnotepad.ui.identifier

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogWindowProvider
import androidx.core.view.WindowCompat
import androidx.compose.ui.window.DialogProperties
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.bridge.IdentifierState
import com.tibich.chordnotepad.bridge.ScreenCommands
import com.tibich.chordnotepad.bridge.SessionRepository
import com.tibich.chordnotepad.ui.icons.AppIcons
import kotlinx.coroutines.flow.filterNotNull

// The desktop's selected-key blue (ui/chord_identifier.py).
private val SelectedKey = Color(0xFF4A90E2)

/**
 * Tools › Identify Chord: the chord identifier, full screen on phones
 * ([compact]) and a dialog on tablets. Everything it shows comes from the
 * session's `IdentifierState`; the session's status line is repeated at the
 * bottom so "Inserted chord: C" is seen while the editor is covered.
 *
 * @param insertAtCursor Inserts a chord at the editor's cursor (`insert_chord`).
 */
@Composable
fun ChordIdentifierDialog(
    repo: SessionRepository,
    commands: ScreenCommands,
    insertAtCursor: (String) -> Unit,
    compact: Boolean,
    onClose: () -> Unit,
) {
    var typed by rememberSaveable { mutableStateOf("") }
    var picked by rememberSaveable { mutableStateOf<String?>(null) }
    var opened by rememberSaveable { mutableStateOf(false) }
    val model = remember { IdentifierModel(commands, insertAtCursor, typed, picked) }
    LaunchedEffect(model) {
        if (!opened) {
            model.open()
            opened = true
        }
    }
    LaunchedEffect(model) {
        snapshotFlow { model.typed to model.picked }.collect { (t, p) ->
            typed = t
            picked = p
        }
    }
    LaunchedEffect(model) { repo.identifier.filterNotNull().collect(model::onState) }
    val state by repo.identifier.collectAsState()
    val status by repo.status.collectAsState()

    Dialog(onDismissRequest = onClose, properties = identifierDialogProperties(compact)) {
        if (compact) SystemBarIcons(MaterialTheme.colorScheme.surface.luminance() > 0.5f)
        Surface(
            modifier = if (compact) Modifier.fillMaxSize() else Modifier.widthIn(max = 640.dp).heightIn(max = 720.dp),
            shape = if (compact) MaterialTheme.shapes.extraSmall else MaterialTheme.shapes.extraLarge,
            color = MaterialTheme.colorScheme.surface,
        ) {
            ChordIdentifier(state, model, status?.text, onClose, if (compact) Modifier.safeDrawingPadding() else Modifier)
        }
    }
}

/**
 * The full-screen (phone) identifier draws edge to edge like the rest of the
 * app (`enableEdgeToEdge`): its window doesn't fit the system bars, so the
 * surface covers the status bar strip and [safeDrawingPadding] keeps the
 * content clear of the bars and the keyboard.
 */
internal fun identifierDialogProperties(compact: Boolean) =
    DialogProperties(usePlatformDefaultWidth = !compact, decorFitsSystemWindows = !compact)

/**
 * Status and navigation bar icons for the full-screen dialog's own window
 * (it doesn't inherit the activity's `enableEdgeToEdge` styling, so its
 * clock and battery were white on the light surface): dark icons on a light
 * surface, light icons on a dark one.
 */
@Composable
private fun SystemBarIcons(lightSurface: Boolean) {
    val view = LocalView.current
    SideEffect {
        val window = (view.parent as? DialogWindowProvider)?.window ?: return@SideEffect
        WindowCompat.getInsetsController(window, view).apply {
            isAppearanceLightStatusBars = lightSurface
            isAppearanceLightNavigationBars = lightSurface
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ChordIdentifier(
    state: IdentifierState?,
    model: IdentifierModel,
    status: String?,
    onClose: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.fillMaxSize()) {
        TopAppBar(
            title = { Text(stringResource(R.string.identifier_title)) },
            navigationIcon = {
                IconButton(onClick = onClose) { Icon(AppIcons.ArrowBack, stringResource(R.string.identifier_close)) }
            },
        )
        Column(Modifier.weight(1f).padding(horizontal = 16.dp)) {
            Text(stringResource(R.string.identifier_hint), style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(12.dp))
            Keyboard(
                selectedMidi = state?.notes?.map { it.midi }.orEmpty().toSet(),
                onTap = model::tapKey,
                onLongPress = model::pressKey,
                modifier = Modifier.fillMaxWidth().height(132.dp),
            )
            Spacer(Modifier.height(12.dp))
            NotesRow(model.typed, state?.typedTextError, model::type, model::clear)
            Spacer(Modifier.height(8.dp))
            Text(stringResource(R.string.identifier_candidates), style = MaterialTheme.typography.titleSmall)
            Candidates(state, model.picked, model::pick, model::insert, Modifier.weight(1f).fillMaxWidth())
        }
        HorizontalDivider()
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                status.orEmpty(),
                style = MaterialTheme.typography.bodySmall,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            Button(onClick = { model.insert() }, enabled = model.picked != null) {
                Text(stringResource(R.string.identifier_insert))
            }
        }
    }
}

@Composable
private fun NotesRow(text: String, error: String?, onType: (String) -> Unit, onClear: () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        OutlinedTextField(
            value = text,
            onValueChange = onType,
            label = { Text(stringResource(R.string.identifier_notes)) },
            singleLine = true,
            isError = error != null,
            supportingText = error?.let { { Text(it) } },
            keyboardOptions = KeyboardOptions(autoCorrectEnabled = false),
            modifier = Modifier.weight(1f),
        )
        OutlinedButton(onClick = onClear, modifier = Modifier.padding(start = 8.dp)) {
            Text(stringResource(R.string.identifier_clear))
        }
    }
}

/** The candidates (tap plays, double-tap inserts), or the session's message when there are none. */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun Candidates(
    state: IdentifierState?,
    picked: String?,
    onPick: (String) -> Unit,
    onInsert: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val candidates = state?.candidates.orEmpty()
    if (candidates.isEmpty()) {
        Text(
            state?.message.orEmpty(),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = modifier.padding(vertical = 12.dp),
        )
        return
    }
    LazyColumn(modifier) {
        items(candidates, key = { it }) { chord ->
            val selected = chord == picked
            Text(
                chord,
                style = MaterialTheme.typography.bodyLarge,
                color = if (selected) MaterialTheme.colorScheme.onSecondaryContainer else MaterialTheme.colorScheme.onSurface,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(if (selected) MaterialTheme.colorScheme.secondaryContainer else Color.Transparent)
                    .combinedClickable(onClick = { onPick(chord) }, onDoubleClick = { onInsert(chord) })
                    .heightIn(min = 48.dp)
                    .padding(horizontal = 12.dp, vertical = 12.dp),
            )
        }
    }
}

/** The two-octave piano: tap toggles a key, long-press sounds it. */
@Composable
private fun Keyboard(
    selectedMidi: Set<Int>,
    onTap: (PianoKey) -> Unit,
    onLongPress: (PianoKey) -> Unit,
    modifier: Modifier = Modifier,
) {
    val piano = remember { PianoKeyboard() }
    val measurer = rememberTextMeasurer()
    val description = stringResource(R.string.identifier_keyboard)
    val outline = MaterialTheme.colorScheme.outline
    Canvas(
        modifier
            .semantics { contentDescription = description }
            .pointerInput(piano) {
                fun at(o: Offset) = piano.keyAt(o.x, o.y, size.width.toFloat(), size.height.toFloat())
                detectTapGestures(
                    onTap = { o -> at(o)?.let(onTap) },
                    onLongPress = { o -> at(o)?.let(onLongPress) },
                )
            },
    ) {
        val unit = size.width / piano.whiteKeyCount
        for (key in piano.keys) {
            val selected = key.midi in selectedMidi
            val h = if (key.isBlack) size.height * PianoKeyboard.BLACK_HEIGHT else size.height
            val topLeft = Offset(key.left * unit, 0f)
            val keySize = Size(key.width * unit, h)
            val fill = when {
                selected -> SelectedKey
                key.isBlack -> Color.Black
                else -> Color.White
            }
            drawRoundRect(fill, topLeft, keySize, CornerRadius(3.dp.toPx()))
            drawRoundRect(if (key.isBlack) Color.Black else outline, topLeft, keySize, CornerRadius(3.dp.toPx()), Stroke(1.dp.toPx()))
            val label = measurer.measure(
                key.name,
                TextStyle(fontSize = if (key.isBlack) 8.sp else 10.sp, color = if (selected || key.isBlack) Color.White else Color.Black),
            )
            labelKey(label, topLeft, keySize)
        }
    }
}

private fun DrawScope.labelKey(label: androidx.compose.ui.text.TextLayoutResult, topLeft: Offset, keySize: Size) {
    val x = topLeft.x + (keySize.width - label.size.width) / 2f
    val y = topLeft.y + keySize.height - label.size.height - 4.dp.toPx()
    if (label.size.width <= keySize.width) drawText(label, topLeft = Offset(x, y))
}
