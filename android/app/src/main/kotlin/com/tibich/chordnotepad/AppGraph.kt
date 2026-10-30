package com.tibich.chordnotepad

import android.content.Context
import androidx.lifecycle.ProcessLifecycleOwner
import com.tibich.chordnotepad.audio.audioLaunchOptions
import com.tibich.chordnotepad.bridge.ChaquopySessionLauncher
import com.tibich.chordnotepad.bridge.LaunchEnvironment
import com.tibich.chordnotepad.bridge.PyHost
import com.tibich.chordnotepad.bridge.SessionCommands
import com.tibich.chordnotepad.bridge.SessionRepository
import com.tibich.chordnotepad.files.ContentResolverDocumentAccess
import com.tibich.chordnotepad.files.RecentDocumentsFile
import com.tibich.chordnotepad.files.SafDocumentStore
import com.tibich.chordnotepad.lifecycle.AndroidAudioFocusGateway
import com.tibich.chordnotepad.lifecycle.AndroidNoisyGateway
import com.tibich.chordnotepad.lifecycle.AppLifecycleHooks
import com.tibich.chordnotepad.lifecycle.Draft
import com.tibich.chordnotepad.lifecycle.PlaybackAudioPolicy
import com.tibich.chordnotepad.ui.ErrorQueue
import com.tibich.chordnotepad.ui.editor.EditorController
import com.tibich.chordnotepad.ui.editor.bind
import com.tibich.chordnotepad.ui.main.ModeController
import com.tibich.chordnotepad.ui.main.UiPreferences
import com.tibich.chordnotepad.ui.requests.CloseCoordinator
import com.tibich.chordnotepad.ui.requests.RequestController
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.filterNotNull
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

    /** Finishing the activity when Back is approved, and what that leaves behind. */
    val close = CloseCoordinator(resetSession = {
        // A draft restore is refused while a song plays.
        commands.stop()
        commands.restoreDraft("", null, false)
    })

    /** Answers the session's requests (app-scoped: a rotation loses no picker result). */
    val requests = RequestController(
        pending = repository.pendingRequest,
        commands = pyHost.commands,
        adopt = documents::adopt,
        runOffMain = { block -> scope.launch(Dispatchers.IO) { block() } },
        onDiscardAnswered = close::onDiscardAnswered,
    )

    /** The editor's text and highlighting (app-scoped: survives rotation). */
    val editor = EditorController(commands)

    /** Edit or Play (app-scoped: survives rotation; follows the opened document). */
    val mode = ModeController()

    /** View-only preferences (the landscape chord sheet column's width). */
    val uiPreferences = UiPreferences(app)

    /**
     * Whether the Quick Start tour was already opened on its own since this
     * process started (main thread). Kept here, not in the UI, so a rotation
     * doesn't reopen it.
     */
    var quickStartShown: Boolean = false

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
        scope.launch { repository.document.filterNotNull().collect(mode::onDocument) }
        errorQueue.bind(scope, repository.errors)
        close.bind(scope, repository.closeApproved)
        ProcessLifecycleOwner.get().lifecycle.addObserver(AppLifecycleHooks(commands))
        PlaybackAudioPolicy(AndroidAudioFocusGateway(app), AndroidNoisyGateway(app), commands::pause)
            .bind(scope, repository.playback)
    }
}
