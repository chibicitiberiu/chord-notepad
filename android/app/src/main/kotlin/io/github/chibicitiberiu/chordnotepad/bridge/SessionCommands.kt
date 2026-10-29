package io.github.chibicitiberiu.chordnotepad.bridge

import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObjectBuilder
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.put

/**
 * The command names Kotlin submits. Session commands are `AppSession` method
 * names, with the JSON object's keys as keyword arguments; host commands are
 * handled by `chordnotepad_android.host` itself (docs/ANDROID.md, "Bridge
 * contract").
 */
object CommandNames {
    // AppSession: editing
    const val SET_TEXT = "set_text"
    const val INSERT_TEXT = "insert_text"
    const val REQUEST_INSERT_DIRECTIVE = "request_insert_directive"
    const val CHECK_DIRECTIVE = "check_directive"
    const val TRANSPOSE = "transpose"
    const val REQUEST_SUGGEST_CAPO = "request_suggest_capo"
    const val CONVERT_NOTATION = "convert_notation"
    // AppSession: playback and toolbar
    const val PLAY_PAUSE = "play_pause"
    const val STOP = "stop"
    const val TAP_CHORD_AT = "tap_chord_at"
    const val SET_BPM = "set_bpm"
    const val SET_MULTIPLIER_PCT = "set_multiplier_pct"
    const val SET_BPM_TEXT = "set_bpm_text"
    const val SET_MULTIPLIER_TEXT = "set_multiplier_text"
    const val RESET_BPM = "reset_bpm"
    const val RESET_MULTIPLIER = "reset_multiplier"
    const val SET_KEY = "set_key"
    const val SET_TIME_SIGNATURE = "set_time_signature"
    const val TOGGLE_METRONOME = "toggle_metronome"
    const val SET_VOICING = "set_voicing"
    const val SET_INSTRUMENT = "set_instrument"
    const val SET_NOTATION = "set_notation"
    const val SET_FONT = "set_font"
    const val STEP_FONT_SIZE = "step_font_size"
    const val RESET_FONT_SIZE = "reset_font_size"
    // AppSession: chord sheet
    const val SET_CHORD_SHEET_VISIBLE = "set_chord_sheet_visible"
    const val SET_CHORD_SHEET_HEIGHT = "set_chord_sheet_height"
    const val SET_CHORD_SHEET_VIEW = "set_chord_sheet_view"
    const val CHORD_SHEET_ZOOM = "chord_sheet_zoom"
    const val AUDITION = "audition"
    // AppSession: documents and requests
    const val NEW_DOCUMENT = "new_document"
    const val OPEN_DOCUMENT = "open_document"
    const val OPEN_RECENT = "open_recent"
    const val SAVE = "save"
    const val SAVE_AS = "save_as"
    const val EXPORT_MIDI = "export_midi"
    const val REQUEST_CLOSE = "request_close"
    const val RESPOND = "respond"
    // Host (Android lifecycle), handled in chordnotepad_android.host
    const val APP_BACKGROUND = "app_background"
    const val APP_FOREGROUND = "app_foreground"
    const val PAUSE = "pause"
    const val RESTORE_DRAFT = "restore_draft"

    /** Every command Kotlin may submit (the contract test checks Python knows them all). */
    val ALL: Set<String> = setOf(
        SET_TEXT, INSERT_TEXT, REQUEST_INSERT_DIRECTIVE, CHECK_DIRECTIVE, TRANSPOSE, REQUEST_SUGGEST_CAPO,
        CONVERT_NOTATION, PLAY_PAUSE, STOP, TAP_CHORD_AT, SET_BPM, SET_MULTIPLIER_PCT,
        SET_BPM_TEXT, SET_MULTIPLIER_TEXT, RESET_BPM, RESET_MULTIPLIER,
        SET_KEY, SET_TIME_SIGNATURE, TOGGLE_METRONOME, SET_VOICING, SET_INSTRUMENT,
        SET_NOTATION, SET_FONT, STEP_FONT_SIZE, RESET_FONT_SIZE, SET_CHORD_SHEET_VISIBLE,
        SET_CHORD_SHEET_HEIGHT, SET_CHORD_SHEET_VIEW, CHORD_SHEET_ZOOM, AUDITION,
        NEW_DOCUMENT, OPEN_DOCUMENT, OPEN_RECENT, SAVE, SAVE_AS, EXPORT_MIDI,
        REQUEST_CLOSE, RESPOND, APP_BACKGROUND, APP_FOREGROUND, PAUSE, RESTORE_DRAFT,
    )
}

/** A selected range `[start, end)` in code points; an empty one means none. */
data class Selection(val start: Int, val end: Int)

/** Sends a command; [PyHost.submit] in the app. Must not block. */
fun interface CommandSubmitter {
    /** Queue [command] with its keyword arguments as a JSON object. */
    fun submit(command: String, argsJson: String)
}

