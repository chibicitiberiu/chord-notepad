package com.tibich.chordnotepad.files

import com.tibich.chordnotepad.bridge.PickDocumentRequest
import com.tibich.chordnotepad.bridge.PickMode

/**
 * Which SAF picker answers a [PickDocumentRequest]. The UI launches it
 * (`ActivityResultContracts.OpenDocument` / `CreateDocument`), passes the URI
 * to [SafDocumentStore.adopt] and answers the request with the ref.
 */
sealed interface PickerLaunch {
    /** `ACTION_OPEN_DOCUMENT` with these MIME types. */
    data class Open(val mimeTypes: List<String>) : PickerLaunch

    /** `ACTION_CREATE_DOCUMENT` for [mimeType], pre-filled with [suggestedName]. */
    data class Create(val mimeType: String, val suggestedName: String) : PickerLaunch
}

/** MIME type of a saved song. */
const val SONG_MIME_TYPE = "text/plain"

/** MIME type of a MIDI export. */
const val MIDI_MIME_TYPE = "audio/midi"

/**
 * What Open asks the picker for: text first, then anything, as the desktop's
 * "Text Files / All Files" dialog allows any file. Songs are plain text, but
 * providers label `.cho`/`.chordpro` files inconsistently and hiding them
 * would be worse than letting the core report a file it can't read.
 */
val OPEN_MIME_TYPES = listOf(SONG_MIME_TYPE, "text/*", "*/*")

/** The picker for [request]. */
fun pickerFor(request: PickDocumentRequest): PickerLaunch = when (request.mode) {
    PickMode.OPEN -> PickerLaunch.Open(OPEN_MIME_TYPES)
    PickMode.SAVE -> PickerLaunch.Create(SONG_MIME_TYPE, request.suggestedName.ifEmpty { "Untitled.txt" })
    PickMode.EXPORT_MIDI -> PickerLaunch.Create(MIDI_MIME_TYPE, request.suggestedName.ifEmpty { "Untitled.mid" })
}
