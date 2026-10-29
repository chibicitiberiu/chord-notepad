package io.github.chibicitiberiu.chordnotepad.ui.chordsheet

import android.os.SystemClock
import android.util.Log
import androidx.compose.foundation.gestures.ScrollableState
import androidx.compose.foundation.gestures.animateScrollBy
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import io.github.chibicitiberiu.chordnotepad.bridge.ChordSheetState
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.debounce
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.withContext

private const val TAG = "CNChordSheet"

/** Where the strip's op buffers come from: `PyHost.chordSheetBuffer` in the app. */
fun interface ChordSheetBufferSource {
    /** The active view packed for a strip [heightDp] tall, or null without a song. Never called on Main by Compose code. */
    suspend fun fetch(heightDp: Float): ByteArray?
}

/**
 * What a buffer depends on: a new one is fetched whenever this changes
 * (docs/ANDROID.md: song revision, view, zoom, height; never on scroll).
 */
data class SheetRequest(val songRevision: Int, val viewId: String, val zoom: Double, val heightDp: Int) {
    companion object {
        /** The request for [state] and a strip [heightDp] tall, or null when nothing should be fetched. */
        fun of(state: ChordSheetState?, heightDp: Int): SheetRequest? =
            if (state == null || !state.visible || heightDp <= 0) null
            else SheetRequest(state.songRevision, state.activeView, state.zoom, heightDp)
    }
}

/**
 * Fetches, decodes and caches the strip's buffer. Compose state; [follow]
 * runs in the pane's composition scope (Main), the bridge call on the bridge
 * thread (inside [source]) and decoding on [decodeDispatcher], followed by
 * [prepare] (glyph preloading) on the same dispatcher.
 */
@Stable
class ChordSheetController(
    private val source: ChordSheetBufferSource,
    private val prepare: (PreparedSheet) -> Unit = {},
    private val decodeDispatcher: CoroutineDispatcher = Dispatchers.Default,
) {
    /** The last sheet decoded, kept until a newer one is ready; null without a song. */
    var sheet: PreparedSheet? by mutableStateOf(null)
        private set

    /** Why the last buffer couldn't be shown (an unsupported version), or null. */
    var failure: String? by mutableStateOf(null)
        private set

    /** The request [sheet] answers. */
    var loaded: SheetRequest? by mutableStateOf(null)
        private set

    /** The newest request [follow] has seen (loaded or not yet). */
    private var requested: SheetRequest? by mutableStateOf(null)

    /** True while a buffer is being fetched or decoded for the newest request (the pane shows a progress bar). */
    val loading: Boolean get() = requested.let { it != null && it != loaded && failure == null }

    /**
     * Fetch a buffer for each distinct request. A newer request cancels the
     * wait for an older one; height changes during a split drag settle first.
     */
    @OptIn(FlowPreview::class)
    suspend fun follow(requests: Flow<SheetRequest?>) {
        requests.distinctUntilChanged().onEach { requested = it }.debounce(SETTLE_MS).collectLatest { request ->
            if (request != null) load(request)
        }
    }

    private suspend fun load(request: SheetRequest) {
        val start = SystemClock.elapsedRealtimeNanos()
        val bytes = source.fetch(request.heightDp.toFloat())
        val fetched = SystemClock.elapsedRealtimeNanos()
        if (bytes == null) {
            sheet = null
            loaded = request
            Log.i(TAG, "fetch $request: no song (${ms(fetched - start)} ms)")
            return
        }
        try {
            val (prepared, decodeNs) = withContext(decodeDispatcher) {
                val t0 = SystemClock.elapsedRealtimeNanos()
                val buffer = ChordSheetBuffer.decode(bytes)
                val t1 = SystemClock.elapsedRealtimeNanos()
                val p = PreparedSheet(buffer)
                prepare(p)
                p to (t1 - t0)
            }
            val done = SystemClock.elapsedRealtimeNanos()
            Log.i(
                TAG,
                "fetch ${request.viewId} z=${request.zoom} h=${request.heightDp}: ${bytes.size} B, " +
                    "${prepared.buffer.content.size}+${prepared.buffer.lane.size} ops, " +
                    "fetch ${ms(fetched - start)} ms, decode ${ms(decodeNs)} ms, " +
                    "prepare ${ms(done - fetched - decodeNs)} ms",
            )
            failure = null
            loaded = request
            sheet = prepared
        } catch (e: UnsupportedChordSheetVersion) {
            Log.e(TAG, "Chord sheet buffer version ${e.version} not supported", e)
            failure = "This chord sheet needs a newer version of the app."
            loaded = request
            sheet = null
        } catch (e: ChordSheetFormatException) {
            Log.e(TAG, "Malformed chord sheet buffer", e)
            failure = "The chord sheet couldn't be drawn."
            loaded = request
            sheet = null
        }
    }

    private companion object {
        const val SETTLE_MS = 60L

        fun ms(ns: Long) = "%.1f".format(ns / 1e6)
    }
}

/**
 * The strip's horizontal scroll, in pixels. A plain [ScrollableState] whose
 * offset the draw phase reads, so scrolling redraws without recomposing.
 */
@Stable
class StripScroll {
    private var offsetState = mutableFloatStateOf(0f)

    /** Scroll offset in px (content x at the viewport's left edge × density). */
    val offset: Float get() = offsetState.floatValue

    /** The largest offset (content width − viewport width, in px). */
    var max: Float = 0f
        set(value) {
            field = value.coerceAtLeast(0f)
            if (offsetState.floatValue > field) offsetState.floatValue = field
        }

    /** For `Modifier.scrollable(..., reverseDirection = true)`: a positive delta scrolls right. */
    val scrollable = ScrollableState { delta ->
        val old = offsetState.floatValue
        val new = (old + delta).coerceIn(0f, max)
        offsetState.floatValue = new
        new - old
    }

    /** Jump to [px] (clamped). */
    fun snapTo(px: Float) {
        offsetState.floatValue = px.coerceIn(0f, max)
    }

    /** Animate to [px] (clamped); cancels a fling in progress. */
    suspend fun animateTo(px: Float) {
        scrollable.animateScrollBy(px.coerceIn(0f, max) - offset)
    }
}
