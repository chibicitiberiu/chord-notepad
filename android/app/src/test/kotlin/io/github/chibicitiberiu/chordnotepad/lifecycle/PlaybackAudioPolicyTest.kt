package io.github.chibicitiberiu.chordnotepad.lifecycle

import io.github.chibicitiberiu.chordnotepad.bridge.PlaybackState
import io.github.chibicitiberiu.chordnotepad.bridge.PlaybackStatus
import io.github.chibicitiberiu.chordnotepad.bridge.PlaybackStatus.IDLE
import io.github.chibicitiberiu.chordnotepad.bridge.PlaybackStatus.PAUSED
import io.github.chibicitiberiu.chordnotepad.bridge.PlaybackStatus.PLAYING
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PlaybackAudioPolicyTest {
    private val events = mutableListOf<String>()
    private var grant = true
    private var onLoss: (() -> Unit)? = null
    private var onNoisy: (() -> Unit)? = null
    private var pauses = 0

    private val focus = object : AudioFocusGateway {
        override fun request(onLoss: () -> Unit): Boolean {
            events += "request"
            this@PlaybackAudioPolicyTest.onLoss = onLoss
            return grant
        }

        override fun abandon() {
            events += "abandon"
        }
    }

    private val noisy = object : NoisyGateway {
        override fun register(onNoisy: () -> Unit) {
            events += "register"
            this@PlaybackAudioPolicyTest.onNoisy = onNoisy
        }

        override fun unregister() {
            events += "unregister"
        }
    }

    private val policy = PlaybackAudioPolicy(focus, noisy) { pauses++ }

    private fun go(vararg statuses: PlaybackStatus) = statuses.forEach(policy::onStatus)

    @Test
    fun `play takes focus and listens for noisy, stop gives both back`() {
        go(IDLE, PLAYING)
        assertEquals(listOf("register", "request"), events)
        go(IDLE)
        assertEquals(listOf("register", "request", "abandon", "unregister"), events)
        assertEquals(0, pauses)
    }

    @Test
    fun `pause keeps focus, resume asks again`() {
        go(PLAYING, PAUSED)
        assertEquals(listOf("register", "request"), events)
        go(PLAYING)
        assertEquals(listOf("register", "request", "register", "request"), events)
    }

    @Test
    fun `denied focus pauses at once`() {
        grant = false
        go(PLAYING)
        assertEquals(1, pauses)
    }

    @Test
    fun `focus loss and noisy audio pause`() {
        go(PLAYING)
        onLoss!!()
        onNoisy!!()
        assertEquals(2, pauses)
    }

    @Test
    fun `idle without playing does nothing`() {
        go(IDLE, IDLE)
        assertTrue(events.isEmpty())
    }

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun `follows the repository's playback state`() = runTest(UnconfinedTestDispatcher()) {
        val playback = MutableStateFlow<PlaybackState?>(null)
        policy.bind(backgroundScope, playback)
        playback.value = PlaybackState(PLAYING, bar = 1, totalBars = 4)
        playback.value = PlaybackState(PLAYING, bar = 2, totalBars = 4) // same status: nothing new
        assertEquals(listOf("register", "request"), events)
        playback.value = PlaybackState(IDLE)
        assertEquals("unregister", events.last())
    }
}
