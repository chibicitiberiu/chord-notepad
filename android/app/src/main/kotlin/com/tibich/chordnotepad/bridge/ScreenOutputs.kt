package com.tibich.chordnotepad.bridge

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

// The M5 screens' outputs: chord identifier, Settings (values and the
// voicings editor), Quick Start. Mirrors src/session/state.py and events.py;
// see the docstrings there. Fields typed `json` in bridge_schema.json are
// plain JSON objects here ([JsonObject]).

/** A note selected in the chord identifier (C4 = MIDI 60). */
@Serializable
data class IdentifierNote(val name: String, val octave: Int, val midi: Int)

/**
 * The chord identifier. [notesText] is what the typed-notes field shows after
 * a key toggle (don't overwrite the field while the user types there);
 * [message] replaces the candidate list when there are none. [sounding] are
 * the MIDI notes played last (a candidate or Play), to highlight for
 * [soundingSeconds]; a new [soundingToken] restarts that timer, and
 * [soundingBelow]/[soundingAbove] mark notes off either end of the piano.
 * Every name is spelled in [notation], the open song's (`american` or
 * `european`), and the piano labels its keys in it.
 */
@Serializable
data class IdentifierState(
    val notes: List<IdentifierNote>,
    @SerialName("notes_text") val notesText: String,
    @SerialName("typed_text_error") val typedTextError: String? = null,
    val candidates: List<String>,
    val message: String? = null,
    val sounding: List<Int> = emptyList(),
    @SerialName("sounding_token") val soundingToken: Int = 0,
    @SerialName("sounding_seconds") val soundingSeconds: Double = 3.0,
    @SerialName("sounding_below") val soundingBelow: String? = null,
    @SerialName("sounding_above") val soundingAbove: String? = null,
    val notation: String = "american",
) : SessionState

/** The settings Android shows (General and Playback); `commit_settings`/`apply_settings` take it back. */
@Serializable
data class SettingsValues(
    @SerialName("font_family") val fontFamily: String,
    @SerialName("font_size") val fontSize: Int,
    val notation: String,
    /** "" for no key. */
    val key: String,
    @SerialName("show_quick_start_on_startup") val showQuickStartOnStartup: Boolean,
    @SerialName("max_recent_files") val maxRecentFiles: Int,
    val bpm: Int,
    @SerialName("time_signature_beats") val timeSignatureBeats: Int,
    @SerialName("time_signature_unit") val timeSignatureUnit: Int,
)

/** The current settings (re-sent whenever the config changes) and their limits. */
@Serializable
data class SettingsState(
    val values: SettingsValues,
    @SerialName("american_keys") val americanKeys: List<String>,
    @SerialName("european_keys") val europeanKeys: List<String>,
    @SerialName("font_size_min") val fontSizeMin: Int,
    @SerialName("font_size_max") val fontSizeMax: Int,
    @SerialName("bpm_min") val bpmMin: Int,
    @SerialName("bpm_max") val bpmMax: Int,
    @SerialName("max_recent_files_max") val maxRecentFilesMax: Int,
    @SerialName("time_signature_units") val timeSignatureUnits: List<Int>,
) : SessionState

/** One model's voicings in the editor's list. */
@Serializable
data class VoicingGroup(val model: String, val label: String, val names: List<String>)

/** A "Load config" entry; send [group] and [label] to `load_voicing_preset`. */
@Serializable
data class VoicingPreset(val label: String, val group: String)

/**
 * A voicing value that isn't saved because it's wrong; [text] says where it
 * is, what was typed, what's wrong and the field's syntax or range. [fieldId]
 * is null for the voicing as a whole.
 */
@Serializable
data class SettingsProblem(
    val voicing: String,
    @SerialName("field_id") val fieldId: String? = null,
    val text: String,
)

/**
 * The voicings editor of an open settings edit (`begin_settings_edit`).
 * [values], [fieldErrors] and [hints] are keyed by the form schema's field
 * ids (`voice:<i>:<column>` for a records cell in [fieldErrors]).
 * [problems]: every wrong voicing value; [stagedNumbers]: number fields'
 * wrong texts as Python keeps them; [restored]: the edit opened with wrong
 * values kept from last time.
 */
@Serializable
data class VoicingEditorState(
    val active: Boolean,
    val revision: Int,
    val groups: List<VoicingGroup>,
    val invalid: List<String>,
    val presets: List<VoicingPreset>,
    val selected: String? = null,
    val model: String? = null,
    val values: JsonObject,
    @SerialName("field_errors") val fieldErrors: JsonObject,
    @SerialName("form_errors") val formErrors: List<String>,
    val hints: JsonObject,
    val dirty: Boolean,
    val problems: List<SettingsProblem> = emptyList(),
    @SerialName("staged_numbers") val stagedNumbers: Map<String, String> = emptyMap(),
    val restored: Boolean = false,
) : SessionState

/** The voicings editor's form schemas (`settings_forms.voicing_form.editor_schema`); keep it. */
@Serializable
data class VoicingEditorSchema(val version: Int, val schema: JsonObject) : SessionEvent

/** One Quick Start block: `text`, `snippet` (with highlight [spans]) or `image`. */
@Serializable
data class QuickStartBlock(
    val kind: String,
    val text: String,
    val notation: String? = null,
    val spans: List<Span>,
    val image: String? = null,
)

/** A Quick Start page. */
@Serializable
data class QuickStartPage(val title: String, val blocks: List<QuickStartBlock>)

/** The Quick Start tour (`request_quick_start`), worded for Android. */
@Serializable
data class QuickStartContent(
    val pages: List<QuickStartPage>,
    @SerialName("show_on_startup") val showOnStartup: Boolean,
) : SessionEvent

/**
 * The live check of an Insert dialog's fields (`check_directive`). [fields]
 * echoes what was checked, so a late reply can be told from the current one.
 * [errors] maps a field to its message; [formError] is a problem about none.
 */
@Serializable
data class DirectiveCheck(
    val kind: String,
    @SerialName("request_id") val requestId: Int,
    val fields: Map<String, String>,
    val errors: Map<String, String>,
    @SerialName("form_error") val formError: String,
) : SessionEvent

/**
 * The directive at a text offset, or one being typed there
 * (`request_directive_hint`): its range, [keyword] as typed, the correct
 * [syntax] (one line per directive a half-typed keyword could become) and,
 * when invalid or without effect, the [message] saying why. [redundant]
 * marks a valid directive that has no effect. [syntax] is "" when there is
 * no directive at [offset].
 */
@Serializable
data class DirectiveHint(
    val offset: Int,
    val start: Int,
    val end: Int,
    val keyword: String,
    val syntax: String,
    val message: String,
    val redundant: Boolean = false,
) : SessionEvent

/** Wire type name → serializer for the M5 outputs ([BridgeCodec.serializers] includes them). */
internal val screenSerializers: Map<String, KSerializer<out SessionOutput>> = mapOf(
    "IdentifierState" to IdentifierState.serializer(),
    "SettingsState" to SettingsState.serializer(),
    "VoicingEditorState" to VoicingEditorState.serializer(),
    "VoicingEditorSchema" to VoicingEditorSchema.serializer(),
    "QuickStartContent" to QuickStartContent.serializer(),
    "DirectiveCheck" to DirectiveCheck.serializer(),
    "DirectiveHint" to DirectiveHint.serializer(),
)
