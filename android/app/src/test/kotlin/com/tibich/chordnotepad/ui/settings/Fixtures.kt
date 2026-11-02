package com.tibich.chordnotepad.ui.settings

import com.tibich.chordnotepad.bridge.BridgeCodec
import com.tibich.chordnotepad.bridge.CommandSubmitter
import com.tibich.chordnotepad.bridge.SettingsState
import com.tibich.chordnotepad.bridge.VoicingEditorSchema
import com.tibich.chordnotepad.bridge.VoicingEditorState
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/**
 * The fixtures android/tools/gen_voicing_form_fixtures.py wrote from a real
 * session (`{"type", "json"}`), decoded as the bridge would.
 */
object Fixtures {
    private fun load(name: String): Any {
        val text = Fixtures::class.java.getResourceAsStream("/voicing_form/$name.json")!!
            .bufferedReader().use { it.readText() }
        val root = Json.parseToJsonElement(text).jsonObject
        return BridgeCodec.decode(root.getValue("type").jsonPrimitive.content, root.getValue("json").toString())
    }

    /** The editor schema. */
    val schema: EditorSchema by lazy { EditorSchema.parse((load("schema") as VoicingEditorSchema).schema) }

    /** `SettingsState` at startup (American, key C, 120 BPM, 4/4). */
    val settings: SettingsState by lazy { load("settings") as SettingsState }

    /** "New voicing" (fretboard): tuning "E2 A2 X9 G3" (field error), relaxed span 2 (form error). */
    val fretboardInvalid: VoicingEditorState by lazy { load("fretboard_invalid") as VoicingEditorState }

    /**
     * The same as an ensemble with a third voice moved up (Voice 1, Voice 3,
     * Voice 2): voice 1 low "H9" and gap "0" (cell errors), voice 0 low above
     * high (a rule across fields, blamed on both cells).
     */
    val ensemble: VoicingEditorState by lazy { load("ensemble") as VoicingEditorState }

    /** The same as a piano, untouched. */
    val piano: VoicingEditorState by lazy { load("piano") as VoicingEditorState }
}

/** Records every command sent, with its arguments. */
class RecordingSubmitter : CommandSubmitter {
    val sent = mutableListOf<Pair<String, JsonObject>>()

    override fun submit(command: String, argsJson: String) {
        sent += command to Json.parseToJsonElement(argsJson).jsonObject
    }

    /** The names of the commands sent, in order. */
    val names: List<String> get() = sent.map { it.first }

    /** Forget what was sent. */
    fun clear() = sent.clear()
}
