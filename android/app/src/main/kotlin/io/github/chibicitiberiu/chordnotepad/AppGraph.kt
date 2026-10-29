package io.github.chibicitiberiu.chordnotepad

import android.content.Context
import androidx.lifecycle.ProcessLifecycleOwner
import io.github.chibicitiberiu.chordnotepad.audio.audioLaunchOptions
import io.github.chibicitiberiu.chordnotepad.bridge.ChaquopySessionLauncher
import io.github.chibicitiberiu.chordnotepad.bridge.LaunchEnvironment
import io.github.chibicitiberiu.chordnotepad.bridge.PyHost
import io.github.chibicitiberiu.chordnotepad.bridge.SessionCommands
import io.github.chibicitiberiu.chordnotepad.bridge.SessionRepository
import io.github.chibicitiberiu.chordnotepad.files.ContentResolverDocumentAccess
import io.github.chibicitiberiu.chordnotepad.files.RecentDocumentsFile
import io.github.chibicitiberiu.chordnotepad.files.SafDocumentStore
import io.github.chibicitiberiu.chordnotepad.lifecycle.AndroidAudioFocusGateway
import io.github.chibicitiberiu.chordnotepad.lifecycle.AndroidNoisyGateway
import io.github.chibicitiberiu.chordnotepad.lifecycle.AppLifecycleHooks
import io.github.chibicitiberiu.chordnotepad.lifecycle.Draft
import io.github.chibicitiberiu.chordnotepad.lifecycle.PlaybackAudioPolicy
import io.github.chibicitiberiu.chordnotepad.ui.ErrorQueue
import io.github.chibicitiberiu.chordnotepad.ui.editor.EditorController
import io.github.chibicitiberiu.chordnotepad.ui.editor.bind
import io.github.chibicitiberiu.chordnotepad.ui.requests.RequestController
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.io.File

/**
 * The app's long-lived objects, created once in [ChordNotepadApp.onCreate].
 * Python doesn't start until [pyHost]'s `start()` (the activity calls it).
 */
class AppGraph(context: Context) {
    private val app = context.applicationContext

    /** Main-thread scope for app-lifetime collectors. */
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)

    /** The session's output, as flows. */
    val repository = SessionRepository()

    /** SAF documents and the recent list. */
    val documents = SafDocumentStore(
        ContentResolverDocumentAccess(app),
        RecentDocumentsFile(File(app.filesDir, "recent_documents.json")),
    )

    /** The Python session. */
    val pyHost = PyHost(
        launcher = ChaquopySessionLauncher(app),
        environment = {
            LaunchEnvironment(
                filesDir = app.filesDir.path,
                nativeLibDir = app.applicationInfo.nativeLibraryDir,
                audio = audioLaunchOptions(app),
            )
        },
        store = documents,
        repository = repository,
    )

    /** Commands to the session. */
    val commands: SessionCommands get() = pyHost.commands

    /** Answers the session's requests (app-scoped: a rotation loses no picker result). */
    val requests = RequestController(
        pending = repository.pendingRequest,
        commands = pyHost.commands,
        adopt = documents::adopt,
        runOffMain = { block -> scope.launch(Dispatchers.IO) { block() } },
    )

    /** The editor's text and highlighting (app-scoped: survives rotation). */
    val editor = EditorController(commands)

    /** The session's errors waiting to be shown. */
    val errorQueue = ErrorQueue()

    /**
     * The editor's current text, for the draft kept across process death
     * (main thread); while null no draft is saved.
     */
    @Volatile
    var editorText: (() -> String)? = null

    /** The draft to save now, or null (main thread). */
    fun currentDraft(): Draft? {
        val text = editorText?.invoke() ?: return null
        val doc = repository.document.value
        return Draft(text, doc?.documentId, doc?.isModified ?: false)
    }

    /** Hook the process lifecycle, the audio policy and the editor (main thread, once). */
    fun install() {
        editorText = editor::currentText
        editor.bind(scope, repository)
        errorQueue.bind(scope, repository.errors)
        ProcessLifecycleOwner.get().lifecycle.addObserver(AppLifecycleHooks(commands))
        PlaybackAudioPolicy(AndroidAudioFocusGateway(app), AndroidNoisyGateway(app), commands::pause)
            .bind(scope, repository.playback)
    }
}
