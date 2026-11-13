package com.tibich.chordnotepad.ui.main

import android.os.SystemClock
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.Orientation
import androidx.compose.foundation.gestures.draggable
import androidx.compose.foundation.gestures.rememberDraggableState
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.isImeVisible
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalView
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.foundation.focusable
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.unit.dp
import com.tibich.chordnotepad.AppGraph
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.bridge.DocumentRef
import com.tibich.chordnotepad.bridge.HostStatus
import com.tibich.chordnotepad.bridge.PlaybackStatus
import com.tibich.chordnotepad.bridge.ScreenCommands
import com.tibich.chordnotepad.bridge.SongDefault
import com.tibich.chordnotepad.bridge.SongDefaultsState
import com.tibich.chordnotepad.bridge.ToolbarState
import com.tibich.chordnotepad.text.OffsetMapper
import com.tibich.chordnotepad.ui.MainActions
import com.tibich.chordnotepad.ui.UiTags
import com.tibich.chordnotepad.ui.chordsheet.ChordSheetPane
import com.tibich.chordnotepad.ui.chordsheet.ChordSheetSplit
import com.tibich.chordnotepad.ui.editor.ChordEditor
import com.tibich.chordnotepad.ui.editor.DirectiveHintController
import com.tibich.chordnotepad.ui.editor.DirectiveHintStrip
import com.tibich.chordnotepad.ui.editor.EXPLAIN_SHOWN_MS
import com.tibich.chordnotepad.ui.editor.bind
import com.tibich.chordnotepad.ui.handleEditShortcutBeforeIme
import com.tibich.chordnotepad.ui.handleShortcut
import com.tibich.chordnotepad.ui.identifier.ChordIdentifierDialog
import com.tibich.chordnotepad.ui.identifier.identifierLayout
import com.tibich.chordnotepad.ui.menus.currentProgramName
import com.tibich.chordnotepad.ui.menus.instrumentFamilies
import com.tibich.chordnotepad.ui.menus.recentEntries
import com.tibich.chordnotepad.ui.menus.selectedVoicingLabel
import com.tibich.chordnotepad.ui.menus.voicingGroups
import com.tibich.chordnotepad.ui.play.PlayTap
import com.tibich.chordnotepad.ui.play.Player
import com.tibich.chordnotepad.ui.play.PlayerActions
import com.tibich.chordnotepad.ui.play.PlayerState
import com.tibich.chordnotepad.ui.sheets.ExamplesSheet
import com.tibich.chordnotepad.ui.sheets.InsertSheet
import com.tibich.chordnotepad.ui.sheets.InstrumentPickerSheet
import com.tibich.chordnotepad.ui.sheets.SheetRoute
import com.tibich.chordnotepad.ui.sheets.SongDefaultValue
import com.tibich.chordnotepad.ui.sheets.SongDefaults
import com.tibich.chordnotepad.ui.sheets.SongDefaultsActions
import com.tibich.chordnotepad.ui.sheets.SongDefaultsSheet
import com.tibich.chordnotepad.ui.sheets.SpeedDialog
import com.tibich.chordnotepad.ui.sheets.SpeedSheet
import com.tibich.chordnotepad.ui.sheets.VoicingPickerSheet
import com.tibich.chordnotepad.ui.sheets.afterSheetDismissed
import com.tibich.chordnotepad.ui.sheets.back
import com.tibich.chordnotepad.ui.sheets.open
import com.tibich.chordnotepad.ui.sheets.speedBadge
import com.tibich.chordnotepad.ui.theme.appColors
import com.tibich.chordnotepad.ui.tools.DirectiveKind
import com.tibich.chordnotepad.ui.tools.ToolActions
import com.tibich.chordnotepad.ui.tools.TransposeDialog
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Where the main screen can send the user (the drawer's App entries). */
interface Navigation {
    fun settings(voicings: Boolean = false)
    fun userGuide()
    fun quickStart()
    fun about()
}

/**
 * The main screen of the Edit / Play redesign (docs/design/android-ui-spec.md):
 * the app bar with its tabs, the Edit ribbon or the player, the song text,
 * the chord sheet (Play only, below the text in portrait, beside it in
 * landscape), the ☰ drawer and the bottom sheets.
 */
@OptIn(ExperimentalLayoutApi::class, ExperimentalFoundationApi::class)
@Composable
fun SongScreen(graph: AppGraph, actions: MainActions, snackbars: SnackbarHostState, nav: Navigation) {
    val repo = graph.repository
    val colors = appColors
    val mode by graph.mode.mode.collectAsState()
    val host by repo.hostStatus.collectAsState()
    val document by repo.document.collectAsState()
    val editorState by repo.editor.collectAsState()
    val toolbar by repo.toolbar.collectAsState()
    val status by repo.status.collectAsState()
    val playback by repo.playback.collectAsState()
    val chordSheet by repo.chordSheet.collectAsState()
    val recent by repo.recentDocuments.collectAsState()
    val maxRecent = repo.settings.collectAsState().value?.values?.maxRecentFiles
    val songDefaultsState by repo.songDefaults.collectAsState()
    val songDefaults = songDefaultsState?.let(::songDefaultsOf)

    var routeSaved by rememberSaveable { mutableStateOf("") }
    val route = SheetRoute.restore(routeSaved)
    fun go(r: SheetRoute) {
        routeSaved = r.save()
    }
    var renameFailure by remember { mutableStateOf<RenameFailure?>(null) }
    // A name the session refused stays in the Rename dialog with the reason;
    // a storage that can't rename closes it and offers Save As.
    var renameError by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(repo) {
        repo.renameFailed.collect { f ->
            if (f.canSaveAs) {
                routeSaved = SheetRoute.None.save()
                renameFailure = RenameFailure(f.name, f.reason, true)
            } else {
                renameError = f.reason
            }
        }
    }
    // The rename went through (the title changed): close the dialog.
    var renaming by remember { mutableStateOf(false) }
    LaunchedEffect(document?.displayName) {
        if (renaming) {
            renaming = false
            if (SheetRoute.restore(routeSaved) == SheetRoute.Rename) routeSaved = SheetRoute.None.save()
        }
    }

    val drawer = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    BackHandler(enabled = drawer.isOpen) { scope.launch { drawer.close() } }
    val textScroll: ScrollState = rememberScrollState()
    // Sideways, while word wrap is off (both modes share it, as they share textScroll).
    // A song that's opened starts at the lines' start (not on a rotation).
    val textHScroll: ScrollState = rememberScrollState()
    var openedSeen by rememberSaveable { mutableIntStateOf(graph.editor.documentsOpened) }
    LaunchedEffect(graph.editor.documentsOpened) {
        if (graph.editor.documentsOpened != openedSeen) {
            openedSeen = graph.editor.documentsOpened
            textHScroll.scrollTo(0)
        }
    }
    val ribbonScroll = rememberScrollState()
    val tools = remember(graph) { ToolActions(graph.commands, ScreenCommands(graph.pyHost), graph.editor) }
    val editor = graph.editor
    // Focus the text field (Edit's "put the cursor on the directive"): bumped to ask.
    var focusAsk by remember { mutableIntStateOf(0) }
    val textFocus = remember { FocusRequester() }
    val rootFocus = remember { FocusRequester() }
    // Whether the root or anything in it has focus. When the focused editor
    // goes (Edit to Play turns it into plain text), focus would go nowhere and
    // the shortcuts with it (B1): the root takes it back.
    var rootHasFocus by remember { mutableStateOf(false) }
    LaunchedEffect(rootHasFocus) { if (!rootHasFocus) runCatching { rootFocus.requestFocus() } }
    val playbackStatus = playback?.status ?: PlaybackStatus.IDLE

    // Directive hints: Edit's strip while the cursor is in a directive, Play's
    // long-press explanation. Asked for debounced; the session thread answers.
    val hints = remember(graph) {
        DirectiveHintController { offset ->
            editor.syncNow()
            graph.commands.requestDirectiveHint(offset)
        }
    }
    var textFocused by remember { mutableStateOf(false) }
    val currentMode by rememberUpdatedState(mode)
    LaunchedEffect(hints) {
        hints.bind(this, repo, snapshotFlow {
            val selection = editor.state.selection
            if (currentMode == AppMode.EDIT && textFocused && selection.collapsed) {
                editor.codePointAt(selection.start)
            } else {
                null
            }
        })
    }
    LaunchedEffect(hints.explained, mode) {
        if (hints.explained != null) {
            if (mode != AppMode.PLAY) hints.dismiss() else {
                delay(EXPLAIN_SHOWN_MS)
                hints.dismiss()
            }
        }
    }
    var stripPx by remember { mutableIntStateOf(0) }

    fun selectMode(target: AppMode) {
        if (graph.mode.select(target, playbackStatus)) actions.stop()
    }

    // Edit mode has no status line: what the session says shows as a snackbar.
    // Play shows it on the player, and a snackbar still up from Edit goes.
    StatusSnackbars(mode, status?.text, playbackStatus, snackbars)

    val window = LocalConfiguration.current
    val windowSideBySide = ScreenLayout.of(
        window.screenWidthDp.toFloat(), window.screenHeightDp.toFloat(), mode, chordSheet?.visible == true,
    ).sideBySide

    // The screen stays on while a song plays; released on pause, stop, the end or leaving.
    val view = LocalView.current
    val awake = keepScreenOn(playback)
    DisposableEffect(view, awake) {
        view.keepScreenOn = awake
        onDispose { view.keepScreenOn = false }
    }

    val ribbonActions = remember(actions, tools, editor) {
        object : RibbonActions {
            override fun undo() = actions.undo()
            override fun redo() = actions.redo()
            override fun insert() = go(SheetRoute.Insert)
            override fun transpose() = go(SheetRoute.Transpose(selection = tools.selection() != null))
            override fun identify() = go(SheetRoute.Identify)
            override fun setNotation(notation: String) = actions.setNotation(notation)
            override fun convert() {
                val current = graph.repository.toolbar.value?.notation ?: "american"
                tools.convertNotation(if (current == "american") "european" else "american")
            }
        }
    }
    val playerActions = remember(actions) {
        object : PlayerActions {
            override fun songDefaults() = go(SheetRoute.SongDefaults)
            override fun voicing() = go(SheetRoute.Voicing)
            override fun instrument() = go(SheetRoute.Instrument())
            override fun rewind() = actions.rewind()
            override fun playPause() = actions.playPause()
            override fun toggleMetronome() = actions.toggleMetronome()
            override fun speed() = go(SheetRoute.Speed())
            override fun toggleSheet() {
                graph.repository.chordSheet.value?.let { actions.setChordSheetVisible(!it.visible) }
            }
        }
    }
    val drawerActions = remember(actions, nav) {
        object : DrawerActions {
            override fun newSong() = actions.newDocument()
            override fun open() = actions.openDocument()
            override fun openRecent(ref: DocumentRef) = actions.openRecent(ref)
            override fun saveAs() = actions.saveAs()
            override fun exportMidi() = actions.exportMidi()
            override fun settings() = nav.settings()
            override fun examples() = go(SheetRoute.Examples)
            override fun userGuide() = nav.userGuide()
            override fun quickStart() = nav.quickStart()
            override fun about() = nav.about()
        }
    }

    val canUndo = editor.state.undoState.canUndo
    val canRedo = editor.state.undoState.canRedo
    // The file name without its extension (Rename shows the full one).
    val title = document?.displayName?.let(::renameFieldText) ?: stringResource(R.string.app_name)
    val modified = document?.isModified == true

    ModalNavigationDrawer(
        drawerState = drawer,
        gesturesEnabled = drawer.isOpen,
        drawerContent = {
            AppDrawer(recentEntries(recent, maxRecent), drawerActions, close = { scope.launch { drawer.close() } })
        },
    ) {
        Scaffold(
            // A focusable root with initial focus, so a hardware keyboard's shortcuts
            // work before anything is tapped; it shows no soft keyboard.
            modifier = Modifier
                .handleKeys(actions, nav)
                .onFocusChanged { rootHasFocus = it.hasFocus }
                .focusRequester(rootFocus)
                .focusable(),
            containerColor = colors.surface,
            snackbarHost = {
                SnackbarHost(snackbars, Modifier.padding(bottom = snackbarClearanceDp(mode, windowSideBySide).dp))
            },
        ) { padding ->
            BoxWithConstraints(Modifier.fillMaxSize().padding(padding).consumeWindowInsets(padding)) {
                val layout = ScreenLayout.of(maxWidth.value, maxHeight.value, mode, chordSheet?.visible == true)
                val density = LocalDensity.current
                val imeVisible = WindowInsets.isImeVisible
                val imeDp = with(density) { WindowInsets.ime.getBottom(this).toDp() }
                val headerDp = if (layout.oneLineHeader || mode == AppMode.PLAY) BAR_HEIGHT_DP else 2 * BAR_HEIGHT_DP
                val collapsed = collapseHeader(mode, imeVisible, maxHeight.value - imeDp.value - headerDp)

                Column(Modifier.fillMaxSize().imePadding()) {
                    if (!collapsed) {
                        Header(
                            layout, mode, title, modified, ribbonActions, canUndo, canRedo,
                            toolbar?.notation, ribbonScroll,
                            onMenu = { scope.launch { drawer.open() } },
                            onRename = { go(SheetRoute.Rename) },
                            onMode = ::selectMode,
                            onSave = actions::save,
                        )
                    }
                    if (host is HostStatus.Starting) LinearProgressIndicator(Modifier.fillMaxWidth())
                    val text = @Composable { m: Modifier ->
                        ChordEditor(
                            controller = editor,
                            editorState = editorState,
                            mode = mode,
                            playhead = playback?.playheadOffset?.let { OffsetMapper.of(editor.state.text).toUtf16(it) },
                            playing = playbackStatus == PlaybackStatus.PLAYING,
                            scroll = textScroll,
                            hScroll = textHScroll,
                            onStepFontSize = actions::stepFontSize,
                            onPlayTap = { tap ->
                                when (tap) {
                                    is PlayTap.OnChord -> actions.tapChord(tap.start)
                                    is PlayTap.Nearest -> actions.setPlayhead(tap.start)
                                }
                            },
                            onScrub = actions::setPlayhead,
                            focusRequester = textFocus,
                            onKeyBeforeIme = actions::handleEditShortcutBeforeIme,
                            modifier = m.testTag(UiTags.EDITOR),
                            onTextFocus = { textFocused = it },
                            explained = hints.explained,
                            onExplain = hints::explain,
                            onDismissExplained = hints::dismiss,
                        )
                    }
                    when {
                        layout.sideBySide -> SideBySide(graph, text, playerState(toolbar, playback?.status, playback.isStarting, chordSheet?.visible, status?.text, host, songDefaults, graph), playerActions)
                        layout.sheetBelow -> {
                            text(Modifier.weight(1f).fillMaxWidth())
                            ChordSheetSplit(graph.pyHost, Modifier.fillMaxWidth())
                        }
                        else -> text(Modifier.weight(1f).fillMaxWidth())
                    }
                    // Under the text, so above the keyboard when it's open: it takes its
                    // own room and never covers the line being typed.
                    val strip = hints.strip.takeIf { mode == AppMode.EDIT }
                    if (strip != null) {
                        DirectiveHintStrip(strip, Modifier.fillMaxWidth().onSizeChanged { stripPx = it.height })
                    }
                    if (mode == AppMode.PLAY && !layout.sideBySide) {
                        Player(
                            playerState(toolbar, playback?.status, playback.isStarting, chordSheet?.visible, status?.text, host, songDefaults, graph),
                            playerActions,
                            compact = false,
                        )
                    }
                }
                if (collapsed) {
                    // Stacked above the hint strip when it shows.
                    val stripDp = if (mode == AppMode.EDIT && hints.strip != null) with(density) { stripPx.toDp() } else 0.dp
                    FloatingUndoChip(
                        ribbonActions, canUndo, canRedo,
                        Modifier.align(Alignment.BottomEnd).imePadding().padding(end = 10.dp, bottom = 8.dp + stripDp),
                    )
                }
            }
        }
    }

    LaunchedEffect(focusAsk) {
        if (focusAsk > 0) runCatching { textFocus.requestFocus() }
    }

    Sheets(
        route = route,
        graph = graph,
        actions = actions,
        tools = tools,
        toolbar = toolbar,
        songDefaults = songDefaults ?: toolbar?.let(::fallbackDefaults),
        go = ::go,
        nav = nav,
        renameError = renameError,
        onRenameSubmit = { name ->
            renameError = null
            renaming = true
            actions.rename(name)
        },
        onRenameClosed = {
            renameError = null
            renaming = false
        },
        onEditDirective = { offset ->
            go(SheetRoute.None)
            selectMode(AppMode.EDIT)
            val utf16 = OffsetMapper.of(editor.state.text).toUtf16(offset)
            editor.state.edit { selection = TextRange(utf16.coerceIn(0, length)) }
            focusAsk++
        },
    )
    renameFailure?.let { failure ->
        RenameFailedDialog(
            failure,
            onSaveAs = { name ->
                renameFailure = null
                actions.saveAs(name)
            },
            onDismiss = { renameFailure = null },
        )
    }
}

/** The app bar, and the Edit ribbon under it (or beside it on a phone in landscape). */
@Composable
private fun Header(
    layout: ScreenLayout,
    mode: AppMode,
    title: String,
    modified: Boolean,
    ribbonActions: RibbonActions,
    canUndo: Boolean,
    canRedo: Boolean,
    notation: String?,
    ribbonScroll: ScrollState,
    onMenu: () -> Unit,
    onRename: () -> Unit,
    onMode: (AppMode) -> Unit,
    onSave: () -> Unit,
) {
    val colors = appColors
    Column(Modifier.fillMaxWidth().background(colors.surface)) {
        if (layout.oneLineHeader) {
            val window = LocalConfiguration.current.screenWidthDp.toFloat()
            AppBar(
                title, modified, mode, showTitle = true, onMenu, onRename, onMode, onSave,
                titleMaxWidth = oneLineTitleMaxWidthDp(window).dp,
            ) {
                Box(Modifier.width(1.dp).fillMaxHeight().background(colors.line))
                EditRibbon(ribbonActions, canUndo, canRedo, notation, Modifier.weight(1f), ribbonScroll)
            }
        } else {
            AppBar(title, modified, mode, showTitle = true, onMenu, onRename, onMode, onSave)
            if (mode == AppMode.EDIT) {
                EditRibbon(ribbonActions, canUndo, canRedo, notation, Modifier.fillMaxWidth(), ribbonScroll)
            }
        }
        HorizontalDivider(color = colors.line)
    }
}

/**
 * Landscape Play mode: the text on the left, then a vertical handle, then a
 * column with the chord sheet and the compact player. The handle sets the
 * column's width (30–70 %, wider when the player needs it), kept in
 * [AppGraph.uiPreferences].
 */
@Composable
private fun SideBySide(
    graph: AppGraph,
    text: @Composable (Modifier) -> Unit,
    player: PlayerState,
    playerActions: PlayerActions,
) {
    val colors = appColors
    var stored by remember { mutableFloatStateOf(graph.uiPreferences.sideFraction) }
    var rowWidth by remember { mutableIntStateOf(0) }
    // Never so narrow that the compact player loses a button (L3).
    val density = LocalDensity.current
    val minFraction = if (rowWidth > 0) minSideFraction(with(density) { rowWidth.toDp().value }) else SIDE_FRACTION_MIN
    val fraction = clampSideFraction(stored, minFraction)
    Row(Modifier.fillMaxSize().onSizeChanged { rowWidth = it.width }) {
        text(Modifier.weight(1f - fraction).fillMaxHeight())
        Box(
            Modifier
                .width(14.dp)
                .fillMaxHeight()
                .testTag(UiTags.SIDE_HANDLE)
                .background(colors.surface)
                .semantics { contentDescription = "Resize the chord sheet" }
                .draggable(
                    state = rememberDraggableState { dx ->
                        if (rowWidth > 0) stored = clampSideFraction(clampSideFraction(stored, minFraction) - dx / rowWidth, minFraction)
                    },
                    orientation = Orientation.Horizontal,
                    onDragStopped = { graph.uiPreferences.sideFraction = stored },
                ),
            contentAlignment = Alignment.Center,
        ) {
            Box(Modifier.align(Alignment.CenterStart).width(1.dp).fillMaxHeight().background(colors.line))
            Box(Modifier.size(width = 4.dp, height = 36.dp).clip(RoundedCornerShape(2.dp)).background(colors.grip))
        }
        Column(Modifier.weight(fraction).fillMaxHeight()) {
            ChordSheetPane(graph.pyHost, Modifier.weight(1f).fillMaxWidth())
            Player(player, playerActions, compact = true)
        }
    }
}

/** What the player shows, from the session's states. */
@Composable
private fun playerState(
    toolbar: ToolbarState?,
    status: PlaybackStatus?,
    starting: Boolean,
    sheetVisible: Boolean?,
    statusText: String?,
    host: HostStatus,
    defaults: SongDefaults?,
    graph: AppGraph,
): PlayerState {
    val voicing by graph.repository.voicingMenu.collectAsState()
    val instruments by graph.repository.instrumentMenu.collectAsState()
    val text = when (host) {
        is HostStatus.Failed -> stringResource(R.string.status_failed, host.message)
        HostStatus.NotStarted, HostStatus.Starting -> statusText ?: stringResource(R.string.status_starting)
        else -> statusText.orEmpty()
    }
    return PlayerState(
        pill = defaults?.summary ?: toolbar?.let { fallbackDefaults(it).summary }.orEmpty(),
        playing = status == PlaybackStatus.PLAYING,
        starting = starting,
        metronome = toolbar?.metronome == true,
        speedBadge = toolbar?.let { speedBadge(it.multiplierPct) },
        sheetVisible = sheetVisible == true,
        status = text,
        voicingLabel = selectedVoicingLabel(voicing).orEmpty(),
        voicingLockedReason = voicing?.lockedReason,
        instrumentLabel = instruments?.let { currentProgramName(instrumentFamilies(it)) }.orEmpty(),
    )
}

/** Song defaults from the toolbar, before the session sends `SongDefaultsState`. */
private fun fallbackDefaults(t: ToolbarState): SongDefaults {
    val tempo = t.bpmDisplay.toString()
    val time = "${t.beats}/${t.unit}"
    return SongDefaults(
        SongDefaultValue(tempo, t.bpmSetBy != null), SongDefaultValue(time, t.timeSetBy != null),
        SongDefaultValue(t.key, t.keySetBy != null),
        SongDefaults.summaryOf(tempo, time, t.key),
    )
}

/** In Edit mode, each new status message shows as a short snackbar. */
@Composable
private fun StatusSnackbars(mode: AppMode, text: String?, playback: PlaybackStatus, snackbars: SnackbarHostState) {
    var last by remember { mutableStateOf(text) }
    // When a song last stopped (playing or paused → idle), monotonic ms.
    var stoppedAt by remember { mutableStateOf<Long?>(null) }
    var wasActive by remember { mutableStateOf(playback != PlaybackStatus.IDLE) }
    LaunchedEffect(playback) {
        val active = playback != PlaybackStatus.IDLE
        if (wasActive && !active) stoppedAt = SystemClock.uptimeMillis()
        wasActive = active
    }
    LaunchedEffect(mode) {
        // A status message still up from Edit goes (errors, which have a dismiss action, stay).
        val data = snackbars.currentSnackbarData
        if (!statusSnackbarsShown(mode) && data?.visuals?.withDismissAction == false) data.dismiss()
    }
    val currentMode by rememberUpdatedState(mode)
    LaunchedEffect(text) {
        val t = text
        if (t != last) {
            last = t
            // Opening a song switches to Play along with its status: let the mode settle first.
            delay(150)
            val allowed = statusSnackbarAllowed(currentMode, SystemClock.uptimeMillis(), stoppedAt)
            if (allowed && !t.isNullOrBlank()) snackbars.showSnackbar(t, duration = SnackbarDuration.Short)
        }
    }
}

/** The open bottom sheet or dialog. */
@Composable
private fun Sheets(
    route: SheetRoute,
    graph: AppGraph,
    actions: MainActions,
    tools: ToolActions,
    toolbar: ToolbarState?,
    songDefaults: SongDefaults?,
    go: (SheetRoute) -> Unit,
    nav: Navigation,
    renameError: String?,
    onRenameSubmit: (String) -> Unit,
    onRenameClosed: () -> Unit,
    onEditDirective: (Int) -> Unit,
) {
    val repo = graph.repository
    val close = { go(SheetRoute.None) }
    when (route) {
        SheetRoute.None -> Unit
        SheetRoute.SongDefaults -> songDefaults?.let { defaults ->
            SongDefaultsSheet(
                defaults,
                keys = toolbar?.keyOptions.orEmpty(),
                actions = object : SongDefaultsActions {
                    override fun setTempoText(text: String) = actions.setBpmText(text)
                    override fun setTime(beats: Int, unit: Int) = actions.setTimeSignature(beats, unit)
                    override fun setKey(key: String) = actions.setKey(key)
                    override fun editDirective(offset: Int) = onEditDirective(offset)
                    override fun writeIntoSong() = actions.writeSongDefaults()
                },
                onDismiss = close,
            )
        } ?: LaunchedEffect(Unit) { close() }
        SheetRoute.Voicing -> {
            val state by repo.voicingMenu.collectAsState()
            state?.let {
                VoicingPickerSheet(
                    voicingGroups(it),
                    onChoose = actions::setVoicing,
                    onEditVoicings = {
                        close()
                        nav.settings(voicings = true)
                    },
                    onDismiss = close,
                )
            }
        }
        is SheetRoute.Instrument -> {
            val state by repo.instrumentMenu.collectAsState()
            // Bumped when the sheet hid itself but the route keeps a sheet
            // (Back on a family): a new sheet shows the families.
            var sheetGeneration by remember { mutableIntStateOf(0) }
            state?.let {
                key(sheetGeneration) {
                    InstrumentPickerSheet(
                        instrumentFamilies(it),
                        family = route.family,
                        onOpenFamily = { i -> go(route.open(i)) },
                        onBack = { go(route.back()) },
                        onChoose = actions::setInstrument,
                        onDismiss = {
                            val (next, newSheet) = route.afterSheetDismissed()
                            if (newSheet) sheetGeneration++
                            go(next)
                        },
                        onDone = close,
                    )
                }
            }
        }
        is SheetRoute.Speed -> {
            val pct = toolbar?.multiplierPct ?: 100.0
            SpeedSheet(
                pct,
                onSpeed = actions::setMultiplierPct,
                onReset = actions::resetMultiplier,
                onManual = { go(SheetRoute.Speed(manual = true)) },
                onDismiss = close,
            )
            if (route.manual) {
                SpeedDialog(
                    pct,
                    onApply = {
                        actions.setMultiplierPct(it)
                        go(SheetRoute.Speed())
                    },
                    onDismiss = { go(SheetRoute.Speed()) },
                )
            }
        }
        SheetRoute.Insert -> InsertSheet(
            onInsert = { kind ->
                close()
                DirectiveKind.of(kind)?.let(tools::insertDirective)
            },
            onDismiss = close,
        )
        SheetRoute.Examples -> ExamplesSheet(
            names = graph.exampleNames,
            onPick = { name ->
                close()
                actions.openExample(name)
            },
            onDismiss = close,
        )
        SheetRoute.Rename -> RenameDialog(
            displayName = graph.repository.document.collectAsState().value?.displayName.orEmpty(),
            error = renameError,
            onRename = onRenameSubmit,
            onDismiss = {
                onRenameClosed()
                close()
            },
        )
        is SheetRoute.Transpose -> TransposeDialog(
            hasSelection = route.selection,
            onApply = { semitones ->
                close()
                tools.transpose(semitones, tools.selection())
            },
            onDismiss = close,
        )
        SheetRoute.Identify -> {
            val density = LocalDensity.current
            val window = LocalWindowInfo.current.containerSize
            val layout = with(density) { identifierLayout(window.width.toDp().value, window.height.toDp().value) }
            ChordIdentifierDialog(
                repo = repo,
                commands = tools.screen,
                insertAtCursor = tools::insertChord,
                layout = layout,
                onClose = close,
            )
        }
    }
}

/** Hardware keyboard shortcuts (Ctrl+S…, F1), as before the redesign. */
private fun Modifier.handleKeys(actions: MainActions, nav: Navigation): Modifier =
    onPreviewKeyEvent { actions.handleShortcut(it, onHelp = nav::userGuide) }

/** The sheet's model of the session's [SongDefaultsState]. */
private fun songDefaultsOf(s: SongDefaultsState): SongDefaults {
    fun v(d: SongDefault) = SongDefaultValue(d.value, d.fromDirective, d.directiveOffset)
    return SongDefaults(v(s.tempo), v(s.time), v(s.key), s.summary, s.lockedReason)
}
