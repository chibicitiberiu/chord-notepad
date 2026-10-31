package com.tibich.chordnotepad.lifecycle

import android.content.Intent
import java.util.Calendar
import java.util.Locale
import java.util.TimeZone

/**
 * How an activity came up, sent as `app_started`'s `launch_kind`. The session
 * decides the startup screen from the first one (docs/ANDROID.md, "Startup screen and support prompt").
 */
enum class LaunchKind(val wire: String) {
    /** The launcher, or the recents list: may show Quick Start or the support prompt. */
    DIRECT("direct"),

    /** Open with: a file to show, nothing over it. */
    DOCUMENT("document"),

    /** Recreated (rotation, process death), a debug activity, anything else: nothing over it. */
    RESTORE("restore"),
}

/** Pure launch rules, kept apart from the activity so JVM tests cover them. */
object LaunchRules {
    /**
     * Classify an activity creation.
     *
     * @param restored `savedInstanceState != null`.
     * @param action The intent's action (null when there's no intent or action).
     * @param flags The intent's flags.
     */
    fun classify(restored: Boolean, action: String?, flags: Int): LaunchKind = when {
        restored -> LaunchKind.RESTORE
        action == Intent.ACTION_MAIN || fromHistory(flags) -> LaunchKind.DIRECT
        action == Intent.ACTION_VIEW -> LaunchKind.DOCUMENT
        else -> LaunchKind.RESTORE
    }

    /**
     * Whether an intent is a file to open now: a `content:` VIEW that isn't
     * the recents list replaying the intent that started the task, and not
     * the intent a recreated activity got back.
     *
     * @param restored `savedInstanceState != null` (false for `onNewIntent`).
     * @param scheme The intent data's scheme, or null without data.
     */
    fun shouldOpen(restored: Boolean, action: String?, flags: Int, scheme: String?): Boolean =
        !restored && action == Intent.ACTION_VIEW && !fromHistory(flags) && scheme == "content"

    private fun fromHistory(flags: Int) = (flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY) != 0
}

/** Local calendar dates as ISO strings (`2026-10-30`); minSdk 24 has no java.time. */
object LocalDates {
    /** The local date of [millis] (epoch milliseconds) in [zone]. */
    fun iso(millis: Long, zone: TimeZone = TimeZone.getDefault()): String {
        val c = Calendar.getInstance(zone)
        c.timeInMillis = millis
        return String.format(
            Locale.ROOT, "%04d-%02d-%02d",
            c.get(Calendar.YEAR), c.get(Calendar.MONTH) + 1, c.get(Calendar.DAY_OF_MONTH),
        )
    }
}

/**
 * What `app_started` reports besides the launch kind.
 *
 * @property today Today's local date (ISO).
 * @property installedOn The local date of the first install (ISO).
 * @property canAskForSupport `SupportBilling.canAskForSupport()`.
 */
data class LaunchFacts(val today: String, val installedOn: String, val canAskForSupport: Boolean)

/** Changes [LaunchFacts] before they are sent: debug builds fake the dates (src/debug). */
fun interface LaunchFactsOverride {
    /** The facts to send for a launch by [intent] (null for activities without one). */
    fun adjust(intent: Intent?, facts: LaunchFacts): LaunchFacts
}

/** Where a debug build installs its [LaunchFactsOverride]; always null in release builds. */
object LaunchOverrides {
    @Volatile
    var override: LaunchFactsOverride? = null
}
