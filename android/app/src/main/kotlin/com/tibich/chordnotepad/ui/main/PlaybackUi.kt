package com.tibich.chordnotepad.ui.main

import com.tibich.chordnotepad.bridge.PlaybackState
import com.tibich.chordnotepad.bridge.PlaybackStatus

/** The player's height in dp (divider, pill, buttons, status line). */
const val PLAYER_HEIGHT_DP = 110f

/**
 * True from Play until the first chord sounds: the session renders the whole
 * song before the first note (slow devices take a while), so it reports
 * `playing` with no chord yet. A resume keeps its chord, so it never counts.
 */
val PlaybackState?.isStarting: Boolean
    get() = this != null && status == PlaybackStatus.PLAYING && chordIndex == null

/** The screen stays on while a song plays or starts; a pause, stop or the end releases it. */
fun keepScreenOn(playback: PlaybackState?): Boolean = playback?.status == PlaybackStatus.PLAYING

/** Edit mode shows the session's status messages as snackbars; Play shows them on the player's status line. */
fun statusSnackbarsShown(mode: AppMode): Boolean = mode == AppMode.EDIT

/**
 * How far above the bottom of the screen a snackbar sits so it clears the
 * player (error snackbars show in Play too). Side by side, the player is a
 * column beside the text and the bottom is free.
 */
fun snackbarClearanceDp(mode: AppMode, sideBySide: Boolean): Float =
    if (mode == AppMode.PLAY && !sideBySide) PLAYER_HEIGHT_DP else 0f
