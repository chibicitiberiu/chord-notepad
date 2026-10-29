package io.github.chibicitiberiu.chordnotepad.bridge

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json

/** A `(type_name, json)` pair from Python that doesn't decode. */
class BridgeDecodeException(message: String, cause: Throwable? = null) : Exception(message, cause)

/**
 * Decodes the session's output from the wire form `session.bridge.encode`
 * produces: the Python class name plus its fields as a JSON object.
 */
object BridgeCodec {
    /**
     * Lenient about extra keys, so a newer core field doesn't crash an older
     * view; the contract test catches real drift.
     */
    val json: Json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    /** Wire type name (the Python class name) → serializer. */
    val serializers: Map<String, KSerializer<out SessionOutput>> = mapOf(
        "HighlightState" to HighlightState.serializer(),
        "PlaybackState" to PlaybackState.serializer(),
        "ToolbarState" to ToolbarState.serializer(),
        "StatusState" to StatusState.serializer(),
        "EditorState" to EditorState.serializer(),
        "VoicingMenuState" to VoicingMenuState.serializer(),
        "InstrumentMenuState" to InstrumentMenuState.serializer(),
        "ChordSheetState" to ChordSheetState.serializer(),
        "DocumentState" to DocumentState.serializer(),
        "RecentDocumentsState" to RecentDocumentsState.serializer(),
        "UserError" to UserError.serializer(),
        "AudioUnavailable" to AudioUnavailable.serializer(),
        "UnexpectedError" to UnexpectedError.serializer(),
        "TextEdited" to TextEdited.serializer(),
        "InsertDirectiveRequest" to InsertDirectiveRequest.serializer(),
        "CapoChoiceRequest" to CapoChoiceRequest.serializer(),
        "ConfirmDiscardRequest" to ConfirmDiscardRequest.serializer(),
        "PickDocumentRequest" to PickDocumentRequest.serializer(),
        "CloseApproved" to CloseApproved.serializer(),
    )

    /**
     * Decodes one output.
     *
     * @throws BridgeDecodeException for an unknown type name or a payload that
     *   doesn't match the Kotlin DTO.
     */
    fun decode(typeName: String, payload: String): SessionOutput {
        val serializer = serializers[typeName]
            ?: throw BridgeDecodeException("Unknown session output type: $typeName")
        return try {
            json.decodeFromString(serializer, payload)
        } catch (e: SerializationException) {
            throw BridgeDecodeException("Can't decode $typeName: ${e.message}", e)
        } catch (e: IllegalArgumentException) {
            throw BridgeDecodeException("Can't decode $typeName: ${e.message}", e)
        }
    }
}
