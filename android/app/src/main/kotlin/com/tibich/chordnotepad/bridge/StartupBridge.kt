package com.tibich.chordnotepad.bridge

import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// The startup screen (docs/design/android-support-plan.md; contract in
// docs/ANDROID.md, "Bridge contract", "Startup screen"). Mirrors
// src/session/state.py: the session decides what opens over the editor.

/** What opens over the editor at startup. */
@Serializable
enum class StartupScreen {
    @SerialName("none") NONE,
    @SerialName("quick_start") QUICK_START,

    /** The request for the optional supporter purchase. */
    @SerialName("support_prompt") SUPPORT_PROMPT,
}

/**
 * The answer to the session's first `app_started`; back to [StartupScreen.NONE]
 * after `dismiss_startup_screen`. Null in the repository until then.
 */
@Serializable
data class StartupState(val screen: StartupScreen) : SessionState

/** Wire type name → serializer for these outputs ([BridgeCodec.serializers] includes them). */
internal val startupSerializers: Map<String, KSerializer<out SessionOutput>> = mapOf(
    "StartupState" to StartupState.serializer(),
)
