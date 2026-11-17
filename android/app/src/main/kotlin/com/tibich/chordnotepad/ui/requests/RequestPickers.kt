package com.tibich.chordnotepad.ui.requests

import android.content.ActivityNotFoundException
import android.net.Uri
import android.util.Log
import androidx.activity.ComponentActivity
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.tibich.chordnotepad.bridge.SessionRequest
import com.tibich.chordnotepad.files.MIDI_MIME_TYPE
import com.tibich.chordnotepad.files.PickerLaunch
import com.tibich.chordnotepad.files.SONG_MIME_TYPE
import com.tibich.chordnotepad.files.WAV_MIME_TYPE
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * The SAF pickers for `PickDocumentRequest`s, registered on the activity
 * itself, so a result that arrives after a rotation reaches the new
 * activity. Also lets [RequestController] cancel the requests that have no
 * UI yet. Call [attach] from `onCreate`, before the activity starts.
 */
class RequestPickers(
    private val activity: ComponentActivity,
    private val pending: StateFlow<SessionRequest?>,
    private val controller: RequestController,
) {
    private lateinit var open: ActivityResultLauncher<Array<String>>
    private lateinit var saveSong: ActivityResultLauncher<String>
    private lateinit var saveMidi: ActivityResultLauncher<String>
    private lateinit var saveWav: ActivityResultLauncher<String>

    /** Register the launchers and follow the pending request while started. */
    fun attach() {
        val answer: (Uri?) -> Unit = { uri -> controller.onPicked(uri?.toString()) }
        open = activity.registerForActivityResult(ActivityResultContracts.OpenDocument(), answer)
        saveSong = activity.registerForActivityResult(ActivityResultContracts.CreateDocument(SONG_MIME_TYPE), answer)
        saveMidi = activity.registerForActivityResult(ActivityResultContracts.CreateDocument(MIDI_MIME_TYPE), answer)
        saveWav = activity.registerForActivityResult(ActivityResultContracts.CreateDocument(WAV_MIME_TYPE), answer)
        activity.lifecycleScope.launch {
            activity.repeatOnLifecycle(Lifecycle.State.STARTED) {
                pending.collect { request -> controller.onPending(request)?.let(::launch) }
            }
        }
    }

    private fun launch(picker: PickerLaunch) {
        try {
            when (picker) {
                is PickerLaunch.Open -> open.launch(picker.mimeTypes.toTypedArray())
                is PickerLaunch.Create -> createLauncher(picker.mimeType).launch(picker.suggestedName)
            }
        } catch (e: ActivityNotFoundException) {
            // No documents UI on this device: answer as if cancelled.
            Log.w(TAG, "No picker for $picker", e)
            controller.onPicked(null)
        }
    }

    /** The CreateDocument launcher registered for [mimeType] (one per MIME type the pickers ask for). */
    private fun createLauncher(mimeType: String): ActivityResultLauncher<String> = when (mimeType) {
        MIDI_MIME_TYPE -> saveMidi
        WAV_MIME_TYPE -> saveWav
        else -> saveSong
    }

    private companion object {
        const val TAG = "CNRequests"
    }
}
