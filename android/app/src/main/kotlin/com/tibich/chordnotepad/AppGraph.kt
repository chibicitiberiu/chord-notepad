package com.tibich.chordnotepad

import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log
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
import com.tibich.chordnotepad.lifecycle.LaunchFacts
import com.tibich.chordnotepad.lifecycle.LaunchKind
import com.tibich.chordnotepad.lifecycle.LaunchOverrides
import com.tibich.chordnotepad.lifecycle.LocalDates
import com.tibich.chordnotepad.lifecycle.PlaybackAudioPolicy
import com.tibich.chordnotepad.ui.ErrorQueue
import com.tibich.chordnotepad.ui.editor.EditorController
import com.tibich.chordnotepad.ui.editor.bind
import com.tibich.chordnotepad.ui.main.ModeController
import com.tibich.chordnotepad.ui.main.UiPreferences
import com.tibich.chordnotepad.ui.requests.CloseCoordinator
import com.tibich.chordnotepad.ui.requests.RequestController
import com.tibich.chordnotepad.support.createSupportBilling
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
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

    /** The optional supporter purchase (app-scoped: purchase results survive rotation). */
    val supportBilling = createSupportBilling(app, scope)

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
        return Draft(text, doc?.documentId, doc?.isModified ?: false, doc?.readOnly ?: false)
    }

    // The last launch report and document job queued (main thread); each new
    // one waits for the one before, so they reach the session in order.
    private var launchJob: Job? = null
    private var documentJob: Job? = null

    /**
     * Tell the session an activity was created ([kind]), once billing is ready
     * (at most [BILLING_WAIT_MS]), so it can pick the startup screen; [intent]
     * goes to a debug build's [LaunchOverrides]. Call once per `onCreate` (main
     * thread); the session acts on the first call only.
     */
    fun reportLaunch(kind: LaunchKind, intent: Intent?) {
        val previous = launchJob
        launchJob = scope.launch {
            previous?.join()
            supportBilling.awaitReady(BILLING_WAIT_MS)
            val now = System.currentTimeMillis()
            val facts = LaunchFacts(
                today = LocalDates.iso(now),
                installedOn = LocalDates.iso(firstInstallTime() ?: now),
                canAskForSupport = supportBilling.canAskForSupport(),
            )
            val sent = LaunchOverrides.override?.adjust(intent, facts) ?: facts
            commands.appStarted(kind.wire, sent.today, sent.installedOn, sent.canAskForSupport)
        }
    }

    /**
     * Run [block] off the main thread after the document work queued before it
     * (main thread). The draft restore and Open with both go through here, so a
     * restored draft never replaces a file opened after it.
     */
    fun queueDocumentWork(block: () -> Unit) {
        val previous = documentJob
        documentJob = scope.launch(Dispatchers.IO) {
            previous?.join()
            block()
        }
    }

    private fun firstInstallTime(): Long? = try {
        val pm = app.packageManager
        val info: PackageInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            pm.getPackageInfo(app.packageName, PackageManager.PackageInfoFlags.of(0))
        } else {
            @Suppress("DEPRECATION")
            pm.getPackageInfo(app.packageName, 0)
        }
        info.firstInstallTime
    } catch (e: PackageManager.NameNotFoundException) {
        Log.w(TAG, "No package info for ${app.packageName}", e)
        null
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

    private companion object {
        const val TAG = "CNAppGraph"

        /** How long the startup screen waits for billing (Python takes about as long to start). */
        const val BILLING_WAIT_MS = 2000L
    }
}
