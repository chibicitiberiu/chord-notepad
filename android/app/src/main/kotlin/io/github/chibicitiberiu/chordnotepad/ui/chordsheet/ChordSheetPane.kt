package io.github.chibicitiberiu.chordnotepad.ui.chordsheet

import android.content.pm.ApplicationInfo
import android.util.Log
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.ui.icons.IconTints
import io.github.chibicitiberiu.chordnotepad.ui.icons.MdiIcon
import io.github.chibicitiberiu.chordnotepad.ui.theme.appColors
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateCentroid
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.scrollable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.PlainTooltip
import androidx.compose.material3.Text
import androidx.compose.material3.TooltipAnchorPosition
import androidx.compose.material3.TooltipBox
import androidx.compose.material3.TooltipDefaults
import androidx.compose.material3.rememberTooltipState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.PointerInputScope
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFontFamilyResolver
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import io.github.chibicitiberiu.chordnotepad.bridge.ChordSheetState
import io.github.chibicitiberiu.chordnotepad.bridge.ChordSheetView
import io.github.chibicitiberiu.chordnotepad.bridge.PyHost
import io.github.chibicitiberiu.chordnotepad.bridge.SessionCommands
import io.github.chibicitiberiu.chordnotepad.bridge.SessionRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.combine

private const val TAG = "CNChordSheet"

/** `renderer_interface.NOTE_INK`: the colour of untinted glyph images. */
private const val NOTE_INK = "#22323a"

/** The marker lane's height until the first buffer says otherwise (`marker_lane.LANE_HEIGHT`). */
private const val DEFAULT_LANE_HEIGHT = 20f

/**
 * The chord sheet: view tabs and zoom buttons above a horizontally scrolling
 * strip of chord cards (piano roll, staff, fret cards, tab), with the marker
 * lane on top and a frozen gutter on the left. Tapping a chord auditions it;
 * the chord under the playhead is highlighted and kept in view; pinch zooms.
 *
 * Draws nothing while [ChordSheetState.visible] is false. The caller sizes it
 * (the resizable split under the editor); the strip fetches a new op buffer
 * when the height changes.
 */
@Composable
fun ChordSheetPane(host: PyHost, modifier: Modifier = Modifier) {
    val source = remember(host) { ChordSheetBufferSource(host::chordSheetBuffer) }
    ChordSheetPane(host.repository, host.commands, source, modifier)
}

/**
 * [ChordSheetPane] over explicit parts (tests, previews).
 *
 * @param repository Supplies [ChordSheetState].
 * @param commands Receives `set_chord_sheet_view`, `chord_sheet_zoom` and `audition`.
 * @param buffers Fetches op buffers (off Main).
 */
@Composable
fun ChordSheetPane(
    repository: SessionRepository,
    commands: SessionCommands,
    buffers: ChordSheetBufferSource,
    modifier: Modifier = Modifier,
) {
    val state by repository.chordSheet.collectAsState()
    val context = LocalContext.current
    val density = LocalDensity.current.density
    val glyphs = remember { GlyphCache(context.applicationContext.assets) }
    val controller = remember(buffers) {
        ChordSheetController(buffers, prepare = { glyphs.preload(it.imageKeys, density) })
    }
    var contentHeightDp by remember { mutableIntStateOf(0) }

    LaunchedEffect(controller) {
        controller.follow(
            combine(repository.chordSheet, snapshotFlow { contentHeightDp }) { s, h -> SheetRequest.of(s, h) },
        )
    }

    val current = state
    if (current == null || !current.visible) {
        Box(modifier)
        return
    }
    Column(modifier.background(appColors.surfaceLow)) {
        ChordSheetHeader(
            state = current,
            onSelect = commands::setChordSheetView,
            onZoom = commands::chordSheetZoom,
        )
        ChordSheetStrip(
            controller = controller,
            glyphs = glyphs,
            currentIndex = current.currentIndex,
            cursorIndex = current.cursorIndex,
            zoom = current.zoom,
            zoomSupported = current.zoomSupported,
            onAudition = commands::audition,
            onZoomSteps = commands::chordSheetZoom,
            onContentHeight = { contentHeightDp = it },
            modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 4.dp).padding(bottom = 4.dp),
        )
    }
}