/**
 * Typed builders for every command. All offsets are Unicode code points of
 * the session's text (convert with text.OffsetMapper); a selection is a
 * code-point `(start, end)` pair, or null for none.
 *
 * @param onResponded Told which request was answered, so the repository can
 *   drop it from `pendingRequest`.
 */
class SessionCommands(
    private val submitter: CommandSubmitter,
    private val onResponded: (requestId: Int) -> Unit = {},
) {
    private fun send(command: String, args: JsonObjectBuilder.() -> Unit = {}) {
        submitter.submit(command, buildJsonObject(args).toString())
    }

    // -- editing ------------------------------------------------------------

    /** The editor's whole text after a user edit; [clientToken] comes back in `HighlightState`. */
    fun setText(text: String, clientToken: Int) = send(CommandNames.SET_TEXT) {
        put("text", text)
        put("client_token", clientToken)
    }

    /** Insert [text] at code point [at] (a programmatic edit; comes back as `TextEdited`). */
    fun insertText(at: Int, text: String) = send(CommandNames.INSERT_TEXT) {
        put("at", at)
        put("text", text)
    }

    /** Ask for an `InsertDirectiveRequest` of [kind] (`bpm`, `time`, `key`, `label`, `loop`) at [at]. */
    fun requestInsertDirective(kind: String, at: Int) = send(CommandNames.REQUEST_INSERT_DIRECTIVE) {
        put("kind", kind)
        put("at", at)
    }

    /** Check an Insert dialog's [fields] (reply: `DirectiveCheck`); the request stays pending. */
    fun checkDirective(kind: String, fields: Map<String, String>, requestId: Int) = send(CommandNames.CHECK_DIRECTIVE) {
        put("kind", kind)
        put("fields", buildJsonObject { fields.forEach { (k, v) -> put(k, v) } })
        put("request_id", requestId)
    }

    /** Transpose the selection (or the whole song when null) by [semitones]. */
    fun transpose(semitones: Int, selection: Selection? = null) = send(CommandNames.TRANSPOSE) {
        put("semitones", semitones)
        put("selection", selection.toJson())
    }

    /** Start Suggest Capo for the selection (or the whole song). */
    fun requestSuggestCapo(selection: Selection? = null) = send(CommandNames.REQUEST_SUGGEST_CAPO) {
        put("selection", selection.toJson())
    }

    /** Convert the song's chords to [target] notation (`american`/`european`). */
    fun convertNotation(target: String) = send(CommandNames.CONVERT_NOTATION) { put("target", target) }

    // -- playback and toolbar -------------------------------------------------

    /** Play, pause or resume; [fromOffset] plays from that code point. */
    fun playPause(fromOffset: Int? = null) = send(CommandNames.PLAY_PAUSE) { put("from_offset", fromOffset) }

    /** Stop playback. */
    fun stop() = send(CommandNames.STOP)

    /** Play the chord at code point [offset], if any. */
    fun tapChordAt(offset: Int) = send(CommandNames.TAP_CHORD_AT) { put("offset", offset) }

    /** Set the base tempo (clamped and snapped by the session). */
    fun setBpm(bpm: Double) = send(CommandNames.SET_BPM) { put("bpm", bpm) }

    /** Set the speed multiplier in percent. */
    fun setMultiplierPct(pct: Double) = send(CommandNames.SET_MULTIPLIER_PCT) { put("pct", pct) }

    /** A typed tempo (`"120"`); Python parses it and ignores text that isn't a number. */
    fun setBpmText(text: String) = send(CommandNames.SET_BPM_TEXT) { put("text", text) }

    /** A typed speed (`"150"`, `"150%"`, `"1.5x"`); Python parses it and ignores anything else. */
    fun setMultiplierText(text: String) = send(CommandNames.SET_MULTIPLIER_TEXT) { put("text", text) }

    /** Back to the default tempo (the desktop scrubber's middle-click). */
    fun resetBpm() = send(CommandNames.RESET_BPM)

    /** Back to 100 % speed (the desktop scrubber's middle-click). */
    fun resetMultiplier() = send(CommandNames.RESET_MULTIPLIER)

    /** Set the key for roman numerals; null clears it. */
    fun setKey(key: String?) = send(CommandNames.SET_KEY) { put("key", key) }

    /** Set the time signature. */
    fun setTimeSignature(beats: Int, unit: Int) = send(CommandNames.SET_TIME_SIGNATURE) {
        put("beats", beats)
        put("unit", unit)
    }

    /** Toggle the metronome click. */
    fun toggleMetronome() = send(CommandNames.TOGGLE_METRONOME)

    /** Choose a voicing (a `VoicingMenuState` item value). */
    fun setVoicing(voicing: String) = send(CommandNames.SET_VOICING) { put("voicing", voicing) }

    /** Choose a General MIDI program (0-127). */
    fun setInstrument(program: Int) = send(CommandNames.SET_INSTRUMENT) { put("program", program) }

    /** Switch detection notation (`american`/`european`). */
    fun setNotation(notation: String) = send(CommandNames.SET_NOTATION) { put("notation", notation) }

    /** Set the editor font. */
    fun setFont(family: String, size: Int) = send(CommandNames.SET_FONT) {
        put("family", family)
        put("size", size)
    }

    /** Grow or shrink the editor font by [delta] points. */
    fun stepFontSize(delta: Int) = send(CommandNames.STEP_FONT_SIZE) { put("delta", delta) }

    /** Back to the configured font size. */
    fun resetFontSize() = send(CommandNames.RESET_FONT_SIZE)

    // -- chord sheet ------------------------------------------------------------

    /** Show or hide the chord sheet. */
    fun setChordSheetVisible(visible: Boolean) = send(CommandNames.SET_CHORD_SHEET_VISIBLE) {
        put("visible", visible)
    }

    /** The chord sheet's height (kept across runs). */
    fun setChordSheetHeight(px: Int) = send(CommandNames.SET_CHORD_SHEET_HEIGHT) { put("px", px) }

    /** Switch the chord sheet's view (a `ChordSheetView.viewId`). */
    fun setChordSheetView(viewId: String) = send(CommandNames.SET_CHORD_SHEET_VIEW) { put("view_id", viewId) }

    /** Zoom the chord sheet [step] steps (positive in; a whole pinch is one command; 0 does nothing). */
    fun chordSheetZoom(step: Int) = send(CommandNames.CHORD_SHEET_ZOOM) { put("step", step) }

    /** Play the chord sheet's chord [index]. */
    fun audition(index: Int) = send(CommandNames.AUDITION) { put("index", index) }

    // -- documents ----------------------------------------------------------------

    /** New document (asks about unsaved changes first). */
    fun newDocument() = send(CommandNames.NEW_DOCUMENT)

    /** Open [ref], or ask with a `PickDocumentRequest` when null. */
    fun openDocument(ref: DocumentRef? = null) = send(CommandNames.OPEN_DOCUMENT) { put("ref", ref.toJson()) }

    /** Open a recent document. */
    fun openRecent(ref: DocumentRef) = send(CommandNames.OPEN_RECENT) { put("ref", ref.toJson()) }

    /** Save (Save As for a never-saved document). */
    fun save() = send(CommandNames.SAVE)

    /** Save under a new name. */
    fun saveAs() = send(CommandNames.SAVE_AS)

    /** Export the song as MIDI. */
    fun exportMidi() = send(CommandNames.EXPORT_MIDI)

    /** Ask to close; the session answers with `CloseApproved` or a request. */
    fun requestClose() = send(CommandNames.REQUEST_CLOSE)

    // -- answers to requests ----------------------------------------------------

    /** Answer a request with a raw JSON [value] (null cancels). Prefer the typed overloads. */
    fun respond(requestId: Int, value: JsonElement) {
        send(CommandNames.RESPOND) {
            put("request_id", requestId)
            put("value", value)
        }
        onResponded(requestId)
    }

    /** Answer a `ConfirmDiscardRequest`; null cancels. */
    fun respondDiscard(requestId: Int, choice: DiscardChoice?) =
        respond(requestId, choice?.let { BridgeCodec.json.encodeToJsonElement(it) } ?: JsonNull)

    /** Answer a `PickDocumentRequest`; null means the user cancelled. */
    fun respondPick(requestId: Int, ref: DocumentRef?) = respond(requestId, ref.toJson())

    /** Answer a `CapoChoiceRequest` with an option's value; null cancels. */
    fun respondCapo(requestId: Int, value: String?) = respond(requestId, JsonPrimitive(value))

    /** Answer an `InsertDirectiveRequest` with its fields; null cancels. */
    fun respondDirective(requestId: Int, fields: Map<String, String>?) = respond(
        requestId,
        fields?.let { f -> buildJsonObject { f.forEach { (k, v) -> put(k, v) } } } ?: JsonNull,
    )

    // -- host (Android lifecycle) -------------------------------------------------

    /** The app went to the background (ON_STOP): pause playback, save the config. */
    fun appBackground() = send(CommandNames.APP_BACKGROUND)

    /** The app came to the foreground (ON_START). */
    fun appForeground() = send(CommandNames.APP_FOREGROUND)

    /** Pause if playing (audio focus loss, headphones unplugged); otherwise nothing. */
    fun pause() = send(CommandNames.PAUSE)

    /**
     * After process death: put back the text the user had, the document it
     * belongs to ([document], null for a never-saved one) and its modified flag.
     */
    fun restoreDraft(text: String, document: DocumentRef?, modified: Boolean) =
        send(CommandNames.RESTORE_DRAFT) {
            put("text", text)
            put("document", document.toJson())
            put("modified", modified)
        }
}

private fun Selection?.toJson(): JsonElement =
    this?.let { buildJsonArray { add(JsonPrimitive(it.start)); add(JsonPrimitive(it.end)) } } ?: JsonNull

private fun DocumentRef?.toJson(): JsonElement =
    this?.let { BridgeCodec.json.encodeToJsonElement(it) } ?: JsonNull
