package com.tibich.chordnotepad.bridge

import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonObjectBuilder
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.put

/** The M5 screens' command names (`AppSession` methods; docs/ANDROID.md, "Bridge contract"). */
object ScreenCommandNames {
    // chord identifier
    const val IDENTIFIER_TOGGLE_NOTE = "identifier_toggle_note"
    const val IDENTIFIER_SET_NOTES_TEXT = "identifier_set_notes_text"
    const val IDENTIFIER_CLEAR = "identifier_clear"
    const val PLAY_NOTE = "play_note"
    const val PLAY_IDENTIFIED_CHORD = "play_identified_chord"
    const val INSERT_CHORD = "insert_chord"
    // settings and Quick Start
    const val APPLY_SETTINGS = "apply_settings"
    const val SET_SHOW_QUICK_START_ON_STARTUP = "set_show_quick_start_on_startup"
    const val REQUEST_QUICK_START = "request_quick_start"
    const val BEGIN_SETTINGS_EDIT = "begin_settings_edit"
    const val CANCEL_SETTINGS_EDIT = "cancel_settings_edit"
    const val SAVE_SETTINGS = "save_settings"
    // voicings editor
    const val REQUEST_VOICING_EDITOR_SCHEMA = "request_voicing_editor_schema"
    const val SELECT_VOICING = "select_voicing"
    const val ADD_VOICING = "add_voicing"
    const val REMOVE_VOICING = "remove_voicing"
    const val RENAME_VOICING = "rename_voicing"
    const val SET_VOICING_VALUES = "set_voicing_values"
    const val SET_VOICING_MODEL = "set_voicing_model"
    const val ADD_VOICING_RECORD = "add_voicing_record"
    const val REMOVE_VOICING_RECORD = "remove_voicing_record"
    const val LOAD_VOICING_PRESET = "load_voicing_preset"

    /** Every command these builders send (the contract test checks Python knows them all). */
    val ALL: Set<String> = setOf(
        IDENTIFIER_TOGGLE_NOTE, IDENTIFIER_SET_NOTES_TEXT, IDENTIFIER_CLEAR, PLAY_NOTE,
        PLAY_IDENTIFIED_CHORD, INSERT_CHORD, APPLY_SETTINGS, SET_SHOW_QUICK_START_ON_STARTUP,
        REQUEST_QUICK_START, BEGIN_SETTINGS_EDIT, CANCEL_SETTINGS_EDIT, SAVE_SETTINGS,
        REQUEST_VOICING_EDITOR_SCHEMA, SELECT_VOICING, ADD_VOICING, REMOVE_VOICING,
        RENAME_VOICING, SET_VOICING_VALUES, SET_VOICING_MODEL, ADD_VOICING_RECORD,
        REMOVE_VOICING_RECORD, LOAD_VOICING_PRESET,
    )
}

/**
 * Typed builders for the M5 screens' commands (chord identifier, Settings
 * with the voicings editor, Quick Start). Offsets are code points.
 */
class ScreenCommands(private val submitter: CommandSubmitter) {
    private fun send(command: String, args: JsonObjectBuilder.() -> Unit = {}) {
        submitter.submit(command, buildJsonObject(args).toString())
    }

    // -- chord identifier ---------------------------------------------------------

    /** Tap on a piano key: select or deselect it; a newly selected key sounds. */
    fun identifierToggleNote(note: String, octave: Int) = send(ScreenCommandNames.IDENTIFIER_TOGGLE_NOTE) {
        put("note", note)
        put("octave", octave)
    }

    /** The typed-notes field changed (`"C E G"`, `"C4, E4, G4"`). */
    fun identifierSetNotesText(text: String) = send(ScreenCommandNames.IDENTIFIER_SET_NOTES_TEXT) {
        put("text", text)
    }

    /** Deselect every note (Clear; also when the screen opens). */
    fun identifierClear() = send(ScreenCommandNames.IDENTIFIER_CLEAR)

