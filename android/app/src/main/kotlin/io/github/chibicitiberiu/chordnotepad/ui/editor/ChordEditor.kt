package io.github.chibicitiberiu.chordnotepad.ui.editor

import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.input.OutputTransformation
import androidx.compose.foundation.text.input.TextFieldDecorator
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.chibicitiberiu.chordnotepad.bridge.EditorState
import io.github.chibicitiberiu.chordnotepad.bridge.SpanKind
import io.github.chibicitiberiu.chordnotepad.ui.main.AppMode
import io.github.chibicitiberiu.chordnotepad.ui.play.ChordBox
import io.github.chibicitiberiu.chordnotepad.ui.play.PlayTap
import io.github.chibicitiberiu.chordnotepad.ui.play.grabsMarker
import io.github.chibicitiberiu.chordnotepad.ui.play.markerChord
import io.github.chibicitiberiu.chordnotepad.ui.play.playableChords
import io.github.chibicitiberiu.chordnotepad.ui.play.resolveTap
import io.github.chibicitiberiu.chordnotepad.ui.play.scrubTarget
import io.github.chibicitiberiu.chordnotepad.ui.theme.appColors
import kotlin.math.roundToInt

/** The desktop's default editor font size, before `EditorState` arrives. */
private const val DEFAULT_FONT_POINTS = 11

/** The text's padding inside the editor (the mockup's 8 px × 12 px). */
private val TextPadding = PaddingValues(horizontal = 12.dp, vertical = 8.dp)

/** The playhead marker's grab strip, centred on it. */
private val MarkerGrabWidth = 24.dp

/** A tap this close to a chord counts as on it. */
private val ChordSlop = 4.dp

/**
 * The song text in either mode, over the session's highlighting; a pinch
 * changes the font size in both.
 *
 * - [AppMode.EDIT]: an editable text field. A tap places the cursor (and
 *   opens the keyboard); it doesn't play anything.
 * - [AppMode.PLAY]: frozen, not a text field at all (so nothing can open the
 *   keyboard). The playhead marker sits before the chord at [playhead]. A tap
 *   on a chord moves the playhead there and plays it ([onPlayTap] with
 *   [PlayTap.OnChord]); a tap elsewhere moves it to the nearest chord; a drag
 *   that starts on the marker scrubs it (the marker follows the finger,
 *   [onScrub] gets the chord on release); other drags scroll. While
 *   a song plays ([playing]) a tap makes playback jump there (the session's
 *   rule) and the marker can't be dragged.
 *
 * Both modes share [scroll], so switching keeps the place. Offsets are UTF-16.
 */
@Composable
fun ChordEditor(
    controller: EditorController,
    editorState: EditorState?,
    mode: AppMode,
    playhead: Int?,
    playing: Boolean,
    scroll: ScrollState,
    onStepFontSize: (Int) -> Unit,
    onPlayTap: (PlayTap) -> Unit,
    onScrub: (Int) -> Unit,
    modifier: Modifier = Modifier,
    focusRequester: FocusRequester? = null,
) {
    val colors = appColors
    val fontPoints = editorState?.fontSize ?: DEFAULT_FONT_POINTS
    val textStyle = TextStyle(
        color = colors.editorText,
        fontFamily = fontKindFor(editorState?.fontFamily.orEmpty()).family,
        fontSize = editorFontSizeSp(fontPoints).sp,
    )
    val styles = remember(colors) { spanStylesFor(colors) }
    val playingStyle = remember(colors) { playingStyleFor(colors) }
    val currentPoints by rememberUpdatedState(fontPoints)
    var layout by remember { mutableStateOf<TextLayoutResult?>(null) }
    val padTop = with(LocalDensity.current) { 8.dp.roundToPx() }

    // Keep the sounding chord in view (the desktop's `see`), only when playback moved on.
    val sounding = controller.playing
    LaunchedEffect(sounding, mode) {
        val p = sounding ?: return@LaunchedEffect
        val l = layout ?: return@LaunchedEffect
        if (p.start > l.layoutInput.text.length) return@LaunchedEffect
        val line = l.getLineForOffset(p.start)
        val top = l.getLineTop(line).roundToInt() + padTop
        val bottom = l.getLineBottom(line).roundToInt() + padTop
        val viewport = scroll.viewportSize
        if (viewport > 0 && (top < scroll.value || bottom > scroll.value + viewport)) {
            scroll.animateScrollTo((top - viewport / 3).coerceIn(0, scroll.maxValue))
        }
    }

    Box(
        modifier
            .background(colors.surface)
            .pinchToZoomFont(currentPoints = { currentPoints }, onStep = onStepFontSize),
    ) {
        when (mode) {
            AppMode.EDIT -> BasicTextField(
                state = controller.state,
                modifier = Modifier.fillMaxSize().let { m -> focusRequester?.let { m.focusRequester(it) } ?: m },
                readOnly = editorState?.readOnly ?: false,
                inputTransformation = PasteNormalization,
                textStyle = textStyle,
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.None,
                    autoCorrectEnabled = false,
                ),
                onTextLayout = { result -> layout = result() },
                cursorBrush = SolidColor(colors.primary),
                outputTransformation = remember(controller, styles, playingStyle) {
                    highlightTransformation(controller, styles, playingStyle)
                },
                scrollState = scroll,
                decorator = TextFieldDecorator { innerTextField ->
                    Box(Modifier.fillMaxSize().padding(TextPadding)) { innerTextField() }
                },
            )
            AppMode.PLAY -> PlayText(
                controller = controller,
                textStyle = textStyle,
                styles = styles,
                playingStyle = playingStyle,
                playhead = playhead,
                playing = playing,
                scroll = scroll,
                onLayout = { layout = it },
                onPlayTap = onPlayTap,
                onScrub = onScrub,
            )
        }
    }
}

