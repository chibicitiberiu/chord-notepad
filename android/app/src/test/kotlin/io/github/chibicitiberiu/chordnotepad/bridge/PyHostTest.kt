package io.github.chibicitiberiu.chordnotepad.bridge

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Collections
import java.util.concurrent.Executors

class PyHostTest {
    private val executor = Executors.newSingleThreadExecutor { r -> Thread(r, "test-bridge") }
    private val repo = SessionRepository()
    private val log: MutableList<String> = Collections.synchronizedList(mutableListOf())
    private var sink: EventSink? = null
    private var launchFails = false
    private var submitFails = false

    private val handle = object : SessionHandle {
        override fun submit(command: String, argsJson: String) {
            if (submitFails) throw IllegalStateException("python said no")
            log += "submit $command $argsJson on ${Thread.currentThread().name}"
        }

        override fun shutdown() {
            log += "shutdown"
        }
    }

    private val env = LaunchEnvironment("/files", "/lib", AudioLaunchOptions(48_000, 192, "/files/sf2"))

    private val host = PyHost(
        launcher = { e, _, s ->
            log += "launch ${e.audio.sampleRate} on ${Thread.currentThread().name}"
            if (launchFails) throw RuntimeException("no python")
            sink = s
            handle
        },
        environment = { env },
        store = NoStore,
        repository = repo,
        executor = executor,
    )

    private fun drain() = executor.submit {}.get()

    @After
    fun stop() {
        executor.shutdownNow()
    }

    /** Runs [block] while collecting the repository's errors. */
    private fun collectingErrors(block: () -> Unit): List<SessionError> {
        val errors: MutableList<SessionError> = Collections.synchronizedList(mutableListOf())
        // Unconfined: the collector runs inside the emitting thread's tryEmit,
        // so the list is complete as soon as block() (and its drain) returns.
        val job = CoroutineScope(Dispatchers.Unconfined).launch { repo.errors.collect { errors += it } }
        try {
            block()
        } finally {
            job.cancel()
        }
        return errors.toList()
    }

    @Test
    fun `starts on the bridge thread, then runs commands in order there`() {
        host.start()
        host.commands.stop()
        host.commands.playPause(3)
        drain()
        assertEquals(
            listOf(
                "launch 48000 on test-bridge",
                "submit stop {} on test-bridge",
                """submit play_pause {"from_offset":3} on test-bridge""",
            ),
            log,
        )
        assertEquals(HostStatus.Running, repo.hostStatus.value)
    }

    @Test
    fun `start is idempotent`() {
        host.start()
        host.start()
        drain()
        assertEquals(1, log.count { it.startsWith("launch") })
    }

    @Test
    fun `commands before start are dropped`() {
        host.commands.stop()
        host.start()
        drain()
        assertEquals(listOf("launch 48000 on test-bridge"), log)
    }

    @Test
    fun `a failed start is reported and later commands are dropped`() {
        launchFails = true
        host.start()
        host.commands.stop()
        drain()
        assertEquals(HostStatus.Failed("no python"), repo.hostStatus.value)
        assertTrue(log.none { it.startsWith("submit") })
    }

    @Test
    fun `a failing submit becomes an UnexpectedError, not a crash`() {
        host.start()
        submitFails = true
        val errors = collectingErrors {
            host.commands.stop()
            drain()
        }
        assertEquals(HostStatus.Running, repo.hostStatus.value)
        assertTrue(errors.single().let { it is UnexpectedError && "stop" in it.message })
    }

    @Test
    fun `events from Python reach the repository, bad ones become UnexpectedError`() {
        host.start()
        drain()
        sink!!.onEvent("StatusState", """{"text": "Ready"}""")
        assertEquals("Ready", repo.status.value?.text)
        val errors = collectingErrors {
            sink!!.onEvent("StatusState", "not json") // must not throw into Python
            sink!!.onEvent("Nope", "{}")
        }
        assertEquals(2, errors.size)
        assertTrue(errors.all { it is UnexpectedError && it.context == "bridge" })
        assertEquals("Ready", repo.status.value?.text)
    }

    @Test
    fun `answering a request clears it`() {
        host.start()
        repo.publish(ConfirmDiscardRequest(9))
        host.commands.respondDiscard(9, DiscardChoice.DISCARD)
        assertEquals(null, repo.pendingRequest.value)
    }

    @Test
    fun `shutdown stops the session`() {
        host.start()
        host.shutdown()
        drain()
        assertEquals("shutdown", log.last())
        assertEquals(HostStatus.Stopped, repo.hostStatus.value)
    }

    private object NoStore : DocumentStoreBridge {
        override fun readText(id: String) = error("unused")
        override fun writeText(id: String, text: String) = Unit
        override fun writeBytes(id: String, data: ByteArray) = Unit
        override fun isAvailable(id: String) = false
        override fun recent() = "[]"
        override fun addRecent(id: String, displayName: String, location: String) = Unit
        override fun setMaxRecent(count: Int) = Unit
        override fun describe(id: String): String? = null
        override fun rename(id: String, displayName: String) = error("unused")
    }
}
