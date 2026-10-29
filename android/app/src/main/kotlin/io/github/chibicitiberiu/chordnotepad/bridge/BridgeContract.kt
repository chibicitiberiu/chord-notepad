package io.github.chibicitiberiu.chordnotepad.bridge

// The Kotlin <-> Python bridge contract (docs/ANDROID.md, "Bridge contract").
// Python implements the other half in chordnotepad_android/host.py:
//
//   start(files_dir: str, native_lib_dir: str, document_store, event_sink,
//         audio_options: dict) -> SessionHandle
//   SessionHandle.submit(command: str, args_json: str) -> None   # enqueue only
//   SessionHandle.shutdown() -> None
//
// Threading: Kotlin calls start/submit/shutdown only from PyHost's bridge
// thread, never from Main. Python calls EventSink and DocumentStoreBridge on
// its session thread; neither may wait for the bridge thread.

/** The Python module and function that start a session. */
object PythonEntry {
    const val MODULE = "chordnotepad_android.host"
    const val START = "start"
}

/**
 * Receives the session's output. Python calls [onEvent] on the session thread,
 * once per state or event, in delivery order. Implementations must return
 * quickly and must not throw (an exception would surface inside Python's
 * flush) or wait for the bridge thread.
 */
interface EventSink {
    /**
     * @param typeName The Python DTO class name, e.g. `HighlightState`.
     * @param json Its fields as a JSON object (see [BridgeCodec]).
     */
    fun onEvent(typeName: String, json: String)
}

/** A running session, as returned by Python's `start`. */
interface SessionHandle {
    /** Queue a command for the session thread; returns at once. */
    fun submit(command: String, argsJson: String)

    /** Stop the session thread and release audio. */
    fun shutdown()
}

/**
 * The documents Python reads and writes, by id (a content URI on Android).
 * Called on the Python session thread; blocking I/O is fine there, waiting for
 * the bridge thread is not. Failures throw [DocumentStoreException] with a
 * user-facing message, which Python turns into `FileOperationError`.
 */
interface DocumentStoreBridge {
    /** The document's raw text (Python normalizes it). */
    fun readText(id: String): String

    /** Replace the document's content with [text] (UTF-8). */
    fun writeText(id: String, text: String)

    /** Replace the document's content with [data] (a MIDI export). */
    fun writeBytes(id: String, data: ByteArray)

    /** Whether the document can still be opened (grant held, provider has it). */
    fun isAvailable(id: String): Boolean

    /**
     * Recently used documents still available, newest first, as a JSON array
     * of `{"id", "display_name", "location"}`. Unavailable ones are pruned.
     */
    fun recent(): String

    /** Move a document to the front of the recent list (capped). */
    fun addRecent(id: String, displayName: String, location: String)

    /** The recent list's cap (`max_recent_files` from the config; default 10). */
    fun setMaxRecent(count: Int)

    /**
     * A ref for [id] as JSON `{"id", "display_name", "location"}`, or null when
     * the document can't be reached (Python's `DocumentStore.ref_for`).
     */
    fun describe(id: String): String?
}

/** A document operation failed; [message] is shown to the user. */
class DocumentStoreException(message: String, cause: Throwable? = null) : Exception(message, cause)

/**
 * Device facts Python needs to start the session.
 *
 * @property filesDir The app's private files directory (config, logs, data).
 * @property nativeLibDir `ApplicationInfo.nativeLibraryDir` (the .so files may
 *   stay inside the APK; FluidSynth is loaded by soname).
 * @property audio Passed to Python as the `audio_options` dict.
 */
data class LaunchEnvironment(
    val filesDir: String,
    val nativeLibDir: String,
    val audio: AudioLaunchOptions,
)

/**
 * The `audio_options` dict: `{"sample_rate": int, "frames_per_buffer": int,
 * "soundfont_path": str}`. Python builds its `AudioOptions` from it (the
 * FluidSynth/Oboe settings themselves are Python's business).
 */
data class AudioLaunchOptions(
    val sampleRate: Int,
    val framesPerBuffer: Int,
    val soundfontPath: String,
)

/** Starts a Python session; [ChaquopySessionLauncher] in the app, fakes in tests. */
fun interface SessionLauncher {
    /** Start a session; blocks until Python's `start` returns. Never called on Main. */
    fun launch(env: LaunchEnvironment, store: DocumentStoreBridge, sink: EventSink): SessionHandle
}
