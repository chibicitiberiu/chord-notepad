package com.tibich.chordnotepad.ui.settings

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.ListItemDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.ui.KeyboardSafeAlertDialog
import com.tibich.chordnotepad.appGraph
import com.tibich.chordnotepad.bridge.ScreenCommands
import com.tibich.chordnotepad.bridge.SessionRepository
import com.tibich.chordnotepad.bridge.SettingsState
import com.tibich.chordnotepad.support.SupportBilling
import com.tibich.chordnotepad.ui.icons.AppIcons
import com.tibich.chordnotepad.ui.support.SupportCard
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.filterNotNull

/** From this width the pages list stays on the left (tablets, phones in landscape). */
private val TwoPaneWidth = 600.dp

/** The voicings list and form need this much width beside the pages list to sit side by side. */
const val VOICINGS_SPLIT_CONTENT_DP = 720f

/**
 * Whether the Voicings page shows its list and form side by side in a
 * window [widthDp] wide: with room for both after the 240 dp pages list
 * (L14: a phone in landscape, 914 dp, got three columns and a 300 dp form).
 */
fun splitsVoicings(widthDp: Float): Boolean {
    val pages = if (widthDp >= 600f) 240f else 0f
    return widthDp - pages >= VOICINGS_SPLIT_CONTENT_DP
}

/** Width of the pages list in two-pane mode. */
private val PagesPaneWidth = 240.dp

/**
 * ☰ drawer › Settings: General, Playback and the Voicings editor over a settings
 * edit (`begin_settings_edit` when it opens; every change is saved as it is
 * made with `commit_settings`; leaving → `cancel_settings_edit`, asking first
 * only while a voicing is invalid). Full screen on phones (pages list → page
 * → voicing form), list/detail panes on tablets. [onClosed] once the edit ended.
 * [initialPage] opens a page at once (Voicings, from the Voicing sheet).
 * [leaveRequested] leaves as Back from the pages list does ([onLeaveRequestSeen] once acted on).
 * [supportBilling] feeds the support card above the pages (play flavour only;
 * it hides itself when there's nothing to sell).
 */
@Composable
fun SettingsScreen(
    repo: SessionRepository,
    commands: ScreenCommands,
    onClosed: () -> Unit,
    initialPage: SettingsPage? = null,
    leaveRequested: Boolean = false,
    onLeaveRequestSeen: () -> Unit = {},
    supportBilling: SupportBilling = LocalContext.current.appGraph.supportBilling,
) {
    val controller = rememberSaveable(
        saver = Saver<SettingsController, String>({ it.snapshot() }, { SettingsController.restore(commands, it) }),
    ) { SettingsController(commands, SettingsUi(nav = SettingsNav(initialPage))) }
    val schemaEvent by repo.voicingEditorSchema.collectAsState()
    val schema = remember(schemaEvent) { schemaEvent?.let { EditorSchema.parse(it.schema) } }
    val limits by repo.settings.collectAsState()
    val ui by controller.ui.collectAsState()
    val editor by controller.editor.collectAsState()

    LaunchedEffect(controller) {
        controller.start(needSchema = repo.voicingEditorSchema.value == null)
        repo.settings.filterNotNull().collect(controller::onSettings)
    }
    LaunchedEffect(controller) { repo.voicingEditor.filterNotNull().collect(controller::onEditor) }
    // A number being typed is saved once it rests; the rest is saved at once.
    LaunchedEffect(ui.draft, ui.saved, ui.numberTexts, ui.sentNumbers, ui.phase, editor != null) {
        if (ui.draftPending || ui.numbersPending) {
            delay(DRAFT_SAVE_DELAY_MS)
            controller.saveDraft()
        }
    }
    LaunchedEffect(ui.phase) { if (ui.phase == SettingsPhase.CLOSED) onClosed() }
    // Asked to leave from outside (a song opened with Open with): as Back
    // from the pages list, asking first while a value is wrong.
    LaunchedEffect(leaveRequested) {
        if (leaveRequested) {
            onLeaveRequestSeen()
            controller.requestClose()
        }
    }

    BoxWithConstraints(Modifier.fillMaxSize()) {
        val twoPane = maxWidth >= TwoPaneWidth
        val split = splitsVoicings(maxWidth.value)
        LaunchedEffect(twoPane) { controller.settleNav(twoPane) }
        BackHandler(enabled = ui.dialog == null) { controller.back(twoPane, split) }
        SettingsScaffold(ui, editor, twoPane, split, controller) {
            val draft = ui.draft
            val l = limits
            if (draft == null || l == null || ui.phase == SettingsPhase.NEW || ui.phase == SettingsPhase.OPENING) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                return@SettingsScaffold
            }
            val page: @Composable (SettingsPage) -> Unit = { p ->
                when (p) {
                    SettingsPage.GENERAL -> GeneralPage(draft, l, ui.numberTexts, controller)
                    SettingsPage.PLAYBACK -> PlaybackPage(draft, l, ui.numberTexts, controller)
                    SettingsPage.VOICINGS -> VoicingsPage(schema, editor, ui.nav.voicingDetail, split, controller)
                }
            }
            val shown = ui.nav.shown(twoPane)
            if (twoPane) {
                Row(Modifier.fillMaxSize()) {
                    PagesList(shown, controller, supportBilling, Modifier.width(PagesPaneWidth).fillMaxHeight())
                    VerticalDivider()
                    Box(Modifier.weight(1f)) { shown?.let { page(it) } }
                }
            } else if (shown == null) {
                PagesList(null, controller, supportBilling, Modifier.fillMaxSize())
            } else {
                page(shown)
            }
        }
    }
    SettingsDialogs(ui, editor, limits, schema, controller)
}

