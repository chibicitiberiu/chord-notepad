package io.github.chibicitiberiu.chordnotepad.about

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.io.InputStream

/** Where the licence list comes from: the APK's assets, or a directory in tests. */
fun interface LicenceAssets {
    /** Opens [path] (relative to the licence directory); throws if missing. */
    fun open(path: String): InputStream
}

/** The kinds of component, in the order the list shows them. */
enum class LicenceGroup(val key: String) {
    APP("app"),
    RUNTIME("runtime"),
    NATIVE("native"),
    PYTHON("python"),
    DATA("data"),
    ANDROID("android"),
    ;

    companion object {
        /** The group named [key]; unknown names are an error in the data file. */
        fun of(key: String): LicenceGroup = entries.firstOrNull { it.key == key }
            ?: error("Unknown licence group '$key'")
    }
}

/**
 * One line of the licences screen.
 *
 * @property id Unique and stable (the detail screen's route).
 * @property license The licence's short name (an SPDX id where there is one).
 * @property copyright The copyright holder(s), when the text itself doesn't name them.
 * @property url The project's home.
 * @property sourceUrl Where the source is, when the licence asks for it to be available.
 * @property textFiles The licence texts to show, under `texts/` (empty: the text is [license]'s).
 * @property note What the component is here for, and anything unusual.
 */
data class LicenceEntry(
    val id: String,
    val name: String,
    val version: String?,
    val group: LicenceGroup,
    val license: String,
    val copyright: String?,
    val url: String?,
    val sourceUrl: String?,
    val textFiles: List<String>,
    val note: String?,
)

/** `components.json`: what the licence plugin can't see (Python, native code, data, the app). */
@Serializable
data class ComponentsFile(val components: List<ComponentJson>)

/** One hand-written component. [texts] are file names (without `.txt`) under `texts/`. */
@Serializable
data class ComponentJson(
    val id: String,
    val name: String,
    val group: String,
    val license: String,
    val texts: List<String>,
    val version: String? = null,
    val copyright: String? = null,
    val url: String? = null,
    val sourceUrl: String? = null,
    val note: String? = null,
)

/** AboutLibraries' `aboutlibraries.json`, the fields we show. */
@Serializable
data class MavenLibrariesFile(val libraries: List<MavenLibrary>)

/** One Maven dependency, as AboutLibraries exports it. */
@Serializable
data class MavenLibrary(
    val uniqueId: String,
    val name: String,
    val artifactVersion: String? = null,
    val description: String? = null,
    val website: String? = null,
    val developers: List<MavenDeveloper> = emptyList(),
    val licenses: List<String> = emptyList(),
    @SerialName("scm") val scm: MavenScm? = null,
)

/** A POM developer. */
@Serializable
data class MavenDeveloper(val name: String? = null)

/** A POM scm block. */
@Serializable
data class MavenScm(val url: String? = null)

/** Reads and combines the licence data. */
object Licences {
    private val json = Json { ignoreUnknownKeys = true }

    /** The directory of licence texts, inside the licence directory. */
    const val TEXTS = "texts"

    /** The hand-written data file. */
    const val COMPONENTS = "components.json"

    /** The licence text file (under [TEXTS]) of a plain Maven licence id like `Apache-2.0`. */
    fun textFileOf(licenseId: String): String = licenseId.replace(Regex("[^A-Za-z0-9.+-]"), "_")

    /** Parses `components.json`. */
    fun parseComponents(text: String): List<LicenceEntry> =
        json.decodeFromString<ComponentsFile>(text).components.map {
            LicenceEntry(
                id = it.id, name = it.name, version = it.version, group = LicenceGroup.of(it.group),
                license = it.license, copyright = it.copyright, url = it.url, sourceUrl = it.sourceUrl,
                textFiles = it.texts, note = it.note,
            )
        }

    /** Parses AboutLibraries' export into the Android libraries group. */
    fun parseMaven(text: String): List<LicenceEntry> =
        json.decodeFromString<MavenLibrariesFile>(text).libraries.map { lib ->
            LicenceEntry(
                id = "maven:" + lib.uniqueId,
                name = lib.name,
                version = lib.artifactVersion,
                group = LicenceGroup.ANDROID,
                license = lib.licenses.joinToString(", ").ifEmpty { "Unknown" },
                copyright = lib.developers.mapNotNull { it.name }.distinct().joinToString(", ").ifEmpty { null },
                url = lib.website ?: lib.scm?.url,
                sourceUrl = null,
                textFiles = lib.licenses.map(::textFileOf),
                note = lib.description,
            )
        }

    /**
     * The whole list: [components] (`components.json`'s text) and the Maven
     * libraries ([mavenJson], null when there is none), by group and then name.
     */
    fun entries(components: String, mavenJson: String?): List<LicenceEntry> {
        val all = parseComponents(components) + (mavenJson?.let(::parseMaven) ?: emptyList())
        val ids = all.map { it.id }
        check(ids.size == ids.toSet().size) { "Duplicate licence ids: " + ids.groupBy { it }.filter { it.value.size > 1 }.keys }
        return all.sortedWith(compareBy({ it.group.ordinal }, { it.name.lowercase() }))
    }

    /** Loads the list from [assets] and AboutLibraries' export. */
    fun load(assets: LicenceAssets, mavenJson: String?): List<LicenceEntry> =
        entries(assets.open(COMPONENTS).use { it.readBytes().decodeToString() }, mavenJson)

    /** The text to show for [entry]: its licence files, one after another. */
    fun textOf(entry: LicenceEntry, assets: LicenceAssets): String =
        entry.textFiles.joinToString("\n\n----------------------------------------\n\n") { file ->
            assets.open("$TEXTS/$file.txt").use { it.readBytes().decodeToString() }.trim()
        }
}
