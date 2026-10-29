package io.github.chibicitiberiu.chordnotepad.ui.main

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit

/**
 * View-only preferences the session doesn't keep: the landscape chord sheet
 * column's width. (The portrait sheet's height is the session's
 * `set_chord_sheet_height`, shared with the desktop's sash; a column width
 * has no desktop counterpart, so it stays on the device, in
 * `shared_prefs/ui.xml`, outside the backed-up config.)
 */
class UiPreferences(context: Context) {
    private val prefs: SharedPreferences = context.getSharedPreferences("ui", Context.MODE_PRIVATE)

    /** The landscape chord sheet column's share of the width, 30–70 %. */
    var sideFraction: Float
        get() = clampSideFraction(prefs.getFloat(SIDE_FRACTION, SIDE_FRACTION_DEFAULT))
        set(value) = prefs.edit { putFloat(SIDE_FRACTION, clampSideFraction(value)) }

    private companion object {
        const val SIDE_FRACTION = "side_fraction"
    }
}