/** The app bar (Back, the page's title) over [content]. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SettingsScaffold(
    ui: SettingsUi,
    editor: EditorView?,
    twoPane: Boolean,
    split: Boolean,
    controller: SettingsController,
    content: @Composable () -> Unit,
) {
    val shown = ui.nav.shown(twoPane)
    val title = when {
        twoPane || shown == null -> stringResource(R.string.settings_title)
        shown == SettingsPage.VOICINGS && ui.nav.voicingDetail && !split && editor?.state?.selected != null ->
            editor.state.selected
        else -> pageTitle(shown)
    }
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(title, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                navigationIcon = {
                    IconButton(onClick = { controller.back(twoPane, split) }) {
                        Icon(AppIcons.ArrowBack, stringResource(R.string.settings_back))
                    }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .consumeWindowInsets(padding)
                .imePadding(),
        ) {
            val problems = ui.numberTexts.isNotEmpty() || editor?.state?.problems?.isNotEmpty() == true
            if (editor?.state?.restored == true && problems) RestoredBanner(controller)
            content()
        }
    }
}

/**
 * The pages: General, Playback, Voicings ([selected] highlighted in two-pane
 * mode), under the support card when [support] has one to show.
 */
@Composable
private fun PagesList(selected: SettingsPage?, controller: SettingsController, support: SupportBilling, modifier: Modifier) {
    Column(modifier) {
        SupportCard(support, Modifier.padding(horizontal = 16.dp, vertical = 8.dp))
        for (page in SettingsPage.entries) {
            ListItem(
                headlineContent = { Text(pageTitle(page)) },
                supportingContent = { Text(pageSummary(page)) },
                colors = ListItemDefaults.colors(
                    containerColor = if (page == selected) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surface,
                ),
                modifier = Modifier.clickable { controller.openPage(page) },
            )
        }
    }
}

@Composable
private fun pageTitle(page: SettingsPage): String = stringResource(
    when (page) {
        SettingsPage.GENERAL -> R.string.settings_page_general
        SettingsPage.PLAYBACK -> R.string.settings_page_playback
        SettingsPage.VOICINGS -> R.string.settings_page_voicings
    },
)

@Composable
private fun pageSummary(page: SettingsPage): String = stringResource(
    when (page) {
        SettingsPage.GENERAL -> R.string.settings_page_general_summary
        SettingsPage.PLAYBACK -> R.string.settings_page_playback_summary
        SettingsPage.VOICINGS -> R.string.settings_page_voicings_summary
    },
)

/**
 * Wrong values kept from last time (the app went away before they were
 * fixed or discarded): Edit goes to the first, Discard drops them.
 */
@Composable
private fun RestoredBanner(controller: SettingsController) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer,
            contentColor = MaterialTheme.colorScheme.onErrorContainer,
        ),
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        Column(Modifier.padding(start = 16.dp, top = 12.dp, end = 8.dp)) {
            Text(stringResource(R.string.settings_restored), style = MaterialTheme.typography.bodyMedium)
            Row(Modifier.align(Alignment.End)) {
                TextButton(onClick = controller::discardProblems) { Text(stringResource(R.string.settings_problems_discard)) }
                TextButton(onClick = controller::editProblems) { Text(stringResource(R.string.settings_problems_edit)) }
            }
        }
    }
}

