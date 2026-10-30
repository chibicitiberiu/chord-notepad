package io.github.chibicitiberiu.chordnotepad.bridge

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// Mirrors src/session/events.py. See the docstrings there for the semantics.

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

/** How a view folds a [TextEdited] into its undo history. */
@Serializable
enum class UndoPolicy {
    /** One undo step on its own (transpose, capo). */
    @SerialName("group") GROUP,
    /** Like any edit (convert notation, inserts, New). */
    @SerialName("plain") PLAIN,
    /** The history starts over (a document was opened). */
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
) : SessionEvent

/** Ask for a directive's fields; answer with a `{field: value}` map of strings or null. */
@Serializable
data class InsertDirectiveRequest(
    @SerialName("request_id") override val requestId: Int,
    /** `bpm`, `time`, `key`, `label` or `loop`. */
    val kind: String,
    @SerialName("existing_labels") val existingLabels: List<String>,
    val notation: String,
) : SessionRequest

/** Ask which fretboard voicing a capo suggestion optimizes for; answer with a value or null. */
@Serializable
data class CapoChoiceRequest(
    @SerialName("request_id") override val requestId: Int,
    val options: List<MenuItem>,
    val default: String,
    /** One line on where the capo goes: the selected part only, or the whole song. */
    val scope: String = "",
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
}

/** Ask the user to pick a document; answer with a [DocumentRef] or null. */
@Serializable
data class PickDocumentRequest(
    @SerialName("request_id") override val requestId: Int,
    val mode: PickMode,
    /** Pre-filled name when saving or exporting; empty when opening. */
    @SerialName("suggested_name") val suggestedName: String,
) : SessionRequest

/** The app may close now; the view tears itself down. */
@Serializable
data object CloseApproved : SessionEvent
