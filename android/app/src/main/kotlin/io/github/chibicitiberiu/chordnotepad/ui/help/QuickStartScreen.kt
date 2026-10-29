package io.github.chibicitiberiu.chordnotepad.ui.help

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.chibicitiberiu.chordnotepad.AppGraph
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.bridge.QuickStartBlock
import io.github.chibicitiberiu.chordnotepad.bridge.QuickStartContent
import io.github.chibicitiberiu.chordnotepad.bridge.ScreenCommands
import io.github.chibicitiberiu.chordnotepad.ui.editor.EditorBackground
import io.github.chibicitiberiu.chordnotepad.ui.editor.EditorText
import io.github.chibicitiberiu.chordnotepad.ui.editor.SpanStyles
import io.github.chibicitiberiu.chordnotepad.ui.icons.AppIcons

/**
 * Help › Quick Start: the tour's pages one at a time (title, paragraphs and
 * read-only example snippets drawn with the editor's colours), Previous/Next
 * and a "Show at startup" checkbox.
 *
 * @param content The tour from the session, or null while it is being fetched.
 * @param showAtStartup The checkbox state.
 * @param onShowAtStartupChange The user toggled the checkbox.
 * @param onClose Leave the tour (Done, the arrow or Back).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QuickStartScreen(
    content: QuickStartContent?,
    showAtStartup: Boolean,
    onShowAtStartupChange: (Boolean) -> Unit,
    onClose: () -> Unit,
) {
    var pageIndex by rememberSaveable { mutableIntStateOf(0) }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.quick_start_title)) },
                navigationIcon = {
                    IconButton(onClick = onClose) {
                        Icon(AppIcons.ArrowBack, contentDescription = stringResource(R.string.licences_back))
                    }
                },
            )
        },
    ) { padding ->
        if (content == null || content.pages.isEmpty()) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }
        val pager = QuickStartPager(content.pages.size, pageIndex)
        val page = content.pages[pager.current]
        Column(Modifier.fillMaxSize().padding(padding)) {
            Column(
                Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState(), enabled = true)
                    .padding(horizontal = 20.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(page.title, style = MaterialTheme.typography.headlineSmall)
                for (block in page.blocks) {
                    when (block.kind) {
                        "snippet" -> Snippet(block)
                        "text" -> Text(block.text, style = MaterialTheme.typography.bodyLarge)
                        // "image": the Android tour has none; the desktop's screenshot isn't bundled.
                    }
                }
            }
            HorizontalDivider()
            Row(
                Modifier.fillMaxWidth().toggleable(
                    value = showAtStartup,
                    role = Role.Checkbox,
                    onValueChange = onShowAtStartupChange,
                ).padding(horizontal = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Checkbox(checked = showAtStartup, onCheckedChange = null, modifier = Modifier.padding(12.dp))
                Text(stringResource(R.string.quick_start_show_at_startup))
            }
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp).padding(bottom = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                OutlinedButton(onClick = { pageIndex = pager.previous().current }, enabled = !pager.isFirst) {
                    Text(stringResource(R.string.quick_start_previous))
                }
                Text(
                    stringResource(R.string.quick_start_page_of, pager.current + 1, pager.pageCount),
                    style = MaterialTheme.typography.bodyMedium,
                )
                if (pager.isLast) {
                    Button(onClick = onClose) { Text(stringResource(R.string.quick_start_done)) }
                } else {
                    Button(onClick = { pageIndex = pager.next().current }) {
                        Text(stringResource(R.string.quick_start_next))
                    }
                }
            }
        }
    }
}

/** An example song as the editor draws it: white, monospace, chords highlighted, not editable. */
@Composable
private fun Snippet(block: QuickStartBlock) {
    Surface(
        shape = RoundedCornerShape(6.dp),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        color = EditorBackground,
    ) {
        Text(
            remember(block) { snippetText(block) },
            color = EditorText,
            fontFamily = FontFamily.Monospace,
            fontSize = 15.sp,
            softWrap = false,
            modifier = Modifier.background(EditorBackground).horizontalScroll(rememberScrollState()).padding(12.dp),
        )
    }
}

/** The snippet's text with the editor's span styles applied (see [snippetRuns]). */
internal fun snippetText(block: QuickStartBlock): AnnotatedString {
    val styles = SpanStyles.toMap()
    return buildAnnotatedString {
        append(block.text)
        for (run in snippetRuns(block)) {
            styles[run.kind]?.let { addStyle(it, run.start, run.end) }
        }
    }
}

/**
 * Quick Start over the session: fetches the tour (`request_quick_start`),
 * and sends the "Show at startup" checkbox back (`set_show_quick_start_on_startup`).
 */
@Composable
fun QuickStartRoute(graph: AppGraph, onClose: () -> Unit) {
    val commands = remember(graph) { ScreenCommands(graph.pyHost) }
    val content by graph.repository.quickStart.collectAsState()
    val settings by graph.repository.settings.collectAsState()
    LaunchedEffect(commands) { commands.requestQuickStart() }
    // The checkbox follows the setting once the session has echoed a change;
    // until then the tour's own value.
    var show by rememberSaveable { mutableStateOf<Boolean?>(null) }
    QuickStartScreen(
        content = content,
        showAtStartup = show ?: settings?.values?.showQuickStartOnStartup ?: content?.showOnStartup ?: true,
        onShowAtStartupChange = {
            show = it
            commands.setShowQuickStartOnStartup(it)
        },
        onClose = onClose,
    )
}
