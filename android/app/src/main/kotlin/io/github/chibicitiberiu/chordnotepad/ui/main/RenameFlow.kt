package io.github.chibicitiberiu.chordnotepad.ui.main

// Rename (tap the app bar's title): the dialog's field, the file name it
// shows ("Saved as name.txt"), and what happens when the storage provider
// can't rename (the session answers RenameFailed; the app offers Save As).

/** The extension a song gets when its name has none. */
const val DEFAULT_SONG_EXTENSION = ".txt"

private val EXTENSION = Regex("""\.[A-Za-z0-9]{1,5}$""")

/** The name the field starts with: the document's file name without its extension. */
fun renameFieldText(displayName: String): String = displayName.replace(EXTENSION, "")

/**
 * The file name a typed [input] saves as: trimmed, with the current
 * document's extension (or `.txt`) unless it names one itself.
 */
fun renamedFileName(input: String, currentDisplayName: String): String {
    val name = input.trim()
    if (name.isEmpty()) return ""
    if (EXTENSION.containsMatchIn(name)) return name
    val ext = EXTENSION.find(currentDisplayName)?.value ?: DEFAULT_SONG_EXTENSION
    return name + ext
}

/** Why the Rename button is disabled, or null when it's enabled. */
enum class RenameProblem { EMPTY, BAD_CHARACTER, UNCHANGED }

/** Characters a document name can't hold on the usual providers. */
private const val BAD_CHARACTERS = "/\\:*?\"<>|"

/** The problem with renaming [currentDisplayName] to [input], or null. */
fun renameProblem(input: String, currentDisplayName: String): RenameProblem? {
    val name = input.trim()
    return when {
        name.isEmpty() -> RenameProblem.EMPTY
        name.any { it in BAD_CHARACTERS || it.code < 32 } -> RenameProblem.BAD_CHARACTER
        renamedFileName(name, currentDisplayName) == currentDisplayName -> RenameProblem.UNCHANGED
        else -> null
    }
}

/**
 * The session couldn't rename the document ([reason]): offer Save As under
 * [name] when [canSaveAs], else just say why.
 */
data class RenameFailure(val name: String, val reason: String, val canSaveAs: Boolean)
