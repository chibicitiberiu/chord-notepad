package io.github.chibicitiberiu.chordnotepad.ui.chordsheet

import io.github.chibicitiberiu.chordnotepad.ui.chordsheet.ChordSheetBufferTest.Companion.bytes
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder

@OptIn(ExperimentalCoroutinesApi::class)
class ChordSheetControllerTest {
    private val fetches = mutableListOf<Float>()
    private var reply: ByteArray? = bytes("multikey_staff")

    private fun controller(dispatcher: kotlinx.coroutines.CoroutineDispatcher) =
        ChordSheetController({ height -> fetches += height; reply }, decodeDispatcher = dispatcher)

    @Test
    fun `one fetch per distinct request, after the height settles`() = runTest {
        val c = controller(UnconfinedTestDispatcher(testScheduler))
        val requests = MutableStateFlow<SheetRequest?>(null)
        val job = launch { c.follow(requests) }
        requests.value = SheetRequest(1, "staff", 1.0, 100)
        advanceTimeBy(10)
        requests.value = SheetRequest(1, "staff", 1.0, 130) // a split drag: only the last height
        advanceTimeBy(100)
        runCurrent()
        assertEquals(listOf(130f), fetches)
        assertNotNull(c.sheet)
        assertEquals("staff", c.sheet!!.buffer.viewId)

        requests.value = SheetRequest(1, "staff", 1.0, 130) // same request (a playhead move)
        advanceTimeBy(100)
        requests.value = SheetRequest(2, "staff", 1.0, 130) // the song changed
        advanceTimeBy(100)
        runCurrent()
        assertEquals(listOf(130f, 130f), fetches)
        job.cancel()
    }

    @Test
    fun `no song clears the sheet, hidden fetches nothing`() = runTest {
        val c = controller(UnconfinedTestDispatcher(testScheduler))
        val requests = MutableStateFlow<SheetRequest?>(SheetRequest(1, "staff", 1.0, 130))
        val job = launch { c.follow(requests) }
        advanceTimeBy(100); runCurrent()
        assertNotNull(c.sheet)
        reply = null
        requests.value = SheetRequest(2, "staff", 1.0, 130)
        advanceTimeBy(100); runCurrent()
        assertNull(c.sheet)
        requests.value = null
        advanceTimeBy(100); runCurrent()
        assertEquals(2, fetches.size)
        job.cancel()
    }

    @Test
    fun `an unsupported version shows a message instead of drawing`() = runTest {
        reply = bytes("multikey_staff").copyOf().also {
            ByteBuffer.wrap(it).order(ByteOrder.LITTLE_ENDIAN).putShort(4, 9)
        }
        val c = controller(UnconfinedTestDispatcher(testScheduler))
        val job = launch { c.follow(MutableStateFlow(SheetRequest(1, "staff", 1.0, 130))) }
        advanceTimeBy(100); runCurrent()
        assertNull(c.sheet)
        assertNotNull(c.failure)
        job.cancel()
    }
}
