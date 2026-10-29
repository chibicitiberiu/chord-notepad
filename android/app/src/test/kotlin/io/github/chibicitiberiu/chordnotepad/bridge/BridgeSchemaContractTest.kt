package io.github.chibicitiberiu.chordnotepad.bridge

import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Test
import java.io.File

/**
 * The Kotlin DTOs against `android/bridge_schema.json`, which session step 14
 * generates from the Python dataclasses (format: docs/ANDROID.md, "Bridge
 * contract"). Skipped until that file exists.
 */
class BridgeSchemaContractTest {
    private lateinit var schema: JsonObject

    @Before
    fun load() {
        val path = System.getProperty("cn.bridgeSchema")
        val file = path?.let(::File)
        assumeTrue("bridge_schema.json not generated yet (session step 14)", file != null && file.isFile)
        schema = Json.parseToJsonElement(file!!.readText()).jsonObject
    }

    private val types get() = schema.getValue("types").jsonObject

    private fun fieldsOf(type: String): Set<String> =
        types.getValue(type).jsonObject.getValue("fields").jsonObject.keys

    private fun kindOf(type: String): String = types.getValue(type).jsonObject.getValue("kind").jsonPrimitive.content

    private fun KSerializer<*>.names(): Set<String> =
        (0 until descriptor.elementsCount).map(descriptor::getElementName).toSet()

    @Test
    fun `every output type matches the schema field for field`() {
        for ((name, serializer) in BridgeCodec.serializers) {
            assertTrue("$name missing from the schema", name in types)
            assertEquals("fields of $name", fieldsOf(name), serializer.names())
        }
    }

    @Test
    fun `Kotlin decodes every output the schema lists`() {
        val outputs = types.keys.filter { kindOf(it) in setOf("state", "event", "request") }.toSet()
        assertEquals(outputs, BridgeCodec.serializers.keys)
    }

    @Test
    fun `value types match`() {
        val values = mapOf(
            "DocumentRef" to DocumentRef.serializer(),
            "Span" to Span.serializer(),
            "MenuItem" to MenuItem.serializer(),
            "InstrumentFamily" to InstrumentFamily.serializer(),
            "ChordSheetView" to ChordSheetView.serializer(),
            "SongDefault" to SongDefault.serializer(),
        )
        for ((name, serializer) in values) assertEquals("fields of $name", fieldsOf(name), serializer.names())
    }

    @Test
    fun `enum values match`() {
        val enums = schema.getValue("enums").jsonObject
        val kotlin = mapOf(
            "SpanKind" to SpanKind.serializer(),
            "PlaybackStatus" to PlaybackStatus.serializer(),
            "PlayAction" to PlayAction.serializer(),
            "UndoPolicy" to UndoPolicy.serializer(),
            "DiscardChoice" to DiscardChoice.serializer(),
            "PickMode" to PickMode.serializer(),
        )
        for ((name, serializer) in kotlin) {
            val python = enums.getValue(name).jsonArray.map { it.jsonPrimitive.content }.toSet()
            assertEquals("values of $name", python, serializer.names())
        }
    }

    @Test
    fun `Python accepts every command Kotlin sends`() {
        val python = schema.getValue("commands").jsonArray.map { it.jsonPrimitive.content }.toSet()
        assertEquals(emptySet<String>(), CommandNames.ALL - python)
    }
}
