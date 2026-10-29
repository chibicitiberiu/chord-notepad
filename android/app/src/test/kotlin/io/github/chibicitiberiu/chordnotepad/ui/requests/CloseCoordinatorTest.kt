package io.github.chibicitiberiu.chordnotepad.ui.requests

import io.github.chibicitiberiu.chordnotepad.bridge.ConfirmDiscardRequest
import io.github.chibicitiberiu.chordnotepad.bridge.DiscardChoice
import io.github.chibicitiberiu.chordnotepad.bridge.SessionCommands
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class CloseCoordinatorTest {
    private var resets = 0
    private val coordinator = CloseCoordinator(resetSession = { resets++ })

    @Test
    fun `a close approved after Don't save resets the session and finishes`() {
        coordinator.onCloseRequested()
        coordinator.onDiscardAnswered(DiscardChoice.DISCARD)
        coordinator.onCloseApproved()
        assertEquals(1, resets)
        assertTrue(coordinator.finishRequested.value)
    }

    @Test
    fun `a close approved after Save keeps the session`() {
        coordinator.onCloseRequested()
        coordinator.onDiscardAnswered(DiscardChoice.SAVE)
        coordinator.onCloseApproved()
        assertEquals(0, resets)
        assertTrue(coordinator.finishRequested.value)
    }

    @Test
    fun `a close without a question keeps the session`() {
        coordinator.onCloseApproved()
        assertEquals(0, resets)
        assertTrue(coordinator.finishRequested.value)
    }

    @Test
    fun `a discard is used once`() {
        coordinator.onDiscardAnswered(DiscardChoice.DISCARD)
        coordinator.onCloseApproved()
        coordinator.consumeFinish()
        coordinator.onCloseApproved()
        assertEquals(1, resets)
    }

    @Test
    fun `a discard for something else is forgotten when the next close is requested`() {
        // File > New > Don't save, then later Back > Save.
        coordinator.onDiscardAnswered(DiscardChoice.DISCARD)
        coordinator.onCloseRequested()
        coordinator.onDiscardAnswered(DiscardChoice.SAVE)
        coordinator.onCloseApproved()
        assertEquals(0, resets)
    }

    @Test
    fun `cancelling the question after a discard doesn't reset`() {
        coordinator.onDiscardAnswered(DiscardChoice.DISCARD)
        coordinator.onDiscardAnswered(DiscardChoice.CANCEL)
        coordinator.onCloseApproved()
        assertEquals(0, resets)
    }

    @Test
    fun `finish waits for a collector that arrives late and is reported once`() {
        coordinator.onCloseApproved()
        // The activity was recreated; its new composition reads the state.
        assertTrue(coordinator.finishRequested.value)
        coordinator.consumeFinish()
        assertFalse(coordinator.finishRequested.value)
    }

    @Test
    fun `bound to the repository's flow it follows every close approval`() = runTest {
        val closeApproved = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
        coordinator.bind(TestScope(UnconfinedTestDispatcher(testScheduler)), closeApproved)
        closeApproved.emit(Unit)
        assertTrue(coordinator.finishRequested.value)
    }

    @Test
    fun `the dialog's Don't save leads to an empty untitled document`() {
        val pending = MutableStateFlow<io.github.chibicitiberiu.chordnotepad.bridge.SessionRequest?>(null)
        val sent = mutableListOf<Pair<String, JsonObject>>()
        val commands = SessionCommands(
            submitter = { command, args -> sent += command to Json.parseToJsonElement(args) as JsonObject },
            onResponded = {},
        )
        val real = CloseCoordinator(resetSession = {
            commands.stop()
            commands.restoreDraft("", null, false)
        })
        val controller = RequestController(pending, commands, adopt = { _, _ -> error("unused") }, runOffMain = {},
            onDiscardAnswered = real::onDiscardAnswered)

        real.onCloseRequested()
        controller.answerDiscard(ConfirmDiscardRequest(5), DiscardChoice.DISCARD)
        real.onCloseApproved()

        val restore = sent.single { it.first == "restore_draft" }.second
        assertEquals(JsonPrimitive(""), restore["text"])
        assertEquals(JsonNull, restore["document"])
        assertEquals(JsonPrimitive(false), restore["modified"])
        assertTrue(sent.indexOfFirst { it.first == "stop" } < sent.indexOfFirst { it.first == "restore_draft" })
        assertTrue(real.finishRequested.value)
    }
}