/** The view tabs (disabled ones explain why on long-press) and the zoom buttons. */
@Composable
private fun ChordSheetHeader(state: ChordSheetState, onSelect: (String) -> Unit, onZoom: (Int) -> Unit) {
    Row(
        Modifier.fillMaxWidth().height(32.dp).padding(horizontal = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Row(
            Modifier.weight(1f).fillMaxHeight().horizontalScroll(rememberScrollState()),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            for (view in state.views) {
                ViewTab(
                    view = view,
                    selected = view.viewId == state.activeView,
                    reason = state.disabledReason,
                    onClick = { onSelect(view.viewId) },
                )
            }
        }
        // Views the core says don't zoom (the piano roll) show no zoom buttons; pinch follows the same flag.
        if (state.zoomSupported) {
            ZoomButton(R.drawable.mdi_magnify_minus, stringResource(R.string.sheet_zoom_out)) { onZoom(-1) }
            ZoomButton(R.drawable.mdi_magnify_plus, stringResource(R.string.sheet_zoom_in)) { onZoom(1) }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ViewTab(view: ChordSheetView, selected: Boolean, reason: String?, onClick: () -> Unit) {
    val colors = appColors
    val tab = @Composable {
        Box(
            Modifier
                .clip(RoundedCornerShape(8.dp))
                .background(if (selected) colors.surfaceHigh else Color.Transparent)
                .selectable(selected = selected, enabled = view.available, role = Role.Tab, onClick = onClick)
                .padding(horizontal = 10.dp, vertical = 4.dp),
        ) {
            Text(
                view.label,
                fontSize = 12.sp,
                fontWeight = FontWeight.Medium,
                color = when {
                    !view.available -> colors.muted.copy(alpha = 0.5f)
                    selected -> colors.text
                    else -> colors.muted
                },
            )
        }
    }
    if (view.available || reason.isNullOrEmpty()) {
        tab()
    } else {
        TooltipBox(
            positionProvider = TooltipDefaults.rememberTooltipPositionProvider(TooltipAnchorPosition.Above),
            tooltip = { PlainTooltip { Text(reason) } },
            state = rememberTooltipState(),
        ) { tab() }
    }
}

@Composable
private fun ZoomButton(icon: Int, description: String, onClick: () -> Unit) {
    Box(
        Modifier
            .size(30.dp)
            .clip(CircleShape)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = description },
        contentAlignment = Alignment.Center,
    ) {
        MdiIcon(icon, IconTints.Zoom, size = 19.dp)
    }
}

/** A pinch in progress: its scale so far and the viewport x it zooms about. */
private data class Pinch(val scale: Float, val focusX: Float, val committed: Boolean = false)

/**
 * The scrolling strip: lane + content in one canvas, the gutter beside it.
 * Scrolling and the playhead only redraw (the draw phase reads the scroll).
 */
@Composable
private fun ChordSheetStrip(
    controller: ChordSheetController,
    glyphs: GlyphCache,
    currentIndex: Int?,
    cursorIndex: Int?,
    zoom: Double,
    zoomSupported: Boolean,
    onAudition: (Int) -> Unit,
    onZoomSteps: (Int) -> Unit,
    onContentHeight: (Int) -> Unit,
    modifier: Modifier,
) {
    val sheet = controller.sheet
    val colors = appColors
    val density = LocalDensity.current.density
    // The buffer's colours for this theme, and the sheet's own background and playing column.
    val palette = remember(sheet, colors) {
        sheet?.colors?.mapValues { (spec, c) -> themedSheetColor(spec, c, colors) }.orEmpty()
    }
    val fontFamilyResolver = LocalFontFamilyResolver.current
    val painter = remember(fontFamilyResolver) {
        // Density 1, font scale 1: layouts measure in dp (see SheetPainter).
        SheetPainter(TextMeasurer(fontFamilyResolver, Density(1f, 1f), LayoutDirection.Ltr, cacheSize = 0), glyphs)
    }
    painter.defaultImageTint = if (colors.dark) {
        ColorFilter.tint(themedSheetColor(NOTE_INK, Color(0xFF22323A), colors), BlendMode.SrcIn)
    } else null
    painter.themeColor = { spec, c -> themedSheetColor(spec, c, colors) }
    val scroll = remember { StripScroll() }
    var viewportPx by remember { mutableIntStateOf(0) }
    var pinch by remember { mutableStateOf<Pinch?>(null) }
    val last = remember { arrayOfNulls<ChordSheetBuffer>(1) }
    val perf = rememberFramePerf()

    // A new buffer: new scroll bounds; keep the same music in view.
    LaunchedEffect(sheet, viewportPx) {
        val buffer = sheet?.buffer ?: return@LaunchedEffect
        val prev = last[0]
        val oldOffset = scroll.offset
        scroll.max = buffer.contentWidth * density - viewportPx
        if (prev != null && prev !== buffer) {
            val oldW = prev.contentWidth * density
            val newW = buffer.contentWidth * density
            when {
                prev.viewId == buffer.viewId && prev.zoom != buffer.zoom ->
                    scroll.snapTo(rescaleScroll(oldOffset, pinch?.focusX ?: (viewportPx / 2f), oldW, newW, viewportPx.toFloat()))
                prev.viewId != buffer.viewId && oldW > 0f -> scroll.snapTo(oldOffset / oldW * newW)
                else -> scroll.snapTo(oldOffset)
            }
            if (prev.zoom != buffer.zoom || prev.viewId != buffer.viewId) pinch = null
        }
        last[0] = buffer
    }

    // A pinch that didn't change the zoom (or whose buffer never came) springs back.
    LaunchedEffect(pinch?.committed) {
        if (pinch?.committed == true) {
            delay(1500)
            pinch = null
        }
    }

    // Follow the playhead (the desktop's 25 % / 70 % band).
    LaunchedEffect(currentIndex, sheet, viewportPx) {
        val buffer = sheet?.buffer ?: return@LaunchedEffect
        val slot = currentIndex?.let(buffer::slotFor) ?: return@LaunchedEffect
        val target = scrollTarget(
            playheadX = slot.x + slot.width / 2f,
            viewportWidth = viewportPx / density,
            currentScroll = scroll.offset / density,
            contentWidth = buffer.contentWidth,
        ) ?: return@LaunchedEffect
        scroll.animateTo(target * density)
    }

    val currentSheet by rememberUpdatedState(sheet)
    val currentZoom by rememberUpdatedState(zoom)
    val zoomable by rememberUpdatedState(zoomSupported)
    val laneHeight = sheet?.buffer?.laneHeight ?: DEFAULT_LANE_HEIGHT
    val gutterWidth = sheet?.buffer?.gutterWidth ?: 0f
    val background = colors.surfaceLow

    Box(modifier.background(background)) {
        val failure = controller.failure
        if (failure != null) {
            Text(failure, Modifier.align(Alignment.Center).padding(8.dp), color = colors.muted)
        }
        Row(Modifier.fillMaxSize()) {
            if (gutterWidth > 0f && sheet != null) {
                Canvas(Modifier.width(gutterWidth.dp).fillMaxHeight()) {
                    val variant = sheet.gutterAt(scroll.offset / density) ?: return@Canvas
                    withTransform({
                        translate(0f, laneHeight * density)
                        scale(density, density, Offset.Zero)
                    }) {
                        // The piano roll's keyboard keeps its own look (its labels sit on white keys).
                        val gutterColors = if (sheet.buffer.viewId == "keyboard") sheet.colors else palette
                        with(painter) { drawOps(variant, gutterColors, Float.NEGATIVE_INFINITY, Float.POSITIVE_INFINITY, density) }
                    }
                }
            }
            Box(
                Modifier
                    .weight(1f)
                    .fillMaxHeight()
                    .clipToBounds()
                    .onSizeChanged {
                        viewportPx = it.width
                        onContentHeight(((it.height / density) - laneHeight).toInt())
                    }
                    .pointerInput(Unit) {
                        detectPinch(
                            onPinch = { scale, focus -> if (zoomable) pinch = Pinch(scale, focus) },
                            onEnd = { scale, focus ->
                                if (!zoomable) return@detectPinch
                                val steps = pinchZoomSteps(zoomable, scale, currentZoom)
                                Log.i(TAG, "pinch scale=$scale -> $steps zoom steps")
                                if (steps == 0) {
                                    pinch = null
                                } else {
                                    pinch = Pinch(scale, focus, committed = true)
                                    onZoomSteps(steps)
                                }
                            },
                        )
                    }
                    .scrollable(scroll.scrollable, Orientation.Horizontal, reverseDirection = true)
                    .pointerInput(Unit) {
                        detectTapGestures { pos ->
                            val buffer = currentSheet?.buffer ?: return@detectTapGestures
                            if (pos.y < buffer.laneHeight * density) return@detectTapGestures
                            buffer.slotAt((scroll.offset + pos.x) / density)?.let {
                                Log.i(TAG, "audition ${it.chordIndex}")
                                onAudition(it.chordIndex)
                            }
                        }
                    },
            ) {
                Canvas(
                    Modifier.fillMaxSize().graphicsLayer {
                        val p = pinch
                        if (p != null) {
                            scaleX = p.scale
                            scaleY = p.scale
                            transformOrigin = TransformOrigin(if (size.width > 0f) p.focusX / size.width else 0f, 0f)
                        }
                    },
                ) {
                    val s = sheet ?: return@Canvas
                    perf.frame {
                        drawStrip(
                            s, painter, palette, scroll.offset, density, currentIndex,
                            // The playhead's edge mark while nothing plays.
                            cursorIndex.takeIf { currentIndex == null }, colors.sheetPlaying, colors.primary,
                        )
                    }
                }
            }
        }
    }
}

/**
 * Lane, highlight and content ops for the visible range, at scroll offset
 * [scrollPx]: the playing column behind the chord sounding, else a primary
 * edge on the left of the playhead's chord ([cursorIndex]).
 */
private fun DrawScope.drawStrip(
    sheet: PreparedSheet,
    painter: SheetPainter,
    palette: Map<String, Color>,
    scrollPx: Float,
    density: Float,
    currentIndex: Int?,
    cursorIndex: Int?,
    playingColor: Color,
    edgeColor: Color,
) {
    val buffer = sheet.buffer
    val left = scrollPx / density
    val right = (scrollPx + size.width) / density
    withTransform({
        translate(-scrollPx, 0f)
        scale(density, density, Offset.Zero)
    }) {
        with(painter) {
            drawOps(sheet.lane, palette, left, right, density)
            translate(top = buffer.laneHeight) {
                currentIndex?.let(buffer::slotFor)?.let { slot ->
                    drawRoundRect(playingColor, Offset(slot.x, 2f), Size(slot.width, buffer.contentHeight - 4f), CornerRadius(6f))
                }
                drawOps(sheet.content, palette, left, right, density)
                cursorIndex?.let(buffer::slotFor)?.let { slot ->
                    drawRoundRect(edgeColor, Offset(slot.x, 2f), Size(3f, buffer.contentHeight - 4f), CornerRadius(1.5f))
                }
            }
        }
    }
}

/**
 * Two-finger pinch on the Initial pass, so the strip's scrollable doesn't
 * also drag: [onPinch] with the scale so far and the focus x where the second
 * finger landed, [onEnd] when the fingers lift.
 */
private suspend fun PointerInputScope.detectPinch(
    onPinch: (scale: Float, focusX: Float) -> Unit,
    onEnd: (scale: Float, focusX: Float) -> Unit,
) {
    awaitEachGesture {
        awaitFirstDown(requireUnconsumed = false, pass = PointerEventPass.Initial)
        var scale = 1f
        var focus = 0f
        var zooming = false
        while (true) {
            val event = awaitPointerEvent(PointerEventPass.Initial)
            val pressed = event.changes.count { it.pressed }
            if (pressed == 0) break
            if (pressed >= 2) {
                if (!zooming) {
                    zooming = true
                    focus = event.calculateCentroid().x
                }
                scale *= event.calculateZoom()
                onPinch(scale, focus)
            }
            if (zooming) event.changes.forEach { it.consume() }
        }
        if (zooming) onEnd(scale, focus)
    }
}

/**
 * Debug-build frame stats for the strip: draw time per frame and the interval
 * between drawn frames, logged every 120 frames (`adb logcat -s CNChordSheet`).
 */
private class FramePerf(private val enabled: Boolean) {
    private val draws = FloatArray(WINDOW)
    private val intervals = FloatArray(WINDOW)
    private var n = 0
    private var lastFrame = 0L

    inline fun frame(block: () -> Unit) {
        if (!enabled) return block()
        val start = System.nanoTime()
        block()
        record(start, System.nanoTime())
    }

    fun record(start: Long, end: Long) {
        val gap = if (lastFrame == 0L) 0f else (start - lastFrame) / 1e6f
        lastFrame = start
        // A pause longer than 100 ms starts a new burst (scroll/fling).
        if (gap > 100f || gap == 0f) return
        draws[n] = (end - start) / 1e6f
        intervals[n] = gap
        if (++n == WINDOW) {
            val d = draws.sorted()
            val i = intervals.sorted()
            Log.i(
                TAG,
                "frames=$WINDOW draw avg=%.2f p95=%.2f max=%.2f ms; interval avg=%.1f p95=%.1f max=%.1f ms".format(
                    d.average(), d[(WINDOW * 0.95).toInt()], d.last(), i.average(), i[(WINDOW * 0.95).toInt()], i.last(),
                ),
            )
            n = 0
        }
    }

    companion object {
        const val WINDOW = 120
    }
}

@Composable
private fun rememberFramePerf(): FramePerf {
    val context = LocalContext.current
    return remember {
        FramePerf((context.applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE) != 0)
    }
}
