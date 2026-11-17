package com.tibich.chordnotepad.bridge

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// Suggest Capo (contract in docs/ANDROID.md, "Bridge contract", "Suggest Capo"). Mirrors
// core/chordnotepad/session/state.py: the session scores the capos and holds the dialog;
// the view shows this state and sends capo_advice_* commands.

/**
 * One capo position in the list.
 *
 * @property capo The fret (0 for no capo); send it with `capoAdviceApply`.
 * @property label The row in words: `Capo 3 · G D Em C · Easier`, or `No capo · Bb F Gm Eb`.
 * @property shapes The shapes the chords are played with on this capo.
 * @property ease `Easier`, `Harder` or `About the same` against no capo; `No capo` for 0.
 * @property recommended The capo Suggest Capo recommends (the first row).
 * @property current The capo already in force where it would go.
 */
@Serializable
data class CapoRow(
    val capo: Int,
    val label: String,
    val shapes: String,
    val ease: String,
    val recommended: Boolean,
    val current: Boolean,
)

/**
 * The Suggest Capo dialog, open while [active]. [status] is `computing`
 * (show a spinner), `ready` or `error`; [message] is the error, or that
 * there are no chords in range. While [playing], Apply is refused (show it
 * disabled with a hint). [rows] come with the recommended one first.
 */
@Serializable
data class CapoAdviceState(
    val active: Boolean,
    val scope: String,
    val voicings: List<MenuItem>,
    val voicing: String,
    val status: String,
    val message: String,
    val playing: Boolean,
    val rows: List<CapoRow>,
) : SessionState {
    /** Whether the capos are being scored. */
    val computing: Boolean get() = status == COMPUTING

    companion object {
        const val COMPUTING = "computing"
        const val READY = "ready"
        const val ERROR = "error"
    }
}

/** Wire type name → serializer for these outputs ([BridgeCodec.serializers] includes them). */
internal val capoSerializers: Map<String, KSerializer<out SessionOutput>> = mapOf(
    "CapoAdviceState" to CapoAdviceState.serializer(),
)
