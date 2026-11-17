package com.tibich.chordnotepad.ui.requests

import android.util.Log
import com.tibich.chordnotepad.bridge.ConfirmDiscardRequest
import com.tibich.chordnotepad.bridge.DiscardChoice
import com.tibich.chordnotepad.bridge.DocumentRef
import com.tibich.chordnotepad.bridge.InsertDirectiveRequest
import com.tibich.chordnotepad.bridge.PaintPdfRequest
import com.tibich.chordnotepad.bridge.PickDocumentRequest
import com.tibich.chordnotepad.bridge.PickMode
import com.tibich.chordnotepad.bridge.SessionCommands
import com.tibich.chordnotepad.bridge.SessionRequest
import com.tibich.chordnotepad.files.PickerLaunch
import com.tibich.chordnotepad.files.pickerFor
import kotlinx.coroutines.flow.StateFlow

/** How the UI presents a pending [SessionRequest]. */
sealed interface RequestPresentation {
    /** The screen shows a dialog for it (Compose, from the pending request). */
    data class Dialog(val request: SessionRequest) : RequestPresentation

    /** The activity launches a system picker for it ([RequestController.takePickerLaunch]). */
    data class Picker(val request: PickDocumentRequest) : RequestPresentation

    /** Painted and written off the main thread, no UI ([RequestController.paintOnce]). */
    data class Paint(val request: PaintPdfRequest) : RequestPresentation

    /**
     * Not presented: cancelled at once. Every kind has a UI since M5; kept
     * for a request type a newer core may add.
     */
    data class NotYetSupported(val request: SessionRequest) : RequestPresentation
}

/** Which presentation [request] gets. */
fun presentationOf(request: SessionRequest): RequestPresentation = when (request) {
    is ConfirmDiscardRequest, is InsertDirectiveRequest -> RequestPresentation.Dialog(request)
    is PickDocumentRequest -> RequestPresentation.Picker(request)
    is PaintPdfRequest -> RequestPresentation.Paint(request)
}

/**
 * Answers the session's requests. App-scoped (in `AppGraph`), so what it
 * remembers survives rotation: the pending request itself lives in the
 * repository's `pendingRequest`, and this class remembers which picker was
 * already launched, so a recreated activity doesn't open the same picker
 * twice and the result delivered to it still answers the right request.
 *
 * The same goes for a PDF export's pages: painted once per request, so a
 * rotation while they're written doesn't write them twice.
 *
 * Main thread, except that [adopt] and [paint] run through [runOffMain].
 *
 * @param pending The repository's pending request.
 * @param adopt Persists a picked document's grant and describes it
 *   (`SafDocumentStore.adopt`); provider I/O.
 * @param runOffMain Runs provider I/O away from the main thread.
 * @param paint Paints a PDF export and writes it (`PdfExporter.export`):
 *   "" when written, else why not; provider I/O.
 * @param onDiscardAnswered Told every answer to the unsaved-changes question,
 *   before it is sent (`CloseCoordinator`).
 */
class RequestController(
    private val pending: StateFlow<SessionRequest?>,
    private val commands: SessionCommands,
    private val adopt: (uri: String, mode: PickMode) -> DocumentRef,
    private val runOffMain: (block: () -> Unit) -> Unit,
    private val onDiscardAnswered: (DiscardChoice) -> Unit = {},
    private val paint: (PaintPdfRequest) -> String? = { null },
) {
    private var launchedPickerId: Int? = null
    private var paintedId: Int? = null

    /**
     * Handle a request that just became pending: cancels the ones not
     * presented yet. Returns the picker to launch for a pick request that
     * hasn't had one yet (marking it launched), else null.
     */
    fun onPending(request: SessionRequest?): PickerLaunch? = when (val p = request?.let(::presentationOf)) {
        is RequestPresentation.NotYetSupported -> {
            cancel(p.request)
            null
        }
        is RequestPresentation.Picker -> takePickerLaunch()
        is RequestPresentation.Paint -> {
            paintOnce(p.request)
            null
        }
        is RequestPresentation.Dialog, null -> null
    }

    /**
     * Paint and write [request]'s PDF off the main thread and answer it;
     * once per request (a recreated activity sees the same pending request).
     */
    fun paintOnce(request: PaintPdfRequest) {
        if (paintedId == request.requestId) return
        paintedId = request.requestId
        runOffMain {
            val answer = try {
                paint(request)
            } catch (e: RuntimeException) {
                Log.w(TAG, "Painting the PDF failed", e)
                null
            }
            commands.respondPaint(request.requestId, answer)
        }
    }

    /** The picker for the pending pick request, once per request; null otherwise. */
    fun takePickerLaunch(): PickerLaunch? {
        val request = pending.value as? PickDocumentRequest ?: return null
        if (launchedPickerId == request.requestId) return null
        launchedPickerId = request.requestId
        return pickerFor(request)
    }

    /**
     * The picker returned [uri], or null when the user backed out. Answers
     * the pick request it was launched for; a result for anything else (a
     * request the session already dropped, or one from before the process
     * died) is ignored.
     */
    fun onPicked(uri: String?) {
        val request = pending.value as? PickDocumentRequest ?: return
        if (request.requestId != launchedPickerId) return
        if (uri == null) {
            commands.respondPick(request.requestId, null)
            return
        }
        runOffMain {
            val ref = try {
                adopt(uri, request.mode)
            } catch (e: RuntimeException) {
                Log.w(TAG, "Can't use the picked document $uri", e)
                null
            }
            commands.respondPick(request.requestId, ref)
        }
    }

    /** The unsaved-changes dialog's answer; null (dismissed) cancels like Cancel. */
    fun answerDiscard(request: ConfirmDiscardRequest, choice: DiscardChoice?) {
        val answer = choice ?: DiscardChoice.CANCEL
        onDiscardAnswered(answer)
        commands.respondDiscard(request.requestId, answer)
    }

    /** An Insert directive dialog's fields, or null for Cancel; the session checks them. */
    fun answerDirective(request: InsertDirectiveRequest, fields: Map<String, String>?) =
        commands.respondDirective(request.requestId, fields)

    /** Ask the session whether an Insert dialog's [fields] make a valid directive. */
    fun checkDirective(request: InsertDirectiveRequest, fields: Map<String, String>) =
        commands.checkDirective(request.kind, fields, request.requestId)

    /** Cancel [request] (the user dismissed it, or there's no UI for it). */
    fun cancel(request: SessionRequest) = when (request) {
        is ConfirmDiscardRequest -> answerDiscard(request, DiscardChoice.CANCEL)
        is PickDocumentRequest -> commands.respondPick(request.requestId, null)
        is InsertDirectiveRequest -> commands.respondDirective(request.requestId, null)
        is PaintPdfRequest -> commands.respondPaint(request.requestId, null)
    }

    private companion object {
        const val TAG = "CNRequests"
    }
}
