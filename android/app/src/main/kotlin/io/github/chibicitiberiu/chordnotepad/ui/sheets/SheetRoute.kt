package io.github.chibicitiberiu.chordnotepad.ui.sheets

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

/** Speed limits (percent): the slider's and the typed value's. */
const val SPEED_MIN_PCT = 25
const val SPEED_MAX_PCT = 400

/** The slider's step, in percent. */
const val SPEED_STEP_PCT = 5

/**
 * The speed typed in the Manual… dialog: a whole number of percent from 25
 * to 400 (a trailing `%` and spaces are allowed), else null.
 */
fun parseSpeedPct(text: String): Int? {
    val t = text.trim().removeSuffix("%").trim()
    if (t.isEmpty() || !t.all(Char::isDigit) || t.length > 4) return null
    return t.toInt().takeIf { it in SPEED_MIN_PCT..SPEED_MAX_PCT }
}

/** A slider position snapped to the 5 % grid and the 25–400 range. */
fun snapSpeedPct(value: Float): Int {
    val snapped = Math.round(value / SPEED_STEP_PCT) * SPEED_STEP_PCT
    return snapped.coerceIn(SPEED_MIN_PCT, SPEED_MAX_PCT)
}

/**
 * The speed badge on the player's button: "1.25×" for 125 %, "0.5×" for
 * 50 %, "2×" for 200 %; null at 100 % (no badge).
 */
fun speedBadge(pct: Double): String? {
    if (Math.abs(pct - 100.0) < 0.001) return null
    val factor = Math.round(pct) / 100.0
    var s = "%.2f".format(java.util.Locale.ROOT, factor).trimEnd('0').trimEnd('.')
    if (s.isEmpty()) s = "0"
    return "$s×"
}
