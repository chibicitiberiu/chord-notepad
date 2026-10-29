package io.github.chibicitiberiu.chordnotepad.ui.settings

import io.github.chibicitiberiu.chordnotepad.bridge.SettingsState
import io.github.chibicitiberiu.chordnotepad.bridge.SettingsValues
import io.github.chibicitiberiu.chordnotepad.ui.editor.EditorFontKind
import io.github.chibicitiberiu.chordnotepad.ui.editor.configFamilyFor
import io.github.chibicitiberiu.chordnotepad.ui.editor.fontKindFor
import kotlinx.serialization.Serializable

/** Notation values (`SettingsValues.notation`). */
const val AMERICAN = "american"

/** See [AMERICAN]. */
const val EUROPEAN = "european"

/**
 * The General and Playback pages' working values. The font family is a kind
 * (Monospace, Sans, Serif: the settings visibility rule); [configuredFamily]
 * is what the config had, kept when the kind doesn't change ([toValues]).
 */
@Serializable
data class SettingsDraft(
    val configuredFamily: String,
    val fontKind: EditorFontKind,
    val fontSize: Int,
    val notation: String,
    val key: String,
    val showQuickStartOnStartup: Boolean,
    val maxRecentFiles: Int,
    val bpm: Int,
    val timeSignatureBeats: Int,
    val timeSignatureUnit: Int,
) {
    /** What `save_settings` sends. */
    fun toValues(): SettingsValues = SettingsValues(
        fontFamily = configFamilyFor(fontKind, configuredFamily),
        fontSize = fontSize,
        notation = notation,
        key = key,
        showQuickStartOnStartup = showQuickStartOnStartup,
        maxRecentFiles = maxRecentFiles,
        bpm = bpm,
        timeSignatureBeats = timeSignatureBeats,
        timeSignatureUnit = timeSignatureUnit,
    )

    /**
     * Switch notation, respelling the key (the two key lists are parallel:
     * C ↔ Do, C# ↔ Do#...). An unknown key becomes "" (none).
     */
    fun withNotation(notation: String, limits: SettingsState): SettingsDraft {
        if (notation == this.notation) return this
        return copy(notation = notation, key = respellKey(key, notation, limits))
    }

    companion object {
        /** The draft of [state]'s values (a key that doesn't fit the notation is respelled). */
        fun of(state: SettingsState): SettingsDraft {
            val v = state.values
            return SettingsDraft(
                configuredFamily = v.fontFamily,
                fontKind = fontKindFor(v.fontFamily),
                fontSize = v.fontSize,
                notation = v.notation,
                key = respellKey(v.key, v.notation, state),
                showQuickStartOnStartup = v.showQuickStartOnStartup,
                maxRecentFiles = v.maxRecentFiles,
                bpm = v.bpm,
                timeSignatureBeats = v.timeSignatureBeats,
                timeSignatureUnit = v.timeSignatureUnit,
            )
        }
    }
}

/** The key choices of [notation] ("" = none comes first in the UI). */
fun keysFor(notation: String, limits: SettingsState): List<String> =
    if (notation == EUROPEAN) limits.europeanKeys else limits.americanKeys

/** [key] spelled in [notation]: kept if it's one of its keys, else mapped by position, else "". */
fun respellKey(key: String, notation: String, limits: SettingsState): String {
    if (key.isEmpty()) return ""
    val target = keysFor(notation, limits)
    if (key in target) return key
    val other = if (notation == EUROPEAN) limits.americanKeys else limits.europeanKeys
    return other.indexOf(key).takeIf { it >= 0 }?.let { target.getOrNull(it) } ?: ""
}

/** The whole numbers the number fields of the General and Playback pages accept. */
enum class NumberSetting {
    FONT_SIZE,
    MAX_RECENT_FILES,
    BPM,
    TIME_SIGNATURE_BEATS,
    ;

    /** The accepted range ([limits] from `SettingsState`). */
    fun range(limits: SettingsState): IntRange = when (this) {
        FONT_SIZE -> limits.fontSizeMin..limits.fontSizeMax
        MAX_RECENT_FILES -> 1..limits.maxRecentFilesMax
        BPM -> limits.bpmMin..limits.bpmMax
        TIME_SIGNATURE_BEATS -> 1..16
    }

    /** The value in [draft]. */
    fun get(draft: SettingsDraft): Int = when (this) {
        FONT_SIZE -> draft.fontSize
        MAX_RECENT_FILES -> draft.maxRecentFiles
        BPM -> draft.bpm
        TIME_SIGNATURE_BEATS -> draft.timeSignatureBeats
    }

    /** [draft] with [value]. */
    fun set(draft: SettingsDraft, value: Int): SettingsDraft = when (this) {
        FONT_SIZE -> draft.copy(fontSize = value)
        MAX_RECENT_FILES -> draft.copy(maxRecentFiles = value)
        BPM -> draft.copy(bpm = value)
        TIME_SIGNATURE_BEATS -> draft.copy(timeSignatureBeats = value)
    }
}
