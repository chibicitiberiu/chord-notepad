package io.github.chibicitiberiu.chordnotepad.bridge

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// Kotlin mirrors of the session's DTOs (src/session/state.py, events.py,
// documents.py). Field names on the wire are the Python dataclass field names
// (snake_case); enums travel as their string values. Offsets are Unicode code
// points; convert them with text.OffsetMapper before touching a Kotlin string.
//
// TODO(step 14): bridge_schema.json from session.bridge is checked against
// these classes by BridgeSchemaContractTest; keep both in step when a DTO changes.

/** Everything the session sends to the view: a [SessionState] or a [SessionEvent]. */
sealed interface SessionOutput

/** A state: coalesced (latest value wins) and replayed to a new listener. */
sealed interface SessionState : SessionOutput

/** A one-off event: delivered in order, never replayed. */
sealed interface SessionEvent : SessionOutput

/** A question for the user; answer it with [SessionCommands.respond]. */
sealed interface SessionRequest : SessionEvent {
    /** Pass back with the answer. */
    val requestId: Int
}

/** A failure to show the user (or, for [UnexpectedError], to report). */
sealed interface SessionError : SessionEvent

/** A document the user picked. [id] is a content URI on Android, opaque to Python. */
@Serializable
data class DocumentRef(
    val id: String,
    @SerialName("display_name") val displayName: String,
    val location: String,
)

/** What a highlighted range of the text is. */
@Serializable
enum class SpanKind {
    @SerialName("chord") CHORD,
    @SerialName("chord_invalid") CHORD_INVALID,
    @SerialName("directive") DIRECTIVE,
    @SerialName("directive_invalid") DIRECTIVE_INVALID,
    @SerialName("comment") COMMENT,
}

/** A highlighted range `[start, end)` of the text, in code points. */
@Serializable
data class Span(val start: Int, val end: Int, val kind: SpanKind)

/** One choice in a menu or list; send [value] back. */
@Serializable
data class MenuItem(val label: String, val value: String)