    /** Long-press on a key: sound it without selecting it. */
    fun playNote(note: String, octave: Int) = send(ScreenCommandNames.PLAY_NOTE) {
        put("note", note)
        put("octave", octave)
    }

    /** Sound a candidate chord. */
    fun playIdentifiedChord(chord: String) = send(ScreenCommandNames.PLAY_IDENTIFIED_CHORD) { put("chord", chord) }

    /** Insert [chord] and a space at code point [at]. */
    fun insertChord(at: Int, chord: String) = send(ScreenCommandNames.INSERT_CHORD) {
        put("at", at)
        put("chord", chord)
    }

    // -- settings and Quick Start ---------------------------------------------------

    /** Write and apply new General/Playback settings at once (no voicings edit needed). */
    fun applySettings(values: SettingsValues) = send(ScreenCommandNames.APPLY_SETTINGS) {
        put("changes", BridgeCodec.json.encodeToJsonElement(values))
    }

    /** Quick Start's "Don't show this again" (false) or its opposite. */
    fun setShowQuickStartOnStartup(show: Boolean) = send(ScreenCommandNames.SET_SHOW_QUICK_START_ON_STARTUP) {
        put("show", show)
    }

    /** Ask for the tour (`QuickStartContent`). */
    fun requestQuickStart() = send(ScreenCommandNames.REQUEST_QUICK_START)

    /** Open a settings working copy (the Settings screen opened). */
    fun beginSettingsEdit() = send(ScreenCommandNames.BEGIN_SETTINGS_EDIT)

    /** Drop the working copy (Cancel / back without saving). */
    fun cancelSettingsEdit() = send(ScreenCommandNames.CANCEL_SETTINGS_EDIT)

    /** Save: validates every voicing, then writes and applies; null keeps the General/Playback values. */
    fun saveSettings(values: SettingsValues?) = send(ScreenCommandNames.SAVE_SETTINGS) {
        put("values", values?.let { BridgeCodec.json.encodeToJsonElement(it) } ?: JsonNull)
    }

    // -- voicings editor --------------------------------------------------------------

    /** Ask for the form schemas (`VoicingEditorSchema`); once per process is enough. */
    fun requestVoicingEditorSchema() = send(ScreenCommandNames.REQUEST_VOICING_EDITOR_SCHEMA)

    /** Show voicing [name] in the form. */
    fun selectVoicing(name: String) = send(ScreenCommandNames.SELECT_VOICING) { put("name", name) }

    /** Add a voicing and select it. */
    fun addVoicing() = send(ScreenCommandNames.ADD_VOICING)

    /** Remove a voicing (confirm first with the schema's `remove_confirm` text). */
    fun removeVoicing(name: String) = send(ScreenCommandNames.REMOVE_VOICING) { put("name", name) }

    /** Rename a voicing; a refused name comes back as a `UserError`. */
    fun renameVoicing(old: String, new: String) = send(ScreenCommandNames.RENAME_VOICING) {
        put("old", old)
        put("new", new)
    }

    /** Form edits: the changed fields (or all), keyed by field id. */
    fun setVoicingValues(values: JsonObject) = send(ScreenCommandNames.SET_VOICING_VALUES) { put("values", values) }

    /** Switch the selected voicing's model (confirm first when `dirty`). */
    fun setVoicingModel(model: String) = send(ScreenCommandNames.SET_VOICING_MODEL) { put("model", model) }

    /** Add a row to a records field. */
    fun addVoicingRecord(fieldId: String = "voices") = send(ScreenCommandNames.ADD_VOICING_RECORD) {
        put("field_id", fieldId)
    }

    /** Remove row [index] of a records field. */
    fun removeVoicingRecord(index: Int, fieldId: String = "voices") = send(ScreenCommandNames.REMOVE_VOICING_RECORD) {
        put("index", index)
        put("field_id", fieldId)
    }

    /** Load a "Load config" entry into the selected voicing (confirm first). */
    fun loadVoicingPreset(preset: VoicingPreset) = send(ScreenCommandNames.LOAD_VOICING_PRESET) {
        put("group", preset.group)
        put("label", preset.label)
    }
}
