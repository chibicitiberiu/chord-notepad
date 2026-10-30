package io.github.chibicitiberiu.chordnotepad.ui

/**
 * Compose test tags on the main screen's controls, so a test or a
 * screenshot script can find them (`Modifier.testTag`). The help
 * screenshots read them as resource ids from `uiautomator dump`
 * (android/tools/help_screenshots.py; the debug-only HelpShotActivity
 * turns on `testTagsAsResourceId`). Renaming one breaks the shot manifest
 * (android/tools/help_shots.json).
 */
object UiTags {
    const val APP_BAR = "app_bar"
    const val MENU = "menu"
    const val TITLE = "title"
    const val TAB_EDIT = "tab_edit"
    const val TAB_PLAY = "tab_play"
    const val SAVE = "save"

    const val RIBBON = "ribbon"
    const val RIBBON_UNDO = "ribbon_undo"
    const val RIBBON_REDO = "ribbon_redo"
    const val RIBBON_INSERT = "ribbon_insert"
    const val RIBBON_TRANSPOSE = "ribbon_transpose"
    const val RIBBON_IDENTIFY = "ribbon_identify"
    const val RIBBON_NOTATION = "ribbon_notation"
    const val RIBBON_CONVERT = "ribbon_convert"
    const val RIBBON_MORE = "ribbon_more"
    const val UNDO_CHIP = "undo_chip"

    const val EDITOR = "editor"
    const val HINT_STRIP = "hint_strip"
    const val HINT_POPUP = "hint_popup"

    const val PLAYER = "player"
    const val PLAYER_PILL = "player_pill"
    const val PLAYER_VOICING = "player_voicing"
    const val PLAYER_INSTRUMENT = "player_instrument"
    const val PLAYER_REWIND = "player_rewind"
    const val PLAYER_PLAY = "player_play"
    const val PLAYER_METRONOME = "player_metronome"
    const val PLAYER_SPEED = "player_speed"
    const val PLAYER_SHEET = "player_sheet"
    const val PLAYER_STATUS = "player_status"

    const val CHORD_SHEET = "chord_sheet"
    const val CHORD_SHEET_TABS = "chord_sheet_tabs"
    const val CHORD_SHEET_ZOOM = "chord_sheet_zoom"
    const val CHORD_SHEET_HANDLE = "chord_sheet_handle"
    const val SIDE_HANDLE = "side_handle"

    const val DRAWER = "drawer"
}
