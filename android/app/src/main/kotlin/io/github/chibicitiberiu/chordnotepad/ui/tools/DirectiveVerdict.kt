package io.github.chibicitiberiu.chordnotepad.ui.tools

import io.github.chibicitiberiu.chordnotepad.bridge.DirectiveCheck

/**
 * What an Insert dialog shows about its fields right now, from Python's
 * latest [DirectiveCheck] (the rules stay in `session/directives.py`).
 *
 * Insert is enabled only once a reply for exactly the current fields came
 * back clean; a reply for older fields, or for another request, counts as
 * "not checked yet". Messages are shown only when [showErrors] (the user has
 * changed something), so a fresh dialog isn't red before anything is typed.
 */
data class DirectiveVerdict(val canInsert: Boolean, val messages: List<String>) {
    companion object {
        /** The verdict for [answer] (the form's fields) given the latest [check]. */
        fun of(
            kind: String,
            requestId: Int,
            answer: Map<String, String>,
            check: DirectiveCheck?,
            showErrors: Boolean,
        ): DirectiveVerdict {
            val current = check != null && check.kind == kind && check.requestId == requestId && check.fields == answer
            if (!current || check == null) return DirectiveVerdict(false, emptyList())
            val messages = check.errors.values.toList() + listOfNotNull(check.formError.ifEmpty { null })
            return DirectiveVerdict(messages.isEmpty(), if (showErrors) messages else emptyList())
        }
    }
}
