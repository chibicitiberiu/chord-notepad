package io.github.chibicitiberiu.chordnotepad.bridge

import android.util.Log

/**
 * The [EventSink] Python calls: decodes each output and hands it to the
 * repository. Never throws back into Python; an output that doesn't decode is
 * logged and surfaced as an [UnexpectedError] (it means the DTOs drifted).
 */
class RepositoryEventSink(private val repository: SessionRepository) : EventSink {
    override fun onEvent(typeName: String, json: String) {
        val output = try {
            BridgeCodec.decode(typeName, json)
        } catch (e: BridgeDecodeException) {
            Log.e(TAG, "Dropping session output", e)
            UnexpectedError(e.message ?: "Can't decode $typeName", context = "bridge")
        } catch (e: RuntimeException) {
            Log.e(TAG, "Dropping session output", e)
            UnexpectedError("Can't decode $typeName: $e", context = "bridge")
        }
        repository.publish(output)
    }

    private companion object {
        const val TAG = "CNBridge"
    }
}
