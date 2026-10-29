package io.github.chibicitiberiu.chordnotepad.ui

import io.github.chibicitiberiu.chordnotepad.bridge.AudioUnavailable
import io.github.chibicitiberiu.chordnotepad.bridge.SessionError
import io.github.chibicitiberiu.chordnotepad.bridge.UserError
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ErrorQueueTest {
    @Test
    fun `errors queue up in order until dismissed`() = runTest(UnconfinedTestDispatcher()) {
        val queue = ErrorQueue()
        val errors = MutableSharedFlow<SessionError>()
        val job = queue.bind(this, errors)
        errors.emit(UserError("Error", "one"))
        errors.emit(AudioUnavailable("no audio", fromClick = true))
        errors.emit(UserError("Error", "one")) // the same again is a second entry
        assertEquals(3, queue.items.value.size)
        queue.dismiss(queue.items.value.first())
        assertEquals(listOf(AudioUnavailable("no audio", true), UserError("Error", "one")), queue.items.value.map { it.error })
        job.cancel()
    }

    @Test
    fun `old errors are dropped beyond the limit`() {
        val queue = ErrorQueue(limit = 2)
        repeat(3) { queue.add(UserError("Error", "$it")) }
        assertEquals(listOf("1", "2"), queue.items.value.map { (it.error as UserError).message })
    }
}
