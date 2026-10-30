package com.tibich.chordnotepad.about

import com.tibich.chordnotepad.ui.about.Pages
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.io.FileNotFoundException

/**
 * The licence data the variant under test bundles: `src/main/assets/licenses`
 * plus its flavour's (`src/play/assets/licenses`: the Play libraries' texts).
 * It parses, every text it names exists and every text is used. Gradle passes
 * the paths per variant (`cn.licensesDirs`, `cn.aboutLibrariesJson`) and
 * `cn.requirements`.
 */
class LicencesTest {
    /** main first, then the flavour's directory if it has one; assets merge like this in the APK. */
    private val dirs = (System.getProperty("cn.licensesDirs") ?: error("cn.licensesDirs not set"))
        .split(File.pathSeparator).map(::File).filter { it.isDirectory }
    private val assets = LicenceAssets { path ->
        val file = dirs.reversed().map { File(it, path) }.firstOrNull { it.isFile }
            ?: throw FileNotFoundException("$path in $dirs")
        file.inputStream()
    }
    private val componentsText = assets.open(Licences.COMPONENTS).use { it.readBytes().decodeToString() }
    private val components = Licences.parseComponents(componentsText)

    /** AboutLibraries' export for this variant; Gradle runs its task first, so it must exist. */
    private fun mavenJson(): String {
        val path = System.getProperty("cn.aboutLibrariesJson") ?: error("cn.aboutLibrariesJson not set")
        val file = File(path)
        assertTrue("$path missing (prepareLibraryDefinitions<Variant> should have made it)", file.isFile)
        return file.readText()
    }

    @Test
    fun `every custom entry parses and has the fields the screen needs`() {
        assertTrue(components.size > 30)
        for (c in components) {
            assertTrue("${c.id}: name", c.name.isNotBlank())
            assertTrue("${c.id}: license", c.license.isNotBlank())
            assertTrue("${c.id}: needs a licence text", c.textFiles.isNotEmpty())
            assertTrue("${c.id}: needs a home page", !c.url.isNullOrBlank() || c.group == LicenceGroup.APP)
        }
        assertEquals("duplicate ids", components.size, components.map { it.id }.toSet().size)
    }

    @Test
    fun `every licence text an entry names exists and has content`() {
        for (c in components) {
            val text = Licences.textOf(c, assets)
            assertTrue("${c.id}: empty licence text", text.length > 100)
        }
    }

    @Test
    fun `no bundled licence text is unused`() {
        val used = components.flatMap { it.textFiles }.toMutableSet()
        used += Licences.parseMaven(mavenJson()).flatMap { it.textFiles }
        val onDisk = dirs.flatMap { File(it, Licences.TEXTS).listFiles().orEmpty().toList() }
            .map { it.name.removeSuffix(".txt") }.toSet()
        assertEquals("texts nothing refers to", emptySet<String>(), onDisk - used)
        assertEquals("texts that are missing", emptySet<String>(), used - onDisk)
    }

    @Test
    fun `the components the app can't list by itself are all there`() {
        val ids = components.map { it.id }.toSet()
        val expected = listOf(
            "chord-notepad", "cpython", "chaquopy", "openssl", "sqlite", "libffi", "zlib", "xz", "bzip2",
            "fluidsynth", "libsndfile", "oboe", "libogg", "libvorbis", "flac", "opus", "libcxx",
            "pychord", "music21", "mido", "pyfluidsynth", "chardet", "generaluser-gs", "bravura",
        )
        assertEquals(emptyList<String>(), expected.filterNot { it in ids })
    }

    @Test
    fun `the app is AGPL and the SoundFont carries its own licence`() {
        val app = components.single { it.id == "chord-notepad" }
        assertEquals("AGPL-3.0-only", app.license)
        assertTrue(Licences.textOf(app, assets).contains("GNU AFFERO GENERAL PUBLIC LICENSE"))
        val font = components.single { it.id == "generaluser-gs" }
        assertTrue(Licences.textOf(font, assets).contains("GeneralUser GS"))
    }

    @Test
    fun `LGPL and MPL components say where their source is`() {
        for (c in components.filter { it.license.startsWith("LGPL") || it.license.startsWith("MPL") }) {
            assertTrue("${c.id}: sourceUrl", !c.sourceUrl.isNullOrBlank())
        }
    }

    @Test
    fun `every Python package in requirements has an entry with the pinned version`() {
        val requirements = File(System.getProperty("cn.requirements") ?: error("cn.requirements not set")).readLines()
        val pins = requirements
            .map { it.substringBefore('#').trim() }
            .mapNotNull { Regex("""^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)""").find(it) }
            .associate { it.groupValues[1].lowercase().replace('_', '-') to it.groupValues[2] }
        assertTrue(pins.size >= 12)
        val python = components.filter { it.group == LicenceGroup.PYTHON }.associate { it.id to it.version }
        assertEquals("packages without an entry, or with another version", pins, python)
    }

    @Test
    fun `the Maven libraries AboutLibraries exports all have a licence text`() {
        val json = mavenJson()
        val libs = Licences.parseMaven(json)
        assertTrue(libs.size > 20)
        val all = Licences.entries(componentsText, json)
        assertEquals(libs.size + components.size, all.size)
        for (lib in libs) {
            assertTrue("${lib.id}: no licence", lib.textFiles.isNotEmpty())
            assertTrue("${lib.id}: ${lib.license}", Licences.textOf(lib, assets).length > 100)
        }
    }

    @Test
    fun `maven data is read from AboutLibraries' format`() {
        val sample = """
            {"libraries":[{"uniqueId":"androidx.core:core","artifactVersion":"1.0","name":"Core",
              "description":"d","website":"https://w","developers":[{"name":"AOSP"}],
              "scm":{"url":"https://s"},"licenses":["Apache-2.0"],"funding":[]}],
             "licenses":{"Apache-2.0":{"name":"x","hash":"Apache-2.0"}}}
        """.trimIndent()
        val e = Licences.parseMaven(sample).single()
        assertEquals("maven:androidx.core:core", e.id)
        assertEquals("Apache-2.0", e.license)
        assertEquals(listOf("Apache-2.0"), e.textFiles)
        assertEquals(LicenceGroup.ANDROID, e.group)
        assertEquals("AOSP", e.copyright)
    }

    @Test
    fun `the list is grouped in a fixed order and sorted by name`() {
        val all = Licences.entries(componentsText, null)
        assertEquals(LicenceGroup.APP, all.first().group)
        assertEquals(all.map { it.group.ordinal }, all.map { it.group.ordinal }.sorted())
        val pythonNames = all.filter { it.group == LicenceGroup.PYTHON }.map { it.name.lowercase() }
        assertEquals(pythonNames.sorted(), pythonNames)
    }

    @Test
    fun `pages go back to where they came from`() {
        assertEquals(Pages.MAIN, Pages.parent(Pages.ABOUT))
        assertEquals(Pages.ABOUT, Pages.parent(Pages.LICENCES))
        assertEquals(Pages.LICENCES, Pages.parent(Pages.detail("fluidsynth")))
        assertEquals("fluidsynth", Pages.detailId(Pages.detail("fluidsynth")))
        assertNull(Pages.detailId(Pages.ABOUT))
        assertEquals("maven:a:b", Pages.detailId(Pages.detail("maven:a:b")))
    }

    @Test
    fun `build info has a version and no date`() {
        val info = BuildInfo.current
        assertTrue(info.versionName.matches(Regex("""\d+\.\d+(\.\d+)?""")))
        assertTrue(info.versionCode > 0)
        assertTrue(info.buildType in setOf("debug", "release"))
    }
}
