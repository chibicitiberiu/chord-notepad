package io.github.chibicitiberiu.chordnotepad.bridge

import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.flow.update

/** Whether the Python session is up. */
sealed interface HostStatus {
    /** [PyHost.start] not called yet. */
    data object NotStarted : HostStatus

    /** Python and the session are starting (a few seconds on a cold start). */
    data object Starting : HostStatus

    /** The session runs; commands reach it. */
    data object Running : HostStatus

    /** Starting failed; commands are dropped. */
    data class Failed(val message: String) : HostStatus

    /** [PyHost.shutdown] ran. */
    data object Stopped : HostStatus
}

/**
 * The session's output as flows, for the UI. App-scoped (it outlives
 * activities, so rotation loses nothing).
 *
 * - Each state is a [StateFlow], null until the session first publishes it
 *   (it replays every state when it starts).
 * - [textEdits] is unbounded and meant for one collector, the editor, which
 *   applies each edit inside `TextFieldState.edit {}`.
 * - [pendingRequest] holds the request waiting for an answer, so it survives
 *   rotation; answering through [SessionCommands] clears it.
 * - [errors] is hot: only collectors present at the time get an error.
 *
 * [publish] is called on the Python session thread; everything it does is
 * non-blocking.
 */
class SessionRepository {
    private val _document = MutableStateFlow<DocumentState?>(null)
    private val _editor = MutableStateFlow<EditorState?>(null)
    private val _highlight = MutableStateFlow<HighlightState?>(null)
    private val _playback = MutableStateFlow<PlaybackState?>(null)
    private val _toolbar = MutableStateFlow<ToolbarState?>(null)
    private val _status = MutableStateFlow<StatusState?>(null)
    private val _voicingMenu = MutableStateFlow<VoicingMenuState?>(null)
    private val _instrumentMenu = MutableStateFlow<InstrumentMenuState?>(null)
    private val _recentDocuments = MutableStateFlow<RecentDocumentsState?>(null)
    private val _chordSheet = MutableStateFlow<ChordSheetState?>(null)
    private val _hostStatus = MutableStateFlow<HostStatus>(HostStatus.NotStarted)
    private val _pendingRequest = MutableStateFlow<SessionRequest?>(null)
    private val _textEdits = Channel<TextEdited>(Channel.UNLIMITED)
    private val _errors = MutableSharedFlow<SessionError>(
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    private val _closeApproved = MutableSharedFlow<Unit>(
        extraBufferCapacity = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )

    /** The open document (title, modified flag). */
    val document: StateFlow<DocumentState?> = _document.asStateFlow()

    /** Editor font, read-only flag and notation. */
    val editor: StateFlow<EditorState?> = _editor.asStateFlow()

    /** Highlight spans for the latest text the session has. */
    val highlight: StateFlow<HighlightState?> = _highlight.asStateFlow()

    /** Transport status and the chord sounding. */
    val playback: StateFlow<PlaybackState?> = _playback.asStateFlow()

    /** Toolbar values. */
    val toolbar: StateFlow<ToolbarState?> = _toolbar.asStateFlow()

    /** The status line. */
    val status: StateFlow<StatusState?> = _status.asStateFlow()

    /** The voicing menu. */
    val voicingMenu: StateFlow<VoicingMenuState?> = _voicingMenu.asStateFlow()

    /** The instrument menu. */
    val instrumentMenu: StateFlow<InstrumentMenuState?> = _instrumentMenu.asStateFlow()

    /** Recent documents. */
    val recentDocuments: StateFlow<RecentDocumentsState?> = _recentDocuments.asStateFlow()

    /** The chord-sheet strip. */
    val chordSheet: StateFlow<ChordSheetState?> = _chordSheet.asStateFlow()

    /** Whether Python is up. */
    val hostStatus: StateFlow<HostStatus> = _hostStatus.asStateFlow()

    /** The request waiting for an answer, or null. A newer request replaces an older one. */
    val pendingRequest: StateFlow<SessionRequest?> = _pendingRequest.asStateFlow()

    /** Programmatic edits, in order (one collector). */
    val textEdits: Flow<TextEdited> = _textEdits.receiveAsFlow()

    /** Errors to show (user errors, audio unavailable, unexpected errors). */
    val errors: SharedFlow<SessionError> = _errors.asSharedFlow()

    /** The session approved closing the app. */
    val closeApproved: SharedFlow<Unit> = _closeApproved.asSharedFlow()

    /** Route one output to its flow. Non-blocking; safe on any thread. */
    fun publish(output: SessionOutput) {
        when (output) {
            is DocumentState -> _document.value = output
            is EditorState -> _editor.value = output
            is HighlightState -> _highlight.value = output
            is PlaybackState -> _playback.value = output
            is ToolbarState -> _toolbar.value = output
            is StatusState -> _status.value = output
            is VoicingMenuState -> _voicingMenu.value = output
            is InstrumentMenuState -> _instrumentMenu.value = output
            is RecentDocumentsState -> _recentDocuments.value = output
            is ChordSheetState -> _chordSheet.value = output
            is TextEdited -> _textEdits.trySend(output)
            is SessionRequest -> _pendingRequest.value = output
            is SessionError -> _errors.tryEmit(output)
            CloseApproved -> _closeApproved.tryEmit(Unit)
        }
    }

    /** The view answered [requestId]; forget it if it's still the pending one. */
    fun requestAnswered(requestId: Int) {
        _pendingRequest.update { if (it?.requestId == requestId) null else it }
    }

    /** Set by [PyHost]. */
    internal fun setHostStatus(status: HostStatus) {
        _hostStatus.value = status
    }
}
