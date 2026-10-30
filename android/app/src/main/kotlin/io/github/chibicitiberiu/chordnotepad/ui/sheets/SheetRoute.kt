package io.github.chibicitiberiu.chordnotepad.ui.sheets

import io.github.chibicitiberiu.chordnotepad.ui.toolbar.formatPct

// Which bottom sheet or small dialog is open over the main screen, as plain
// data (saved across rotation as a string). Every picker is a bottom sheet
// (docs/design/android-ui-spec.md, "Sheets").

/** An open sheet, or [None]. */
sealed interface SheetRoute {
    /** Nothing open. */
    data object None : SheetRoute

    /** The song pill: tempo, time signature and key. */
    data object SongDefaults : SheetRoute

    /** The player's voicing button. */
    data object Voicing : SheetRoute

    /** The player's instrument button: the families ([family] null) or one family's programs. */
    data class Instrument(val family: Int? = null) : SheetRoute

    /** The player's speed button; [manual] is the typed-value dialog on top of it. */
    data class Speed(val manual: Boolean = false) : SheetRoute

    /** The ribbon's ＋ Insert. */
    data object Insert : SheetRoute

    /** Rename (the app bar's title). */
    data object Rename : SheetRoute

    /** Transpose (the ribbon), for the selection or the whole song. */
    data class Transpose(val selection: Boolean) : SheetRoute

    /** Identify (the ribbon). */
    data object Identify : SheetRoute

    /** As a string for `rememberSaveable`. */
    fun save(): String = when (this) {
        None -> ""
        SongDefaults -> "song"
        Voicing -> "voicing"
        is Instrument -> "instrument:" + (family?.toString() ?: "")
        is Speed -> if (manual) "speed:manual" else "speed"
        Insert -> "insert"
        Rename -> "rename"
        is Transpose -> if (selection) "transpose:selection" else "transpose"
        Identify -> "identify"
    }

    companion object {
        /** The route [save] wrote; anything else is [None]. */
        fun restore(saved: String): SheetRoute = when {
            saved == "song" -> SongDefaults
            saved == "voicing" -> Voicing
            saved.startsWith("instrument:") -> Instrument(saved.removePrefix("instrument:").toIntOrNull())
            saved == "speed" -> Speed()
            saved == "speed:manual" -> Speed(manual = true)
            saved == "insert" -> Insert
            saved == "rename" -> Rename
            saved == "transpose" -> Transpose(selection = false)
            saved == "transpose:selection" -> Transpose(selection = true)
            saved == "identify" -> Identify
            else -> None
        }
    }
}

/**
 * Back (the system gesture or a sheet's ←): from a family's programs to the
 * families, from the speed dialog to the speed sheet, otherwise closed.
 */
fun SheetRoute.back(): SheetRoute = when (this) {
    is SheetRoute.Instrument -> if (family != null) SheetRoute.Instrument() else SheetRoute.None
    is SheetRoute.Speed -> if (manual) SheetRoute.Speed() else SheetRoute.None
    else -> SheetRoute.None
}

/** The instrument sheet after tapping family [index]. */
fun SheetRoute.Instrument.open(index: Int): SheetRoute.Instrument = copy(family = index)

/**
 * Speed limits (percent): the slider's and the typed value's, the session's
 * (`toolbar.MULTIPLIER_SCALE`, 12.5–400 %, as on the desktop toolbar).
 */
const val SPEED_MIN_PCT = 12.5
const val SPEED_MAX_PCT = 400.0

/** The slider's step, in percent (its lowest stop is [SPEED_MIN_PCT]). */
const val SPEED_STEP_PCT = 5.0

private val SPEED_NUMBER = Regex("\\d+(\\.\\d+)?")

/**
 * The speed typed in the Manual… dialog: a number of percent from 12.5 to
 * 400 (`12.5` or `12,5`; a trailing `%` and spaces are allowed), else null.
 */
fun parseSpeedPct(text: String): Double? {
    val t = text.trim().removeSuffix("%").trim().replace(',', '.')
    if (t.isEmpty() || t.length > 7 || !SPEED_NUMBER.matches(t)) return null
    return t.toDouble().takeIf { it in SPEED_MIN_PCT..SPEED_MAX_PCT }
}

/** A speed as the sheet shows it: `125`, `12.5` (to a tenth of a percent). */
fun speedPctText(pct: Double): String = formatPct(Math.round(pct * 10.0) / 10.0)

/**
 * A slider position snapped to the 5 % grid within 12.5–400; below 15 % the
 * stops are 12.5 and 15.
 */
fun snapSpeedPct(value: Float): Double {
    val v = value.toDouble().coerceIn(SPEED_MIN_PCT, SPEED_MAX_PCT)
    val next = Math.ceil(SPEED_MIN_PCT / SPEED_STEP_PCT) * SPEED_STEP_PCT
    if (v < next) return if (v < (SPEED_MIN_PCT + next) / 2) SPEED_MIN_PCT else next
    return (Math.round(v / SPEED_STEP_PCT) * SPEED_STEP_PCT).coerceIn(SPEED_MIN_PCT, SPEED_MAX_PCT)
}

/**
 * The speed badge on the player's button: "1.25×" for 125 %, "0.5×" for
 * 50 %, "2×" for 200 %, "0.125×" for 12.5 %; null at 100 % (no badge).
 */
fun speedBadge(pct: Double): String? {
    if (Math.abs(pct - 100.0) < 0.001) return null
    val factor = Math.round(pct * 10.0) / 1000.0
    var s = "%.3f".format(java.util.Locale.ROOT, factor).trimEnd('0').trimEnd('.')
    if (s.isEmpty()) s = "0"
    return "$s×"
}
