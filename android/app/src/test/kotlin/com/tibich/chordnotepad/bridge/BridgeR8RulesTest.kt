package com.tibich.chordnotepad.bridge

import com.tibich.chordnotepad.files.SafDocumentStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * The release build's R8 rules (`app/proguard-rules.pro`) against the Kotlin
 * that Python reaches by name. R8 renames whatever no rule keeps, and a
 * broken name only shows when Python calls it on a device, so this checks:
 * the rules name the bridge classes as they are now (a moved or renamed
 * class fails here), every method Python calls on them is declared on a kept
 * interface, and Python's copy of the rename exception's name is the class's.
 * Gradle passes the paths (`cn.proguardRules`, `cn.androidPython`).
 */
class BridgeR8RulesTest {
    private val rules: List<String> = run {
        val path = System.getProperty("cn.proguardRules") ?: error("cn.proguardRules not set")
        File(path).readLines().map { it.substringBefore('#').trim() }.filter { it.isNotEmpty() }
    }

    private val pythonDir = File(System.getProperty("cn.androidPython") ?: error("cn.androidPython not set"))

    private fun python(name: String): String = File(pythonDir, name).readText()

    /** A rule that starts with [rule] and then opens its member block. */
    private fun hasRule(rule: String) =
        assertTrue("proguard-rules.pro lacks `$rule {`", rules.any { it.startsWith("$rule {") })

    /** The public attributes Python reads off [receiver] (`receiver.name`, not `receiver._name`). */
    private fun calledOn(source: String, receiver: String): Set<String> =
        Regex("""\b${Regex.escape(receiver)}\.([A-Za-z]\w*)""").findAll(source).map { it.groupValues[1] }.toSet()

    private fun methodsOf(type: Class<*>): Set<String> = type.methods.map { it.name }.toSet()

    @Test
    fun `the rules keep the bridge interfaces and their implementations' methods`() {
        for (type in listOf(EventSink::class.java, DocumentStoreBridge::class.java)) {
            assertTrue("${type.name} is an interface", type.isInterface)
            hasRule("-keep interface ${type.name}")
            hasRule("-keepclassmembers class * implements ${type.name}")
        }
    }

    @Test
    fun `the rules keep the rename exception's class name`() {
        hasRule("-keep class ${RenameUnsupportedException::class.java.name}")
    }

    @Test
    fun `Python matches the rename exception by its current simple name`() {
        val constant = Regex("""^RENAME_UNSUPPORTED = "([^"]+)"""", RegexOption.MULTILINE)
            .find(python("android_store.py"))?.groupValues?.get(1)
        assertEquals(RenameUnsupportedException::class.java.simpleName, constant)
    }

    @Test
    fun `everything Python calls on the document store is on DocumentStoreBridge`() {
        val called = calledOn(python("android_store.py"), "self._bridge") +
            calledOn(python("host.py"), "document_store")
        assertTrue("found no calls; did android_store.py change shape?", "readBytes" in called)
        val missing = called - methodsOf(DocumentStoreBridge::class.java)
        assertTrue("Python calls $missing, which DocumentStoreBridge doesn't declare (so no rule keeps it)", missing.isEmpty())
        assertTrue(DocumentStoreBridge::class.java.isAssignableFrom(SafDocumentStore::class.java))
    }

    @Test
    fun `everything Python calls on the event sink is on EventSink`() {
        val called = calledOn(python("host.py"), "event_sink")
        assertEquals(setOf("onEvent"), called)
        assertTrue(called.all { it in methodsOf(EventSink::class.java) })
        assertTrue(EventSink::class.java.isAssignableFrom(RepositoryEventSink::class.java))
    }
}