/**
 * Play mode's frozen text: highlighted, with the playhead marker, tap and
 * scrub handling. A plain [BasicText] (no focus, no keyboard).
 */
@Composable
private fun PlayText(
    controller: EditorController,
    textStyle: TextStyle,
    styles: List<Pair<SpanKind, SpanStyle>>,
    playingStyle: SpanStyle,
    playhead: Int?,
    playing: Boolean,
    scroll: ScrollState,
    onLayout: (TextLayoutResult) -> Unit,
    onPlayTap: (PlayTap) -> Unit,
    onScrub: (Int) -> Unit,
) {
    val colors = appColors
    val density = LocalDensity.current
    val text = controller.state.text.toString()
    val spans = controller.spans
    val sounding = controller.playing
    val annotated = remember(text, spans, sounding, styles, playingStyle) {
        highlighted(text, spans, sounding, styles, playingStyle)
    }
    val chords = remember(spans) { playableChords(spans) }
    var layout by remember { mutableStateOf<TextLayoutResult?>(null) }
    val boxes = remember(layout, chords) { layout?.let { l -> chords.mapNotNull { chordBox(l, it.start, it.end) } }.orEmpty() }
    // The marker moves at once under the finger; the session's playhead takes over when it changes.
    var localHead by remember { mutableStateOf<Int?>(null) }
    LaunchedEffect(playhead) { localHead = null }
    val head = localHead ?: playhead
    val marker = markerChord(chords, head)?.let { m -> boxes.firstOrNull { it.start == m.start } }

    val currentBoxes by rememberUpdatedState(boxes)
    val currentMarker by rememberUpdatedState(marker)
    val currentHead by rememberUpdatedState(head)
    val isPlaying by rememberUpdatedState(playing)
    val padX = with(density) { 12.dp.toPx() }
    val padY = with(density) { 8.dp.toPx() }
    val grabPx = with(density) { MarkerGrabWidth.toPx() }
    val slopPx = with(density) { ChordSlop.toPx() }
    val markerColor = colors.primary

    BoxWithConstraints(Modifier.fillMaxSize()) {
        Box(
            Modifier
                .fillMaxSize()
                .verticalScroll(scroll)
                .pointerInput(Unit) {
                    awaitEachGesture {
                        val down = awaitFirstDown(requireUnconsumed = false)
                        val start = down.position - Offset(padX, padY)
                        // The marker follows playback while a song plays: no scrubbing then.
                        val grabbed = !isPlaying && grabsMarker(currentMarker, start.x, start.y, grabPx)
                        if (grabbed) down.consume()
                        var moved = false
                        var multi = false
                        // Where a scrub has taken the marker; sent once, on release
                        // (set_playhead restarts playback, so not per step).
                        var scrubbed: Int? = null
                        while (true) {
                            val event = awaitPointerEvent()
                            if (event.changes.count { it.pressed } > 1) multi = true
                            val change = event.changes.firstOrNull { it.id == down.id } ?: break
                            if ((change.position - down.position).getDistance() > viewConfiguration.touchSlop) moved = true
                            if (grabbed && !multi) {
                                change.consume()
                                if (moved) {
                                    val p = change.position - Offset(padX, padY)
                                    scrubTarget(currentBoxes, currentHead, p.x, p.y)?.let {
                                        localHead = it
                                        scrubbed = it
                                    }
                                }
                            }
                            if (!change.pressed) {
                                scrubbed?.let(onScrub)
                                if (!moved && !multi) {
                                    val p = change.position - Offset(padX, padY)
                                    resolveTap(currentBoxes, p.x, p.y, slopPx)?.let { tap ->
                                        localHead = when (tap) {
                                            is PlayTap.OnChord -> tap.start
                                            is PlayTap.Nearest -> tap.start
                                        }
                                        onPlayTap(tap)
                                    }
                                }
                                break
                            }
                        }
                    }
                },
        ) {
            BasicText(
                annotated,
                style = textStyle,
                onTextLayout = {
                    layout = it
                    onLayout(it)
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = this@BoxWithConstraints.maxHeight)
                    .padding(TextPadding)
                    .drawPlayhead(marker, markerColor),
            )
        }
    }
}

