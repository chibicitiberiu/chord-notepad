package io.github.chibicitiberiu.chordnotepad.ui.tools

import io.github.chibicitiberiu.chordnotepad.bridge.CapoChoiceRequest
import io.github.chibicitiberiu.chordnotepad.bridge.InsertDirectiveRequest
import io.github.chibicitiberiu.chordnotepad.bridge.Selection
import io.github.chibicitiberiu.chordnotepad.text.OffsetMapper

// The Tools dialogs' values, as plain data: what each dialog holds and the
// answer it sends. The rules (which BPM forms are valid, duplicate labels)
// stay in Python (session/directives.py): a bad answer comes back as a
// UserError. Only the pickers' ranges are mirrored from the desktop's
// spinboxes (Transpose −11..+11, beats 1–16, loop count 1–100), so a picker
// can't offer a value the desktop couldn't.

/**
 * The editor's selection `[start, end)` in UTF-16 units of [text] as a
 * code-point [Selection], or null when nothing is selected (the tools then
 * work on the whole song).
 */
fun selectionOf(text: CharSequence, start: Int, end: Int): Selection? {
    if (start == end) return null
    val mapper = OffsetMapper.of(text)
    val a = mapper.toCodePoint(minOf(start, end))
    val b = mapper.toCodePoint(maxOf(start, end))
    return if (a == b) null else Selection(a, b)
}

/** Transpose's semitones, kept within the desktop dialog's −11..+11. */
data class TransposeForm(val semitones: Int = 0) {
    /** One semitone up (stops at +11). */
    fun up() = copy(semitones = (semitones + 1).coerceIn(RANGE))

    /** One semitone down (stops at −11). */
    fun down() = copy(semitones = (semitones - 1).coerceIn(RANGE))

    companion object {
        /** The semitones Transpose offers. */
        val RANGE: IntRange = -11..11
    }
}

/** The directive kinds of Tools › Insert (`session.directives.DirectiveKind`). */
enum class DirectiveKind(val wire: String) {
    BPM("bpm"),
    TIME("time"),
    KEY("key"),
    LABEL("label"),
    LOOP("loop"),
    ;

    companion object {
        /** The kind for a request's `kind`, or null for one this app doesn't know. */
        fun of(wire: String): DirectiveKind? = entries.firstOrNull { it.wire == wire }
    }
}

/**
 * One Insert directive dialog's fields. [answer] is the `{field: value}` map
 * `respond` takes (`session/directives.py`'s module docstring); every value
 * goes as typed or picked, Python checks it.
 */
data class DirectiveForm(
    val kind: DirectiveKind,
    /** BPM: `110`, `+20`, `20%`, `2x`, `reset`. */
    val bpm: String = "",
    val beats: Int = 4,
    val unit: Int = 4,
    val key: String = "",
    /** Label: the new label's name. */
    val label: String = "",
    /** Loop: `@start` or a label. */
    val loopLabel: String = LOOP_START,
    val count: Int = 2,
) {
    /** The answer to the request. */
    fun answer(): Map<String, String> = when (kind) {
        DirectiveKind.BPM -> mapOf("value" to bpm)
        DirectiveKind.TIME -> mapOf("beats" to beats.toString(), "unit" to unit.toString())
        DirectiveKind.KEY -> mapOf("key" to key)
        DirectiveKind.LABEL -> mapOf("label" to label)
        DirectiveKind.LOOP -> mapOf("label" to loopLabel, "count" to count.toString())
    }

    /** One more loop repeat (stops at 100). */
    fun moreRepeats() = copy(count = (count + 1).coerceIn(COUNT_RANGE))

    /** One loop repeat fewer (stops at 1). */
    fun fewerRepeats() = copy(count = (count - 1).coerceIn(COUNT_RANGE))

    /** As a list of strings for `rememberSaveable` ([restore] reads it back). */
    fun save(): List<String> =
        listOf(kind.name, bpm, beats.toString(), unit.toString(), key, label, loopLabel, count.toString())

    companion object {
        /** The loop target meaning the song's start (`session.directives.LOOP_START`). */
        const val LOOP_START = "@start"

        /** Time signature beats the picker offers (the desktop spinbox). */
        val BEATS_RANGE: IntRange = 1..16

        /** Loop repeats the stepper offers (the desktop spinbox). */
        val COUNT_RANGE: IntRange = 1..100

        /**
         * The fields a fresh dialog shows for [kind], as the desktop's do:
         * 4/4, the first key of the notation, `@start` repeated twice.
         */
        fun initial(kind: DirectiveKind, keys: List<String>): DirectiveForm =
            DirectiveForm(kind, key = keys.firstOrNull().orEmpty())

        /** The form [save] wrote, or null if it isn't one. */
        fun restore(saved: List<String>): DirectiveForm? {
            if (saved.size != 8) return null
            val kind = DirectiveKind.entries.firstOrNull { it.name == saved[0] } ?: return null
            return DirectiveForm(
                kind = kind,
                bpm = saved[1],
                beats = saved[2].toIntOrNull() ?: 4,
                unit = saved[3].toIntOrNull() ?: 4,
                key = saved[4],
                label = saved[5],
                loopLabel = saved[6],
                count = saved[7].toIntOrNull() ?: 2,
            )
        }
    }
}

/**
 * What a loop can jump back to: the song's start, then the request's labels
 * (`session.directives.loop_label_choices`; the session already sorted them).
 */
fun loopChoices(request: InsertDirectiveRequest): List<String> =
    listOf(DirectiveForm.LOOP_START) + request.existingLabels.filter { it != DirectiveForm.LOOP_START }.distinct()

/**
 * The keys the Key dialog offers: the notation's list from `SettingsState`
 * (`session.toolbar.key_options`), else the toolbar's list (the current
 * notation's, which is the request's).
 */
fun keyChoices(notation: String, american: List<String>?, european: List<String>?, toolbar: List<String>?): List<String> =
    (if (notation == "european") european else american)?.takeIf { it.isNotEmpty() } ?: toolbar.orEmpty()

/** The voicing the Suggest Capo dialog starts on: the request's default, else the first option. */
fun initialCapoChoice(request: CapoChoiceRequest): String? =
    request.options.firstOrNull { it.value == request.default }?.value ?: request.options.firstOrNull()?.value
