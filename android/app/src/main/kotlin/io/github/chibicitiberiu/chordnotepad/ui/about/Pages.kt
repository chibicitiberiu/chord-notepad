package io.github.chibicitiberiu.chordnotepad.ui.about

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

    /** Help › Quick Start (also opens on its own the first time, see `QuickStartLaunch`). */
    const val QUICK_START = "quick_start"

    /** ☰ drawer › Settings (its own pages are inside `SettingsScreen`; Back there is its own). */
    const val SETTINGS = "settings"

    /** Settings opened at Voicings (the Voicing sheet's "Edit voicings…"). */
    const val SETTINGS_VOICINGS = "settings/voicings"

    private const val DETAIL = "licence/"

    /** The page of licence entry [id]. */
    fun detail(id: String) = DETAIL + id

    /** The licence entry id of [page], or null when it isn't a licence page. */
    fun detailId(page: String): String? = page.takeIf { it.startsWith(DETAIL) }?.removePrefix(DETAIL)

    /** The page Back goes to from [page]. */
    fun parent(page: String): String = when {
        detailId(page) != null -> LICENCES
        page == LICENCES -> ABOUT
        else -> MAIN
    }
}
