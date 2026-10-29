package io.github.chibicitiberiu.chordnotepad.bridge

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// Mirrors src/session/state.py. See the docstrings there for the semantics.

/** The highlight spans for one version of the text. */
@Serializable
data class HighlightState(
    /** The session's revision of the text the spans were computed for. */
    @SerialName("text_revision") val textRevision: Int,
    /** The `set_text` token that produced that text (0 for session edits). */
    @SerialName("client_token") val clientToken: Int,
    /** Comments, then chords, then directives; kinds may overlap. */
    val spans: List<Span>,
) : SessionState

/** Whether a song is playing. */
@Serializable
enum class PlaybackStatus {
    @SerialName("idle") IDLE,
    @SerialName("playing") PLAYING,
    @SerialName("paused") PAUSED,
}

/** Song playback: the transport status and the chord sounding now. */
@Serializable
data class PlaybackState(
    val status: PlaybackStatus,
    /** The chord sounding, in code points of the text playback started from. */
    @SerialName("playing_span") val playingSpan: Span? = null,
    @SerialName("chord_index") val chordIndex: Int? = null,
    /** 1-based; 0 when idle. */
    val bar: Int = 0,
    @SerialName("total_bars") val totalBars: Int = 0,
) : SessionState

/** What the Play/Pause button does when pressed. */
@Serializable
enum class PlayAction {
    @SerialName("play") PLAY,
    @SerialName("pause") PAUSE,
    @SerialName("resume") RESUME,
}

/** The toolbar: notation, tempo, key, time signature, metronome, transport. */
@Serializable
data class ToolbarState(
    val notation: String,
    val bpm: Int,
    @SerialName("bpm_display") val bpmDisplay: Int,
    @SerialName("bpm_editable") val bpmEditable: Boolean,
    @SerialName("multiplier_pct") val multiplierPct: Double,
    val key: String,
    @SerialName("key_options") val keyOptions: List<String>,
    val beats: Int,
    val unit: Int,
    val metronome: Boolean,
    @SerialName("play_action") val playAction: PlayAction,
) : SessionState

/** The status line under the editor. */
@Serializable
data class StatusState(val text: String) : SessionState

/** How the editor looks and behaves. */
@Serializable
data class EditorState(
    @SerialName("font_family") val fontFamily: String,
    @SerialName("font_size") val fontSize: Int,
    /** True while a song plays or is paused. */
    @SerialName("read_only") val readOnly: Boolean,
    val notation: String,
) : SessionState

/** The voicing menu; send a value back with `set_voicing`. */
@Serializable
data class VoicingMenuState(
    val selected: String,
    val groups: List<List<MenuItem>>,
) : SessionState

/** One General MIDI family in the instrument menu; item values are program numbers. */
@Serializable
data class InstrumentFamily(
    val name: String,
    @SerialName("is_current") val isCurrent: Boolean,
    val items: List<MenuItem>,
)

/** The instrument menu; send a program with `set_instrument`. */
@Serializable
data class InstrumentMenuState(
    val current: Int,
    val families: List<InstrumentFamily>,
) : SessionState

/** One of the chord sheet's views (keyboard, staff, chord boxes, tab). */
@Serializable
data class ChordSheetView(
    @SerialName("view_id") val viewId: String,
    val label: String,
    val available: Boolean,
)

/** The chord-sheet strip under the editor. */
@Serializable
data class ChordSheetState(
    val visible: Boolean,
    val height: Int,
    @SerialName("active_view") val activeView: String,
    val views: List<ChordSheetView>,
    @SerialName("disabled_reason") val disabledReason: String? = null,
    val zoom: Double,
    @SerialName("zoom_supported") val zoomSupported: Boolean,
    @SerialName("current_index") val currentIndex: Int? = null,
    @SerialName("song_revision") val songRevision: Int,
) : SessionState

/** The open document, for the title and the Save As suggestion. */
@Serializable
data class DocumentState(
    @SerialName("display_name") val displayName: String,
    val location: String? = null,
    @SerialName("is_modified") val isModified: Boolean,
    val title: String,
    /**
     * The open document's [DocumentRef.id], or null for a never-saved one.
     * Not in state.py yet: step 14 adds it (the draft restore needs it).
     */
    @SerialName("document_id") val documentId: String? = null,
) : SessionState

/** Recently opened or saved documents, newest first; send one back with `open_recent`. */
@Serializable
data class RecentDocumentsState(val items: List<DocumentRef>) : SessionState
