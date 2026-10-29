package io.github.chibicitiberiu.chordnotepad.ui.toolbar

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.input.key.Key
import androidx.compose.ui.input.key.key
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

// The desktop scrubber chip's colours (ui/scrubber.py, constants.py).
private val LinkBlue = Color(0xFF1565C0)
private val ReadOnlyGray = Color(0xFF888888)
private val ScrubTint = Color(0xFFE6EFFA)
private val ScrubTintPressed = Color(0xFFD4E4F7)

/**
 * A number you drag sideways to change, tap to type, long-press to reset
 * (the desktop scrubber, with long-press for its middle-click).
 *
 * @param text What the chip shows.
 * @param value The value a drag starts from.
 * @param editable False shows [text] greyed and ignores gestures (BPM while playing).
 * @param onDrag A dragged value (raw; the session clamps and snaps it).
 * @param onTyped The text typed in the field (the session parses it).
 * @param onReset Back to the default.
 * @param description What the value is, for accessibility.
 */
@Composable
fun Scrubber(
    text: String,
    value: Double,
    editable: Boolean,
    onDrag: (Double) -> Unit,
    onTyped: (String) -> Unit,
    onReset: () -> Unit,
    description: String,
    modifier: Modifier = Modifier,
) {
    var editing by rememberSaveable { mutableStateOf(false) }
    if (!editable) editing = false
    val currentValue by rememberUpdatedState(value)
    val currentOnDrag by rememberUpdatedState(onDrag)
    var pressed by remember { mutableStateOf(false) }

    val chip = Modifier
        .widthIn(min = 52.dp)
        .background(
            if (!editable) Color.Transparent else if (pressed) ScrubTintPressed else ScrubTint,
            RoundedCornerShape(4.dp),
        )
        .padding(horizontal = 6.dp, vertical = 4.dp)

    if (editing) {
        ScrubberEntry(
            initial = text,
            onCommit = { typed ->
                editing = false
                if (typed.isNotBlank() && typed.trim() != text) onTyped(typed.trim())
            },
            onCancel = { editing = false },
            modifier = modifier.then(chip),
        )
        return
    }

    val gestures = if (!editable) Modifier else Modifier
        .pointerInput(Unit) {
            detectTapGestures(
                onPress = {
                    pressed = true
                    tryAwaitRelease()
                    pressed = false
                },
                onTap = { editing = true },
                onLongPress = { onReset() },
            )
        }
        .pointerInput(Unit) {
            val pixelsPerStep = ScrubberMath.PIXELS_PER_STEP_DP * density
            var start = 0.0
            var dx = 0f
            var last = Double.NaN
            detectHorizontalDragGestures(
                onDragStart = {
                    start = currentValue
                    dx = 0f
                    last = start
                    pressed = true
                },
                onDragEnd = { pressed = false },
                onDragCancel = { pressed = false },
                onHorizontalDrag = { change, amount ->
                    change.consume()
                    dx += amount
                    val v = ScrubberMath.dragged(start, dx, pixelsPerStep)
                    if (v != last) {
                        last = v
                        currentOnDrag(v)
                    }
                },
            )
        }

    Box(
        modifier
            .then(chip)
            .then(gestures)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text,
            color = if (editable) LinkBlue else ReadOnlyGray,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center,
            maxLines = 1,
        )
    }
}

/** The "type a value" field: Done or losing focus commits, Escape cancels. */
@Composable
private fun ScrubberEntry(
    initial: String,
    onCommit: (String) -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier,
) {
    var field by remember { mutableStateOf(TextFieldValue(initial, TextRange(0, initial.length))) }
    val focus = remember { FocusRequester() }
    var hadFocus by remember { mutableStateOf(false) }
    var done by remember { mutableStateOf(false) }
    fun finish(commit: Boolean) {
        if (done) return
        done = true
        if (commit) onCommit(field.text) else onCancel()
    }
    LaunchedEffect(Unit) { focus.requestFocus() }
    BasicTextField(
        value = field,
        onValueChange = { field = it },
        singleLine = true,
        textStyle = TextStyle(
            color = LocalContentColor.current,
            fontWeight = FontWeight.Bold,
            textAlign = TextAlign.Center,
        ).merge(MaterialTheme.typography.bodyMedium),
        cursorBrush = SolidColor(LinkBlue),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text, imeAction = ImeAction.Done),
        keyboardActions = KeyboardActions(onDone = { finish(true) }),
        modifier = modifier
            .widthIn(min = 52.dp, max = 80.dp)
            .focusRequester(focus)
            .onFocusChanged {
                if (it.isFocused) hadFocus = true else if (hadFocus) finish(true)
            }
            .onPreviewKeyEvent {
                when (it.key) {
                    Key.Escape -> { finish(false); true }
                    Key.Enter, Key.NumPadEnter -> { finish(true); true }
                    else -> false
                }
            },
    )
}
