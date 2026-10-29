package io.github.chibicitiberiu.chordnotepad.bridge

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SessionRepositoryTest {
    private val repo = SessionRepository()

    @Test
    fun `states land in their flows, latest wins`() {
        assertNull(repo.status.value)
        repo.publish(StatusState("one"))
        repo.publish(StatusState("two"))
        repo.publish(PlaybackState(PlaybackStatus.PLAYING, bar = 2, totalBars = 8))
        assertEquals("two", repo.status.value?.text)
        assertEquals(PlaybackStatus.PLAYING, repo.playback.value?.status)
        repo.publish(RecentDocumentsState(listOf(DocumentRef("a", "a", "a"))))
        assertEquals(1, repo.recentDocuments.value?.items?.size)
    }

    @Test
    fun `text edits keep their order and wait for a collector`() = runTest {
        val edits = (1..3).map { TextEdited(it, 0, 0, "x$it", UndoPolicy.PLAIN, 0) }
        edits.forEach(repo::publish) // before anyone collects
        assertEquals(edits, repo.textEdits.take(3).toList())
    }

    @Test
    fun `a newer request replaces the pending one, answering clears only the matching id`() {
        repo.publish(ConfirmDiscardRequest(1))
        repo.publish(PickDocumentRequest(2, PickMode.OPEN, ""))
        assertEquals(2, repo.pendingRequest.value?.requestId)
        repo.requestAnswered(1) // stale answer
        assertEquals(2, repo.pendingRequest.value?.requestId)
        repo.requestAnswered(2)
        assertNull(repo.pendingRequest.value)
    }

    @Test
    fun `song defaults and failed renames have their flows`() = runTest(UnconfinedTestDispatcher()) {
        val defaults = SongDefaultsState(
            SongDefault("90", true, 0), SongDefault("3/4", false), SongDefault("", false), "90 · 3/4",
        )
        repo.publish(defaults)
        assertEquals(defaults, repo.songDefaults.value)
        val failures = mutableListOf<RenameFailed>()
        backgroundScope.launch { repo.renameFailed.collect { failures += it } }
        repo.publish(RenameFailed("a/b", "A name can't contain / or \\.", canSaveAs = false))
        assertEquals(listOf("a/b"), failures.map { it.name })
    }

    @Test
    fun `errors and close go to their shared flows`() = runTest(UnconfinedTestDispatcher()) {
        val errors = mutableListOf<SessionError>()
        var closed = 0
        backgroundScope.launch { repo.errors.collect { errors += it } }
        backgroundScope.launch { repo.closeApproved.collect { closed++ } }
        repo.publish(UserError("Error", "Failed to read file"))
        repo.publish(AudioUnavailable("No audio", fromClick = true))
        repo.publish(UnexpectedError("boom"))
        repo.publish(CloseApproved)
        assertEquals(3, errors.size)
        assertEquals(1, closed)
    }
}
