package io.github.chibicitiberiu.chordnotepad.ui.editor

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.input.OutputTransformation
import androidx.compose.foundation.text.input.TextFieldDecorator
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.changedToUpIgnoreConsumed
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.chibicitiberiu.chordnotepad.bridge.EditorState
import kotlin.math.roundToInt

/** The desktop's default editor font size, before `EditorState` arrives. */
private const val DEFAULT_FONT_POINTS = 11

/**
 * The song editor: the session's highlighting over a plain text field, tap a
 * chord to hear it, pinch to change the font size (the desktop's
 * Ctrl+wheel), read-only while a song plays, scrolled to the sounding chord.
 *
 * @param controller The app-scoped editor model.
 * @param editorState Font and read-only flag from the session (null before it starts).
 * @param onStepFontSize Grow (+) or shrink (-) the font by that many points.
 */
@Composable
fun ChordEditor(
    controller: EditorController,
    editorState: EditorState?,
    onStepFontSize: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    val fontPoints = editorState?.fontSize ?: DEFAULT_FONT_POINTS
    val fontKind = fontKindFor(editorState?.fontFamily.orEmpty())
    val textStyle = TextStyle(
        color = EditorText,
        fontFamily = fontKind.family,
        fontSize = editorFontSizeSp(fontPoints).sp,
    )
    val scroll = rememberScrollState()
    var layout by remember { mutableStateOf<TextLayoutResult?>(null) }
    val highlight = remember(controller) { highlightTransformation(controller) }
    val currentPoints by rememberUpdatedState(fontPoints)

    // Keep the sounding chord in view (the desktop's `see`), only when
    // playback moved on.
    val playing = controller.playing
    LaunchedEffect(playing) {
        val p = playing ?: return@LaunchedEffect
        val l = layout ?: return@LaunchedEffect
        if (p.start > l.layoutInput.text.length) return@LaunchedEffect
        val line = l.getLineForOffset(p.start)
        val top = l.getLineTop(line).roundToInt()
        val bottom = l.getLineBottom(line).roundToInt()
        val viewport = scroll.viewportSize
        if (viewport > 0 && (top < scroll.value || bottom > scroll.value + viewport)) {
            scroll.animateScrollTo((top - viewport / 3).coerceIn(0, scroll.maxValue))
        }
    }

    Box(
        modifier
            .border(1.dp, MaterialTheme.colorScheme.outlineVariant)
            .background(EditorBackground)
            .pinchToZoomFont(currentPoints = { currentPoints }, onStep = onStepFontSize),
    ) {
        BasicTextField(
            state = controller.state,
            modifier = Modifier.fillMaxSize(),
            readOnly = editorState?.readOnly ?: false,
            inputTransformation = PasteNormalization,
            textStyle = textStyle,
            keyboardOptions = KeyboardOptions(
                capitalization = KeyboardCapitalization.None,
                autoCorrectEnabled = false,
            ),
            onTextLayout = { result -> layout = result() },
            cursorBrush = SolidColor(EditorText),
            outputTransformation = highlight,
            scrollState = scroll,
            decorator = TextFieldDecorator { innerTextField ->
                Box(
                    Modifier
                        .fillMaxSize()
                        .padding(horizontal = 6.dp, vertical = 4.dp)
                        .onTap { position ->
                            val l = layout ?: return@onTap
                            val offset = l.getOffsetForPosition(position + Offset(0f, scroll.value.toFloat()))
                            controller.tapAt(offset)
                        },
                ) { innerTextField() }
            },
        )
    }
}

/** Paints the controller's spans, then the playing chord on top. */
private fun highlightTransformation(controller: EditorController) = OutputTransformation {
    val spans = controller.spans
    for ((kind, style) in SpanStyles) {
        for (s in spans) {
            if (s.kind == kind && s.start < s.end && s.end <= length) addStyle(style, s.start, s.end)
        }
    }
    controller.playing?.let { p ->
        if (p.start < p.end && p.end <= length) addStyle(PlayingStyle, p.start, p.end)
    }
}

/**
 * A single-finger tap (no drag, released before a long press), seen before
 * the text field handles it, which it still does (the cursor moves as usual).
 * [onTap] gets the position in this element.
 */
private fun Modifier.onTap(onTap: (Offset) -> Unit): Modifier = pointerInput(Unit) {
    awaitEachGesture {
        val down = awaitFirstDown(requireUnconsumed = false, pass = PointerEventPass.Initial)
        val slop = viewConfiguration.touchSlop
        val longPress = viewConfiguration.longPressTimeoutMillis
        var isTap = true
        while (true) {
            val event = awaitPointerEvent(PointerEventPass.Initial)
            if (event.changes.count { it.pressed } > 1) isTap = false
            val change = event.changes.firstOrNull { it.id == down.id } ?: break
            if ((change.position - down.position).getDistance() > slop) isTap = false
            if (change.changedToUpIgnoreConsumed()) {
                if (isTap && change.uptimeMillis - down.uptimeMillis < longPress) onTap(change.position)
                break
            }
        }
    }
}

/**
 * Two-finger pinch → font size steps, like the desktop's Ctrl+wheel. The
 * gesture is taken from the text field (no scrolling or selecting meanwhile);
 * one-finger gestures pass through untouched.
 */
private fun Modifier.pinchToZoomFont(currentPoints: () -> Int, onStep: (Int) -> Unit): Modifier =
    pointerInput(Unit) {
        awaitEachGesture {
            awaitFirstDown(requireUnconsumed = false, pass = PointerEventPass.Initial)
            var zoom = 1f
            var base = -1
            var sent = 0
            while (true) {
                val event = awaitPointerEvent(PointerEventPass.Initial)
                val pressed = event.changes.count { it.pressed }
                if (pressed == 0) break
                if (pressed < 2) continue
                if (base < 0) {
                    base = currentPoints()
                    sent = base
                }
                zoom *= event.calculateZoom()
                event.changes.forEach { it.consume() }
                val target = pinchFontSize(base, zoom)
                if (target != sent) {
                    onStep(target - sent)
                    sent = target
                }
            }
        }
    }

/** Smallest and largest editor font size (`MIN_FONT_SIZE`/`MAX_FONT_SIZE`; the session clamps too). */
const val MIN_FONT_POINTS = 6
const val MAX_FONT_POINTS = 72

/** The font size a pinch of [zoom] (1 = none) from [basePoints] asks for. */
fun pinchFontSize(basePoints: Int, zoom: Float): Int =
    (basePoints * zoom).roundToInt().coerceIn(MIN_FONT_POINTS, MAX_FONT_POINTS)
