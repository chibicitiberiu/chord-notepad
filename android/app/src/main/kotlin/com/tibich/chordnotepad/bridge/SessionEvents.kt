package com.tibich.chordnotepad.bridge

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// Mirrors core/chordnotepad/session/events.py. See the docstrings there for the semantics.

/** Something the user asked for failed in an expected way. */
@Serializable
data class UserError(val title: String, val message: String) : SessionError

/** Audio couldn't start; the session already applied the once-per-session policy for taps. */
@Serializable
data class AudioUnavailable(
    val message: String,
    @SerialName("from_click") val fromClick: Boolean,
) : SessionError

/** A bug: an exception nobody handled (Python's Android error handler, or a bridge failure). */
@Serializable
data class UnexpectedError(val message: String, val context: String? = null) : SessionError

/**
 * An edit was refused because a song is playing or paused. Android stops the
 * song before it edits, so it never sees one; the Qt desktop shows [message].
 */
@Serializable
data class EditRefused(val message: String) : SessionEvent

/** How a view folds a [TextEdited] into its undo history. */
@Serializable
enum class UndoPolicy {
    /** One undo step on its own (transpose, capo). */
    @SerialName("group") GROUP,
    /** Like any edit (convert notation, inserts). */
    @SerialName("plain") PLAIN,
    /** The history starts over (a document was opened, or New). */
    @SerialName("reset") RESET,
}

/**
 * The session changed the text; replace `[start, end)` with [replacement] and
 * put the cursor at [cursor] (code points; see text.applyTo). Never report the
 * result back with `set_text`.
 */
@Serializable
data class TextEdited(
    @SerialName("text_revision") val textRevision: Int,
    val start: Int,
    val end: Int,
    val replacement: String,
    val undo: UndoPolicy,
    val cursor: Int,
    /** Select from here to [cursor]; null for none. Only the desktop's palette sets it. */
    val anchor: Int? = null,
) : SessionEvent

/** Ask for a directive's fields; answer with a `{field: value}` map of strings or null. */
@Serializable
data class InsertDirectiveRequest(
    @SerialName("request_id") override val requestId: Int,
    /** `bpm`, `time`, `key`, `label` or `loop`. */
    val kind: String,
    @SerialName("existing_labels") val existingLabels: List<String>,
    val notation: String,
    /** For `key`: the keys to offer (15 major, 15 minor), in [notation]; empty for the other kinds. */
    @SerialName("key_options") val keyOptions: List<String> = emptyList(),
) : SessionRequest

/** The answers to [ConfirmDiscardRequest]. */
@Serializable
enum class DiscardChoice {
    @SerialName("save") SAVE,
    @SerialName("discard") DISCARD,
    @SerialName("cancel") CANCEL,
}

/** Unsaved changes: save before going on? Answer with a [DiscardChoice] or null. */
@Serializable
data class ConfirmDiscardRequest(
    @SerialName("request_id") override val requestId: Int,
) : SessionRequest

/** What a [PickDocumentRequest] picks a document for. */
@Serializable
enum class PickMode {
    @SerialName("open") OPEN,
    @SerialName("save") SAVE,
    @SerialName("export_midi") EXPORT_MIDI,
    @SerialName("export_audio") EXPORT_AUDIO,
    @SerialName("export_pdf") EXPORT_PDF,
}

/** Ask the user to pick a document; answer with a [DocumentRef] or null. */
@Serializable
data class PickDocumentRequest(
    @SerialName("request_id") override val requestId: Int,
    val mode: PickMode,
    /** Pre-filled name when saving or exporting; empty when opening. */
    @SerialName("suggested_name") val suggestedName: String,
) : SessionRequest

/** Text in one colour from [x] (points from the page's left edge) on its line's baseline. */
@Serializable
data class PdfRun(val x: Double, val text: String, val dim: Boolean)

/** One printed line: its baseline [y] (points from the page's top edge) and its runs. */
@Serializable
data class PdfLine(val y: Double, val runs: List<PdfRun>)

/** One page's lines and its centred page number ("1 / 3") from [footerX]. */
@Serializable
data class PdfPage(
    val lines: List<PdfLine>,
    val footer: String,
    @SerialName("footer_x") val footerX: Double,
)

/**
 * A PDF export's pages (`session.print_layout`): sizes in points, every
 * position absolute; the painter adds nothing of its own.
 */
@Serializable
data class PdfLayout(
    @SerialName("page_width") val pageWidth: Double,
    @SerialName("page_height") val pageHeight: Double,
    @SerialName("font_size") val fontSize: Double,
    @SerialName("line_height") val lineHeight: Double,
    @SerialName("small_font_size") val smallFontSize: Double,
    val title: String,
    @SerialName("title_x") val titleX: Double,
    @SerialName("title_y") val titleY: Double,
    @SerialName("footer_y") val footerY: Double,
    @SerialName("page_count") val pageCount: Int,
    val pages: List<PdfPage>,
)

/**
 * Paint [layout] and write it to [ref] (picked just before); answer with ""
 * when written, the reason when not, or null when cancelled or failed.
 */
@Serializable
data class PaintPdfRequest(
    @SerialName("request_id") override val requestId: Int,
    val ref: DocumentRef,
    val layout: PdfLayout,
) : SessionRequest

/** The app may close now; the view tears itself down. */
@Serializable
data object CloseApproved : SessionEvent
