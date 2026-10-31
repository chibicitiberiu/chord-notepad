package com.tibich.chordnotepad.ui.settings

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.AlertDialog
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
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.appGraph
import com.tibich.chordnotepad.bridge.ScreenCommands
import com.tibich.chordnotepad.bridge.SessionRepository
import com.tibich.chordnotepad.support.SupportBilling
import com.tibich.chordnotepad.ui.icons.AppIcons
import com.tibich.chordnotepad.ui.support.SupportCard
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.filterNotNull

/** From this width the pages list stays on the left (tablets, phones in landscape). */
private val TwoPaneWidth = 600.dp

/** From this width the voicings list and form show side by side. */
private val SplitWidth = 840.dp

/** Width of the pages list in two-pane mode. */
private val PagesPaneWidth = 240.dp

/**
 * ☰ drawer › Settings: General, Playback and the Voicings editor over a settings
 * edit (`begin_settings_edit` when it opens; every change is saved as it is
 * made with `commit_settings`; leaving → `cancel_settings_edit`, asking first
 * only while a voicing is invalid). Full screen on phones (pages list → page
 * → voicing form), list/detail panes on tablets. [onClosed] once the edit ended.
 * [initialPage] opens a page at once (Voicings, from the Voicing sheet).
 * [supportBilling] feeds the support card above the pages (play flavour only;
 * it hides itself when there's nothing to sell).
 */
@Composable
fun SettingsScreen(
    repo: SessionRepository,
    commands: ScreenCommands,
    onClosed: () -> Unit,
    initialPage: SettingsPage? = null,
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
    LaunchedEffect(ui.draft, ui.saved, ui.phase, editor != null) {
        if (ui.draftPending) {
            delay(DRAFT_SAVE_DELAY_MS)
            controller.saveDraft()
        }
    }
    LaunchedEffect(ui.phase) { if (ui.phase == SettingsPhase.CLOSED) onClosed() }

    BoxWithConstraints(Modifier.fillMaxSize()) {
        val twoPane = maxWidth >= TwoPaneWidth
        val split = maxWidth >= SplitWidth
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
                    SettingsPage.GENERAL -> GeneralPage(draft, l, ui.invalidNumbers, controller)
                    SettingsPage.PLAYBACK -> PlaybackPage(draft, l, ui.invalidNumbers, controller)
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
    SettingsDialogs(ui.dialog, schema, controller)
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

/** The open [dialog]: discard an invalid voicing's edits, or the voicings editor's confirmations (texts from the schema). */
@Composable
private fun SettingsDialogs(dialog: SettingsDialog?, schema: EditorSchema?, controller: SettingsController) {
    when (dialog) {
        null -> Unit
        SettingsDialog.Discard -> ConfirmDialog(
            title = stringResource(R.string.settings_discard_title),
            message = stringResource(R.string.settings_discard_message),
            confirm = stringResource(R.string.settings_discard),
            dismiss = stringResource(R.string.settings_keep_editing),
            controller = controller,
            onDismiss = controller::keepEditing,
        )
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
    onDismiss: () -> Unit = controller::dismissDialog,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(message) },
        confirmButton = { TextButton(onClick = { controller.confirmDialog() }) { Text(confirm) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(dismiss) } },
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
    AlertDialog(
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
