package com.tibich.chordnotepad.files

import com.tibich.chordnotepad.bridge.PickDocumentRequest
import com.tibich.chordnotepad.bridge.PickMode
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DocumentPickersTest {
    private fun pick(mode: PickMode, name: String = "") = pickerFor(PickDocumentRequest(1, mode, name))

    @Test
    fun `each pick mode gets its picker and MIME type`() {
        assertEquals(PickerLaunch.Open(OPEN_MIME_TYPES), pick(PickMode.OPEN))
        assertEquals(PickerLaunch.Create("text/plain", "song.txt"), pick(PickMode.SAVE, "song.txt"))
        assertEquals(PickerLaunch.Create("audio/midi", "song.mid"), pick(PickMode.EXPORT_MIDI, "song.mid"))
        assertEquals(PickerLaunch.Create("audio/wav", "song.wav"), pick(PickMode.EXPORT_AUDIO, "song.wav"))
    }

    @Test
    fun `an empty suggestion falls back to Untitled with the extension`() {
        assertEquals(PickerLaunch.Create(SONG_MIME_TYPE, "Untitled.txt"), pick(PickMode.SAVE))
        assertEquals(PickerLaunch.Create(MIDI_MIME_TYPE, "Untitled.mid"), pick(PickMode.EXPORT_MIDI))
        assertEquals(PickerLaunch.Create(WAV_MIME_TYPE, "Untitled.wav"), pick(PickMode.EXPORT_AUDIO))
    }

    @Test
    fun `only songs keep their grant`() {
        assertTrue(SafDocumentStore.keepsGrant(PickMode.OPEN))
        assertTrue(SafDocumentStore.keepsGrant(PickMode.SAVE))
        assertFalse(SafDocumentStore.keepsGrant(PickMode.EXPORT_MIDI))
        assertFalse(SafDocumentStore.keepsGrant(PickMode.EXPORT_AUDIO))
    }
}
