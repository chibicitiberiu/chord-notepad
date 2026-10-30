package com.tibich.chordnotepad.ui.about

import android.content.Context
import android.util.Log
import android.widget.Toast
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.about.LicenceAssets
import com.tibich.chordnotepad.about.LicenceEntry
import com.tibich.chordnotepad.about.LicenceGroup
import com.tibich.chordnotepad.about.Licences
import com.tibich.chordnotepad.ui.icons.AppIcons
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.IOException

/** Where the licence data lives in the APK's assets. */
private const val ASSET_DIR = "licenses"

/** The APK's licence assets. */
fun Context.licenceAssets() = LicenceAssets { path -> assets.open("$ASSET_DIR/$path") }

/** The licence list, read once per composition off the main thread; null while loading. */
@Composable
private fun rememberLicenceEntries(): List<LicenceEntry>? {
    val context = LocalContext.current
    return produceState<List<LicenceEntry>?>(null) {
        value = withContext(Dispatchers.IO) {
            val maven = context.resources.openRawResource(R.raw.aboutlibraries).use { it.readBytes().decodeToString() }
            Licences.load(context.licenceAssets(), maven)
        }
    }.value
}

private fun LicenceGroup.title(): Int = when (this) {
    LicenceGroup.APP -> R.string.licences_group_app
    LicenceGroup.RUNTIME -> R.string.licences_group_runtime
    LicenceGroup.NATIVE -> R.string.licences_group_native
    LicenceGroup.PYTHON -> R.string.licences_group_python
    LicenceGroup.DATA -> R.string.licences_group_data
    LicenceGroup.GUIDE -> R.string.licences_group_guide
    LicenceGroup.ANDROID -> R.string.licences_group_android
}

/**
 * About > Open source licences: every component the app is built from, by kind.
 *
 * @param onOpen Show the licence page of an entry (by id).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LicencesScreen(onBack: () -> Unit, onOpen: (String) -> Unit) {
    val entries = rememberLicenceEntries()
    Scaffold(topBar = { BackBar(stringResource(R.string.licences_title), onBack) }) { padding ->
        if (entries == null) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }
        LazyColumn(Modifier.fillMaxSize().padding(padding)) {
            item {
                Text(
                    stringResource(R.string.licences_intro),
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.padding(16.dp),
                )
            }
            for ((group, rows) in entries.groupBy { it.group }) {
                item(key = "group:" + group.key) {
                    Text(
                        stringResource(group.title()),
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 4.dp),
                    )
                }
                items(rows, key = { it.id }) { entry ->
                    ListItem(
                        headlineContent = { Text(listOfNotNull(entry.name, entry.version).joinToString(" ")) },
                        supportingContent = { Text(entry.license) },
                        modifier = Modifier.clickable { onOpen(entry.id) },
                    )
                }
            }
        }
    }
}

/**
 * One component's licence: what it is, who holds the copyright, where its
 * source and website are (opened only on a tap), then the full licence text.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LicenceDetailScreen(id: String, onBack: () -> Unit) {
    val context = LocalContext.current
    val entries = rememberLicenceEntries()
    val entry = entries?.firstOrNull { it.id == id }
    val text by produceState<String?>(null, entry) {
        value = entry?.let {
            withContext(Dispatchers.IO) {
                try {
                    Licences.textOf(it, context.licenceAssets())
                } catch (e: IOException) {
                    Log.w("CNAbout", "No licence text for ${it.id}", e)
                    ""
                }
            }
        }
    }
    val linkFailed = stringResource(R.string.about_open_failed)
    fun open(url: String) {
        if (!openLink(context, url)) Toast.makeText(context, linkFailed, Toast.LENGTH_SHORT).show()
    }
    Scaffold(topBar = { BackBar(entry?.name ?: stringResource(R.string.licences_title), onBack) }) { padding ->
        Column(
            Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (entry == null) return@Column
            Text(
                listOfNotNull(entry.name, entry.version).joinToString(" "),
                style = MaterialTheme.typography.titleMedium,
            )
            Text(entry.license, style = MaterialTheme.typography.bodyMedium)
            entry.copyright?.let { Text(stringResource(R.string.licences_copyright, it), style = MaterialTheme.typography.bodyMedium) }
            entry.note?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
            entry.url?.let { Link(stringResource(R.string.licences_website) + ": " + it) { open(it) } }
            entry.sourceUrl?.let { Link(stringResource(R.string.licences_source) + ": " + it) { open(it) } }
            HorizontalDivider(Modifier.padding(vertical = 8.dp))
            when {
                text == null -> CircularProgressIndicator()
                text.isNullOrEmpty() -> Text(stringResource(R.string.licences_text_missing))
                else -> SelectionContainer {
                    Text(text.orEmpty(), fontFamily = FontFamily.Monospace, fontSize = 12.sp, lineHeight = 16.sp)
                }
            }
        }
    }
}

@Composable
private fun Link(text: String, onClick: () -> Unit) {
    Text(
        text,
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.primary,
        textDecoration = TextDecoration.Underline,
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun BackBar(title: String, onBack: () -> Unit) {
    TopAppBar(
        title = { Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
        navigationIcon = {
            IconButton(onClick = onBack) {
                Icon(AppIcons.ArrowBack, stringResource(R.string.licences_back))
            }
        },
    )
}
