package com.tibich.chordnotepad.lifecycle

import com.tibich.chordnotepad.bridge.PlaybackState
import com.tibich.chordnotepad.bridge.PlaybackStatus
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch

/** Audio focus, as [PlaybackAudioPolicy] needs it. */
interface AudioFocusGateway {
    /**
     * Ask for music focus; [onLoss] runs (on the main thread) when another app
     * takes it, for good or for a while.
     *
     * @return Whether focus was granted.
     */
    fun request(onLoss: () -> Unit): Boolean

    /** Give focus back (no-op if not held). */
    fun abandon()
}

/** The "audio becoming noisy" broadcast (headphones unplugged). */
interface NoisyGateway {
    /** Start listening; [onNoisy] runs on the main thread. Idempotent. */
    fun register(onNoisy: () -> Unit)

    /** Stop listening (no-op if not registered). */
    fun unregister()
}

/**
 * Plays by Android's audio rules, driven by `PlaybackState`:
 * - entering PLAYING asks for audio focus (denied → pause) and starts
 *   listening for "becoming noisy";
 * - losing focus or the headphones → [pause];
 * - back to IDLE abandons focus and stops listening. PAUSED keeps both, so a
 *   resume doesn't ask again: a second request from the same app makes the
 *   system send the first one a focus loss, which paused the song at once.
 *   After a real loss, the next resume does ask.
 *
 * Ducking is left to the system (Android 8+ ducks music on its own).
 *
 * @param pause Sends the session's `pause` host command.
 */
class PlaybackAudioPolicy(
    private val focus: AudioFocusGateway,
    private val noisy: NoisyGateway,
    private val pause: () -> Unit,
) {
    private var last: PlaybackStatus = PlaybackStatus.IDLE
    private var engaged = false
    private var focusHeld = false

    /** Follow [playback] in [scope] (main thread). */
    fun bind(scope: CoroutineScope, playback: StateFlow<PlaybackState?>): Job = scope.launch {
        playback.map { it?.status ?: PlaybackStatus.IDLE }.distinctUntilChanged().collect(::onStatus)
    }

    /** React to a new transport status. */
    fun onStatus(status: PlaybackStatus) {
        val previous = last
        last = status
        when (status) {
            PlaybackStatus.PLAYING -> if (previous != PlaybackStatus.PLAYING) startPlaying()
            PlaybackStatus.PAUSED -> Unit
            PlaybackStatus.IDLE -> if (engaged) release()
        }
    }

    private fun startPlaying() {
        engaged = true
        noisy.register(pause)
        if (focusHeld) return // a resume after pause: asking again would take focus from ourselves
        focusHeld = focus.request(onLoss = {
            focusHeld = false
            pause()
        })
        if (!focusHeld) pause()
    }

    private fun release() {
        engaged = false
        focusHeld = false
        focus.abandon()
        noisy.unregister()
    }
}
