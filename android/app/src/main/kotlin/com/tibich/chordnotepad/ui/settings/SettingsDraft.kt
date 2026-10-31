package com.tibich.chordnotepad.ui.settings

import com.tibich.chordnotepad.bridge.SettingsState
import com.tibich.chordnotepad.bridge.SettingsValues
import com.tibich.chordnotepad.ui.editor.EditorFontKind
import com.tibich.chordnotepad.ui.editor.configFamilyFor
import com.tibich.chordnotepad.ui.editor.fontKindFor
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
    /** What `commit_settings` sends. */
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

    /** Switch notation; the key stays (it is American, only its spelling on screen changes). */
    fun withNotation(notation: String): SettingsDraft = copy(notation = notation)

    companion object {
        /** The draft of [state]'s values (the key in American spelling, as Python sends it). */
        fun of(state: SettingsState): SettingsDraft {
            val v = state.values
            return SettingsDraft(
                configuredFamily = v.fontFamily,
                fontKind = fontKindFor(v.fontFamily),
                fontSize = v.fontSize,
                notation = v.notation,
                key = respellKey(v.key, AMERICAN, state),
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

/** How [key] (American, as the draft and config keep it) shows in [notation]: Sol for G in European. */
fun shownKey(key: String, notation: String, limits: SettingsState): String = respellKey(key, notation, limits)

/** [key] spelled in [notation]: kept if it's one of its keys, else mapped by position, else "". */
fun respellKey(key: String, notation: String, limits: SettingsState): String {
    if (key.isEmpty()) return ""
    val target = keysFor(notation, limits)
    if (key in target) return key
    val other = if (notation == EUROPEAN) limits.americanKeys else limits.europeanKeys
    return other.indexOf(key).takeIf { it >= 0 }?.let { target.getOrNull(it) } ?: ""
}

/**
 * The whole numbers the number fields of the General and Playback pages
 * accept, in page order. [key] is the setting's name in Python
 * (`SettingsValues`, `NUMBER_SETTINGS`), [page] the page it is on.
 */
enum class NumberSetting(val key: String, val page: SettingsPage) {
    FONT_SIZE("font_size", SettingsPage.GENERAL),
    MAX_RECENT_FILES("max_recent_files", SettingsPage.GENERAL),
    BPM("bpm", SettingsPage.PLAYBACK),
    TIME_SIGNATURE_BEATS("time_signature_beats", SettingsPage.PLAYBACK),
    ;

    companion object {
        /** [texts] keyed by [key], as settings (unknown keys are skipped). */
        fun fromKeys(texts: Map<String, String>): Map<NumberSetting, String> =
            entries.mapNotNull { setting -> texts[setting.key]?.let { setting to it } }.toMap()
    }

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
