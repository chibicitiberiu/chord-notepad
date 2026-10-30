package com.tibich.chordnotepad.debug

import android.content.ContentProvider
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.database.Cursor
import android.net.Uri
import android.util.Log
import androidx.core.content.edit
import com.tibich.chordnotepad.lifecycle.LaunchFacts
import com.tibich.chordnotepad.lifecycle.LaunchFactsOverride
import com.tibich.chordnotepad.lifecycle.LaunchOverrides

/**
 * Debug builds only: fake what `app_started` reports, to check the support
 * prompt on an emulator (which has no Play Store, so billing never offers it).
 * Pass extras to a launch that starts the process (`am force-stop` first: a
 * running app gets the intent in `onNewIntent`, which reports no launch);
 * they are kept until `debug_reset`:
 *
 * ```
 * adb shell am start -n com.tibich.chordnotepad/.MainActivity -a android.intent.action.MAIN \
 *     --es debug_today 2026-11-06 --es debug_installed_on 2026-10-30 --ez debug_can_ask true
 * adb shell am start -n com.tibich.chordnotepad/.MainActivity --ez debug_reset true
 * ```
 */
class DebugLaunchOverride(private val prefs: SharedPreferences) : LaunchFactsOverride {
    override fun adjust(intent: Intent?, facts: LaunchFacts): LaunchFacts {
        if (intent != null) remember(intent)
        val adjusted = LaunchFacts(
            today = prefs.getString(TODAY, null) ?: facts.today,
            installedOn = prefs.getString(INSTALLED_ON, null) ?: facts.installedOn,
            canAskForSupport = if (prefs.contains(CAN_ASK)) prefs.getBoolean(CAN_ASK, false) else facts.canAskForSupport,
        )
        if (adjusted != facts) Log.i(TAG, "Launch facts overridden: $adjusted (real: $facts)")
        return adjusted
    }

    private fun remember(intent: Intent) = prefs.edit {
        if (intent.getBooleanExtra(RESET, false)) clear()
        intent.getStringExtra(TODAY)?.let { putString(TODAY, it) }
        intent.getStringExtra(INSTALLED_ON)?.let { putString(INSTALLED_ON, it) }
        if (intent.hasExtra(CAN_ASK)) putBoolean(CAN_ASK, intent.getBooleanExtra(CAN_ASK, false))
    }

    private companion object {
        const val TAG = "CNDebugLaunch"
        const val TODAY = "debug_today"
        const val INSTALLED_ON = "debug_installed_on"
        const val CAN_ASK = "debug_can_ask"
        const val RESET = "debug_reset"
    }
}

/** Installs [DebugLaunchOverride] when the process starts (a provider's onCreate runs before any activity). */
class DebugLaunchOverrideProvider : ContentProvider() {
    override fun onCreate(): Boolean {
        val prefs = context!!.getSharedPreferences("debug_launch", Context.MODE_PRIVATE)
        LaunchOverrides.override = DebugLaunchOverride(prefs)
        return true
    }

    override fun query(
        uri: Uri, projection: Array<out String>?, selection: String?, selectionArgs: Array<out String>?,
        sortOrder: String?,
    ): Cursor? = null

    override fun getType(uri: Uri): String? = null

    override fun insert(uri: Uri, values: ContentValues?): Uri? = null

    override fun delete(uri: Uri, selection: String?, selectionArgs: Array<out String>?): Int = 0

    override fun update(uri: Uri, values: ContentValues?, selection: String?, selectionArgs: Array<out String>?): Int = 0
}
