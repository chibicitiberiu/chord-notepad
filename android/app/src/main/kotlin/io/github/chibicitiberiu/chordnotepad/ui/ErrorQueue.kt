package io.github.chibicitiberiu.chordnotepad.ui

import io.github.chibicitiberiu.chordnotepad.bridge.SessionError
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * The session's errors waiting to be shown, collected app-wide so none is
 * lost while the activity is being recreated (the repository's error flow
 * keeps nothing for late collectors). The screen shows the first one and
 * [dismiss]es it.
 *
 * @param limit Older errors are dropped beyond this many.
 */
class ErrorQueue(private val limit: Int = 20) {
    private val _items = MutableStateFlow<List<QueuedError>>(emptyList())
    private var nextId = 0L

    /** Errors not dismissed yet, oldest first. */
    val items: StateFlow<List<QueuedError>> = _items.asStateFlow()

    /** Start collecting [errors] in [scope]. */
    fun bind(scope: CoroutineScope, errors: Flow<SessionError>): Job = scope.launch { errors.collect(::add) }

    /** Queue one error. */
    fun add(error: SessionError) {
        val queued = synchronized(this) { QueuedError(nextId++, error) }
        _items.update { (it + queued).takeLast(limit) }
    }

    /** The user saw [error]. */
    fun dismiss(error: QueuedError) {
        _items.update { list -> list.filterNot { it.id == error.id } }
    }
}

/** A queued error; [id] tells two equal errors apart. */
data class QueuedError(val id: Long, val error: SessionError)