/** The marker before the playhead's chord: a primary bar the line's height and a small triangle above it. */
private fun Modifier.drawPlayhead(marker: ChordBox?, color: Color): Modifier = drawWithContent {
    drawContent()
    drawMarker(marker, color)
}

private fun DrawScope.drawMarker(marker: ChordBox?, color: Color) {
    val m = marker ?: return
    val bar = 3.dp.toPx()
    val x = m.left - bar - 0.5.dp.toPx()
    drawRoundRect(
        color,
        topLeft = Offset(x, m.top),
        size = Size(bar, m.bottom - m.top),
        cornerRadius = CornerRadius(bar / 2),
    )
    val cx = x + bar / 2
    val half = 5.5.dp.toPx()
    val h = 7.dp.toPx()
    val triangle = Path().apply {
        moveTo(cx - half, m.top - h + 1.dp.toPx())
        lineTo(cx + half, m.top - h + 1.dp.toPx())
        lineTo(cx, m.top + 1.dp.toPx())
        close()
    }
    drawPath(triangle, color)
}

/** Where the chord `[start, end)` sits in [layout] (its first line). */
internal fun chordBox(layout: TextLayoutResult, start: Int, end: Int): ChordBox? {
    val length = layout.layoutInput.text.length
    if (start < 0 || end > length || start >= end) return null
    val line = layout.getLineForOffset(start)
    val left = layout.getHorizontalPosition(start, usePrimaryDirection = true)
    val right = if (layout.getLineForOffset(end - 1) == line) {
        layout.getHorizontalPosition(end, usePrimaryDirection = true).takeIf { it > left }
            ?: layout.getBoundingBox(end - 1).right
    } else {
        layout.getLineRight(line)
    }
    return ChordBox(start, end, left, layout.getLineTop(line), right, layout.getLineBottom(line))
}

/** The text with the session's spans and the sounding chord painted, for Play mode. */
private fun highlighted(
    text: String,
    spans: List<PaintedSpan>,
    sounding: PlayingChord?,
    styles: List<Pair<SpanKind, SpanStyle>>,
    playingStyle: SpanStyle,
): AnnotatedString = AnnotatedString.Builder(text).apply {
    for ((kind, style) in styles) {
        for (s in spans) {
            if (s.kind == kind && s.start < s.end && s.end <= text.length) addStyle(style, s.start, s.end)
        }
    }
    sounding?.let { p -> if (p.start < p.end && p.end <= text.length) addStyle(playingStyle, p.start, p.end) }
}.toAnnotatedString()

/** Paints the controller's spans, then the playing chord on top (Edit mode). */
private fun highlightTransformation(
    controller: EditorController,
    styles: List<Pair<SpanKind, SpanStyle>>,
    playingStyle: SpanStyle,
) = OutputTransformation {
    val spans = controller.spans
    for ((kind, style) in styles) {
        for (s in spans) {
            if (s.kind == kind && s.start < s.end && s.end <= length) addStyle(style, s.start, s.end)
        }
    }
    controller.playing?.let { p ->
        if (p.start < p.end && p.end <= length) addStyle(playingStyle, p.start, p.end)
    }
}

/**
 * Two-finger pinch → font size steps, like the desktop's Ctrl+wheel. The
 * gesture is taken from the text (no scrolling or selecting meanwhile);
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
