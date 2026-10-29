package io.github.chibicitiberiu.chordnotepad.lifecycle

import android.os.Bundle
import androidx.savedstate.SavedStateRegistry
import io.github.chibicitiberiu.chordnotepad.bridge.DocumentRef
import io.github.chibicitiberiu.chordnotepad.bridge.SessionCommands
import java.util.UUID

/**
 * What the user had in the editor, kept in the activity's saved state so it
 * survives the process being killed in the background.
 *
 * @property documentId The open document's id (`DocumentState.documentId`), or null.
 * @property modified Whether it had unsaved changes.
 */
data class Draft(val text: String, val documentId: String?, val modified: Boolean)

/** A [Draft] tagged with the process that saved it. */
data class SavedDraft(val processToken: String, val draft: Draft)

/** Identifies this process: a saved draft from another one means the process died. */
object ProcessToken {
    /** Random per process. */
    val value: String = UUID.randomUUID().toString()
}

/** When to keep and when to restore a draft (pure logic; [DraftHook] does the Android part). */
object DraftPolicy {
    /**
     * Saved-state bundles share a ~1 MB binder transaction with everything
     * else, so very long texts are not kept (UTF-16: 2 bytes per char).
     */
    const val MAX_DRAFT_CHARS = 100_000

    /** The draft to save, or null when there's nothing worth keeping or it's too big. */
    fun toSave(draft: Draft?, processToken: String, maxChars: Int = MAX_DRAFT_CHARS): SavedDraft? {
        if (draft == null || draft.text.length > maxChars) return null
        if (draft.text.isEmpty() && draft.documentId == null) return null
        return SavedDraft(processToken, draft)
    }

    /**
     * The draft to restore: only after process death. A rotation or a
     * returning activity in the same process still has the live session.
     */
    fun toRestore(saved: SavedDraft?, processToken: String): Draft? =
        saved?.takeIf { it.processToken != processToken }?.draft

    /**
     * Send the restore. A document that can't be reached any more (grant
     * revoked, file deleted) is dropped and the text kept as unsaved changes.
     *
     * @param resolve Builds a ref for a document id (provider I/O; call off Main).
     */
    fun restore(draft: Draft, resolve: (String) -> DocumentRef?, commands: SessionCommands) {
        val ref = draft.documentId?.let(resolve)
        val modified = draft.modified || (draft.documentId != null && ref == null)
        commands.restoreDraft(draft.text, ref, modified)
    }
}

/**
 * Hooks a [Draft] into an activity's [SavedStateRegistry]: saves it from
 * [source] and, after process death, hands the restored one to [onRestore].
 * Call [attach] in `onCreate`, after `super.onCreate`.
 */
class DraftHook(
    private val source: () -> Draft?,
    private val onRestore: (Draft) -> Unit,
    private val processToken: String = ProcessToken.value,
) {
    /** Restore (if the process died) and start saving. */
    fun attach(registry: SavedStateRegistry) {
        val saved = registry.consumeRestoredStateForKey(KEY)?.let(::fromBundle)
        DraftPolicy.toRestore(saved, processToken)?.let(onRestore)
        registry.registerSavedStateProvider(KEY) {
            DraftPolicy.toSave(source(), processToken)?.let(::toBundle) ?: Bundle()
        }
    }

    private fun toBundle(saved: SavedDraft) = Bundle().apply {
        putString(TOKEN, saved.processToken)
        putString(TEXT, saved.draft.text)
        putString(DOCUMENT_ID, saved.draft.documentId)
        putBoolean(MODIFIED, saved.draft.modified)
    }

    private fun fromBundle(b: Bundle): SavedDraft? {
        val token = b.getString(TOKEN) ?: return null
        val text = b.getString(TEXT) ?: return null
        return SavedDraft(token, Draft(text, b.getString(DOCUMENT_ID), b.getBoolean(MODIFIED)))
    }

    private companion object {
        const val KEY = "io.github.chibicitiberiu.chordnotepad.draft"
        const val TOKEN = "process_token"
        const val TEXT = "text"
        const val DOCUMENT_ID = "document_id"
        const val MODIFIED = "modified"
    }
}
