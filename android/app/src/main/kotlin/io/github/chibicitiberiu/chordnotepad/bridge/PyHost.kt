package io.github.chibicitiberiu.chordnotepad.bridge

import android.util.Log
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.withContext
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Owns the Python session for the whole process (one per app).
 *
 * Every call into Python runs on one dedicated "python-bridge" thread, in
 * order: starting Chaquopy and the session, then each command. Main never
 * calls Python; [submit] only queues. Commands submitted after [start] wait
 * behind it, even while Python is still starting; commands submitted before
 * [start], or after a failed start, are dropped and logged.
 *
 * @param launcher Starts Python and the session ([ChaquopySessionLauncher]).
 * @param environment Gathers the launch environment; runs on the bridge
 *   thread, so it may do I/O (copying the SoundFont).
 * @param store The documents Python reads and writes.
 * @param repository Where the session's output goes.
 * @param executor The bridge thread (single-threaded; tests pass their own).
 */
class PyHost(
    private val launcher: SessionLauncher,
    private val environment: () -> LaunchEnvironment,
    private val store: DocumentStoreBridge,
    val repository: SessionRepository,
    private val executor: ExecutorService = newBridgeExecutor(),
) : CommandSubmitter {
    private val started = AtomicBoolean(false)

    // Only touched on the bridge thread.
    private var handle: SessionHandle? = null

    /** The bridge thread as a dispatcher, for work that must be ordered with commands. */
    val dispatcher: CoroutineDispatcher = executor.asCoroutineDispatcher()

    /** Typed commands; answering a request clears it from the repository. */
    val commands: SessionCommands = SessionCommands(this, repository::requestAnswered)

    /** Start Python and the session on the bridge thread. Idempotent; returns at once. */
    fun start() {
        if (!started.compareAndSet(false, true)) return
        repository.setHostStatus(HostStatus.Starting)
        executor.execute {
            try {
                handle = launcher.launch(environment(), store, RepositoryEventSink(repository))
                repository.setHostStatus(HostStatus.Running)
            } catch (t: Throwable) {
                Log.e(TAG, "Starting the Python session failed", t)
                repository.setHostStatus(HostStatus.Failed(t.message ?: t.toString()))
            }
        }
    }

    /** Queue a command for the session. Safe on any thread, including Main. */
    override fun submit(command: String, argsJson: String) {
        executor.execute {
            val session = handle
            if (session == null) {
                Log.w(TAG, "No session; dropped command $command")
                return@execute
            }
            try {
                session.submit(command, argsJson)
            } catch (e: Exception) {
                Log.e(TAG, "Submitting $command failed", e)
                repository.publish(UnexpectedError("Command $command failed: $e", context = "bridge"))
            }
        }
    }

    /**
     * The chord sheet's op buffer for a strip [height] dp tall, packed by
     * Python on the bridge thread (ordered with commands; 10-40 ms on the
     * emulator). Null without a session, without a rendered song, or when
     * packing failed (Python reports that as an `UnexpectedError`).
     */
    suspend fun chordSheetBuffer(height: Float): ByteArray? = withContext(dispatcher) {
        try {
            handle?.chordSheetBuffer(height)
        } catch (e: Exception) {
            Log.e(TAG, "chord_sheet_buffer failed", e)
            null
        }
    }

    /** Shut the session down (tests, or a future explicit exit). Returns at once. */
    fun shutdown() {
        executor.execute {
            try {
                handle?.shutdown()
            } catch (e: Exception) {
                Log.e(TAG, "Session shutdown failed", e)
            }
            handle = null
            repository.setHostStatus(HostStatus.Stopped)
        }
    }

    private companion object {
        const val TAG = "CNPyHost"

        fun newBridgeExecutor(): ExecutorService = Executors.newSingleThreadExecutor { r ->
            Thread(r, "python-bridge").apply { isDaemon = true }
        }
    }
}
