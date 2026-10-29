package io.github.chibicitiberiu.chordnotepad.bridge

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// The Edit/Play redesign's outputs (docs/design/android-ui-spec.md; contract in
// docs/ANDROID.md, "Bridge contract", "Edit/Play redesign"). Mirrors
// src/session/state.py and events.py; see the docstrings there. The playhead
// itself is PlaybackState.playheadOffset and ChordSheetState.cursorIndex.

/**
 * One value the song starts with.
 *
 * @property value `"90"`, `"3/4"`, `"G"`; `""` for a key nobody sets.
 * @property fromDirective A directive before the first chord sets it: show it
 *   read-only ("Set by … in the song · Edit").
 * @property directiveOffset Where that directive starts (code points), for
 *   Edit to put the cursor there; null when not [fromDirective].
 */
@Serializable
data class SongDefault(
    val value: String,
    @SerialName("from_directive") val fromDirective: Boolean,
    @SerialName("directive_offset") val directiveOffset: Int? = null,
)

/**
 * What the song starts with: the Song defaults sheet. [summary] is the
 * pill's text (`"90 · 3/4 · G"`). Values not [SongDefault.fromDirective] are
 * the toolbar defaults (`setBpm`, `setTimeSignature`, `setKey`);
 * `writeSongDefaults` writes them into the song.
 */
@Serializable
data class SongDefaultsState(
    val tempo: SongDefault,
    val time: SongDefault,
    val key: SongDefault,
    val summary: String,
) : SessionState

/**
 * `rename_document` failed. [name] is what the user typed. With [canSaveAs]
 * the storage refused (offer Save As under [name] with `saveAs(name)`);
 * without it the name itself is invalid (keep the dialog open, show [reason]).
 */
@Serializable
data class RenameFailed(
    val name: String,
    val reason: String,
    @SerialName("can_save_as") val canSaveAs: Boolean,
) : SessionEvent

/** Wire type name → serializer for these outputs ([BridgeCodec.serializers] includes them). */
internal val playerSerializers: Map<String, KSerializer<out SessionOutput>> = mapOf(
    "SongDefaultsState" to SongDefaultsState.serializer(),
    "RenameFailed" to RenameFailed.serializer(),
)
