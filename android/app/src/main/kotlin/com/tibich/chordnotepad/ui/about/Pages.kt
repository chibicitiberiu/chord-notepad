package com.tibich.chordnotepad.ui.about

/**
 * Which full-screen page is open over the editor, as a string so it survives
 * rotation in `rememberSaveable`: [MAIN] (none), [ABOUT], [LICENCES], or a
 * licence's text ([detail]).
 */
object Pages {
    /** The editor. */
    const val MAIN = ""

    /** Help > About. */
    const val ABOUT = "about"

    /** The open source licences list. */
    const val LICENCES = "licences"

    /** Help › User Guide (the offline WebView; it handles Back itself). */
    const val USER_GUIDE = "user_guide"

    /** Help › Quick Start (also opens on its own when the session's StartupState says so). */
    const val QUICK_START = "quick_start"

    /** ☰ drawer › Settings (its own pages are inside `SettingsScreen`; Back there is its own). */
    const val SETTINGS = "settings"

    /** Settings opened at Voicings (the Voicing sheet's "Edit voicings…"). */
    const val SETTINGS_VOICINGS = "settings/voicings"

    private const val DETAIL = "licence/"

    /** A licence's text opened from About itself (the app's own licence). */
    private const val ABOUT_DETAIL = "about-licence/"

    /**
     * The page of licence entry [id], from the licences list, or from About
     * when [fromAbout] (Back then goes to About, not to a list never opened: P7).
     */
    fun detail(id: String, fromAbout: Boolean = false) = (if (fromAbout) ABOUT_DETAIL else DETAIL) + id

    /** The licence entry id of [page], or null when it isn't a licence page. */
    fun detailId(page: String): String? = when {
        page.startsWith(DETAIL) -> page.removePrefix(DETAIL)
        page.startsWith(ABOUT_DETAIL) -> page.removePrefix(ABOUT_DETAIL)
        else -> null
    }

    /** The page Back goes to from [page]. */
    fun parent(page: String): String = when {
        page.startsWith(ABOUT_DETAIL) -> ABOUT
        detailId(page) != null -> LICENCES
        page == LICENCES -> ABOUT
        else -> MAIN
    }

    /**
     * What a song that was asked to open (Open with from another app) does
     * to [page] once it arrives: it lands on the main screen in Play (P1).
     */
    fun onSongOpened(page: String): SongOpened = when (page) {
        MAIN -> SongOpened.STAY
        SETTINGS, SETTINGS_VOICINGS -> SongOpened.LEAVE_SETTINGS
        else -> SongOpened.CLOSE
    }
}

/** See [Pages.onSongOpened]. */
enum class SongOpened {
    /** Already on the main screen. */
    STAY,

    /** Close the page. */
    CLOSE,

    /** Leave Settings as Back does: it asks first while a value is wrong. */
    LEAVE_SETTINGS,
}