/**
 * Leaving with wrong values: each one listed (numbers worded here, voicing
 * values as Python words them), Edit goes to the first, Discard drops them
 * and leaves.
 */
@Composable
private fun ProblemsDialog(ui: SettingsUi, editor: EditorView?, limits: SettingsState?, controller: SettingsController) {
    val empty = stringResource(R.string.settings_problem_empty)
    val lines = buildList {
        for ((setting, text) in ui.numberTexts.entries.sortedBy { it.key.ordinal }) {
            val range = limits?.let { setting.range(it) }
            add(
                stringResource(
                    R.string.settings_problem_number,
                    pageTitle(setting.page),
                    stringResource(setting.labelRes()),
                    text.trim().ifEmpty { empty },
                    range?.let { stringResource(R.string.settings_number_range, it.first, it.last) }.orEmpty(),
                ).trim(),
            )
        }
        editor?.state?.problems?.forEach { add(it.text) }
    }
    AlertDialog(
        onDismissRequest = controller::dismissDialog,
        title = { Text(stringResource(R.string.settings_problems_title)) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(stringResource(R.string.settings_problems_intro))
                for (line in lines) Text("• $line", style = MaterialTheme.typography.bodyMedium)
            }
        },
        confirmButton = { TextButton(onClick = controller::editProblems) { Text(stringResource(R.string.settings_problems_edit)) } },
        dismissButton = { TextButton(onClick = { controller.confirmDialog() }) { Text(stringResource(R.string.settings_problems_discard)) } },
    )
}

/** The open dialog: leaving with wrong values, or the voicings editor's confirmations (texts from the schema). */
@Composable
private fun SettingsDialogs(
    ui: SettingsUi,
    editor: EditorView?,
    limits: SettingsState?,
    schema: EditorSchema?,
    controller: SettingsController,
) {
    when (val dialog = ui.dialog) {
        null -> Unit
        SettingsDialog.Problems -> ProblemsDialog(ui, editor, limits, controller)
        is SettingsDialog.RemoveVoicing -> ConfirmDialog(
            title = schema?.text("remove_confirm_title").orEmpty(),
            message = schema?.text("remove_confirm")?.replace("{name}", dialog.name).orEmpty(),
            controller = controller,
        )
        is SettingsDialog.ChangeModel -> ConfirmDialog(
            title = schema?.text("model_confirm_title").orEmpty(),
            message = schema?.text("model_confirm").orEmpty(),
            controller = controller,
        )
        is SettingsDialog.LoadPreset -> ConfirmDialog(
            title = schema?.text("load_confirm_title").orEmpty(),
            message = schema?.text("load_confirm").orEmpty(),
            controller = controller,
        )
        is SettingsDialog.Rename -> RenameDialog(dialog.name, schema, controller)
    }
}

@Composable
private fun ConfirmDialog(
    title: String,
    message: String,
    controller: SettingsController,
    confirm: String = stringResource(android.R.string.ok),
    dismiss: String = stringResource(android.R.string.cancel),
) {
    AlertDialog(
        onDismissRequest = controller::dismissDialog,
        title = { Text(title) },
        text = { Text(message) },
        confirmButton = { TextButton(onClick = { controller.confirmDialog() }) { Text(confirm) } },
        dismissButton = { TextButton(onClick = controller::dismissDialog) { Text(dismiss) } },
    )
}

/** Rename a voicing (the name selected, ready to type over); a refused name comes back as a "Rename Voicing" error. */
@Composable
private fun RenameDialog(name: String, schema: EditorSchema?, controller: SettingsController) {
    var text by rememberSaveable(name, stateSaver = TextFieldValue.Saver) {
        mutableStateOf(TextFieldValue(name, selection = TextRange(0, name.length)))
    }
    val focus = remember { FocusRequester() }
    LaunchedEffect(Unit) { focus.requestFocus() }
    KeyboardSafeAlertDialog(
        onDismissRequest = controller::dismissDialog,
        title = { Text(stringResource(R.string.voicings_rename)) },
        text = {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                singleLine = true,
                label = { Text(schema?.text("name_label", "Name") ?: "Name") },
                supportingText = schema?.help?.get("name")?.let { { Text(it) } },
                modifier = Modifier.focusRequester(focus),
            )
        },
        confirmButton = {
            TextButton(onClick = { controller.confirmDialog(text.text) }, enabled = text.text.isNotBlank()) {
                Text(stringResource(android.R.string.ok))
            }
        },
        dismissButton = { TextButton(onClick = controller::dismissDialog) { Text(stringResource(android.R.string.cancel)) } },
    )
}
