package io.github.chibicitiberiu.chordnotepad.ui.main

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
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
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
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.foundation.focusable
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.unit.dp
import io.github.chibicitiberiu.chordnotepad.AppGraph
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.bridge.DocumentRef
import io.github.chibicitiberiu.chordnotepad.bridge.HostStatus
import io.github.chibicitiberiu.chordnotepad.bridge.PlaybackStatus
import io.github.chibicitiberiu.chordnotepad.bridge.ScreenCommands
import io.github.chibicitiberiu.chordnotepad.bridge.SongDefault
import io.github.chibicitiberiu.chordnotepad.bridge.SongDefaultsState
import io.github.chibicitiberiu.chordnotepad.bridge.ToolbarState
import io.github.chibicitiberiu.chordnotepad.text.OffsetMapper
import io.github.chibicitiberiu.chordnotepad.ui.MainActions
import io.github.chibicitiberiu.chordnotepad.ui.chordsheet.ChordSheetPane
import io.github.chibicitiberiu.chordnotepad.ui.chordsheet.ChordSheetSplit
import io.github.chibicitiberiu.chordnotepad.ui.editor.ChordEditor
import io.github.chibicitiberiu.chordnotepad.ui.handleShortcut
import io.github.chibicitiberiu.chordnotepad.ui.identifier.ChordIdentifierDialog
import io.github.chibicitiberiu.chordnotepad.ui.menus.currentProgramName
import io.github.chibicitiberiu.chordnotepad.ui.menus.instrumentFamilies
import io.github.chibicitiberiu.chordnotepad.ui.menus.recentEntries
import io.github.chibicitiberiu.chordnotepad.ui.menus.selectedVoicingLabel
import io.github.chibicitiberiu.chordnotepad.ui.menus.voicingGroups
import io.github.chibicitiberiu.chordnotepad.ui.play.PlayTap
import io.github.chibicitiberiu.chordnotepad.ui.play.Player
import io.github.chibicitiberiu.chordnotepad.ui.play.PlayerActions
import io.github.chibicitiberiu.chordnotepad.ui.play.PlayerState
import io.github.chibicitiberiu.chordnotepad.ui.sheets.InsertSheet
import io.github.chibicitiberiu.chordnotepad.ui.sheets.InstrumentPickerSheet
import io.github.chibicitiberiu.chordnotepad.ui.sheets.SheetRoute
import io.github.chibicitiberiu.chordnotepad.ui.sheets.SongDefaultValue
import io.github.chibicitiberiu.chordnotepad.ui.sheets.SongDefaults
import io.github.chibicitiberiu.chordnotepad.ui.sheets.SongDefaultsActions
import io.github.chibicitiberiu.chordnotepad.ui.sheets.SongDefaultsSheet
import io.github.chibicitiberiu.chordnotepad.ui.sheets.SpeedDialog
import io.github.chibicitiberiu.chordnotepad.ui.sheets.SpeedSheet
import io.github.chibicitiberiu.chordnotepad.ui.sheets.VoicingPickerSheet
import io.github.chibicitiberiu.chordnotepad.ui.sheets.back
import io.github.chibicitiberiu.chordnotepad.ui.sheets.open
import io.github.chibicitiberiu.chordnotepad.ui.sheets.speedBadge
import io.github.chibicitiberiu.chordnotepad.ui.theme.appColors
import io.github.chibicitiberiu.chordnotepad.ui.tools.DirectiveKind
import io.github.chibicitiberiu.chordnotepad.ui.tools.ToolActions
import io.github.chibicitiberiu.chordnotepad.ui.tools.TransposeDialog
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
    val ribbonScroll = rememberScrollState()
    val tools = remember(graph) { ToolActions(graph.commands, ScreenCommands(graph.pyHost), graph.editor) }
    val editor = graph.editor
    // Focus the text field (Edit's "put the cursor on the directive"): bumped to ask.
    var focusAsk by remember { mutableIntStateOf(0) }
    val textFocus = remember { FocusRequester() }
    val rootFocus = remember { FocusRequester() }
    LaunchedEffect(Unit) { runCatching { rootFocus.requestFocus() } }
    val playbackStatus = playback?.status ?: PlaybackStatus.IDLE

    fun selectMode(target: AppMode) {
        if (graph.mode.select(target, playbackStatus)) actions.stop()
    }

    // Edit mode has no status line: what the session says shows as a snackbar.
    StatusSnackbars(mode, status?.text, snackbars)

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
            AppDrawer(recentEntries(recent), drawerActions, close = { scope.launch { drawer.close() } })
        },
    ) {
        Scaffold(
            // A focusable root with initial focus, so a hardware keyboard's shortcuts
            // work before anything is tapped; it shows no soft keyboard.
            modifier = Modifier.handleKeys(actions, nav).focusRequester(rootFocus).focusable(),
            containerColor = colors.surface,
            snackbarHost = { SnackbarHost(snackbars) },
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
                            onStepFontSize = actions::stepFontSize,
                            onPlayTap = { tap ->
                                when (tap) {
                                    is PlayTap.OnChord -> actions.tapChord(tap.start)
                                    is PlayTap.Nearest -> actions.setPlayhead(tap.start)
                                }
                            },
                            onScrub = actions::setPlayhead,
                            focusRequester = textFocus,
                            modifier = m,
                        )
                    }
                    when {
                        layout.sideBySide -> SideBySide(graph, text, playerState(toolbar, playback?.status, chordSheet?.visible, status?.text, host, songDefaults, graph), playerActions)
                        layout.sheetBelow -> {
                            text(Modifier.weight(1f).fillMaxWidth())
                            ChordSheetSplit(graph.pyHost, Modifier.fillMaxWidth())
                        }
                        else -> text(Modifier.weight(1f).fillMaxWidth())
                    }
                    if (mode == AppMode.PLAY && !layout.sideBySide) {
                        Player(
                            playerState(toolbar, playback?.status, chordSheet?.visible, status?.text, host, songDefaults, graph),
                            playerActions,
                            compact = false,
                        )
                    }
                }
                if (collapsed) {
                    FloatingUndoChip(
                        ribbonActions, canUndo, canRedo,
                        Modifier.align(Alignment.BottomEnd).imePadding().padding(end = 10.dp, bottom = 8.dp),
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
            AppBar(title, modified, mode, showTitle = false, onMenu, onRename, onMode, onSave) {
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
 * column's width (30–70 %), kept in [AppGraph.uiPreferences].
 */
@Composable
private fun SideBySide(
    graph: AppGraph,
    text: @Composable (Modifier) -> Unit,
    player: PlayerState,
    playerActions: PlayerActions,
) {
    val colors = appColors
    var fraction by remember { mutableFloatStateOf(graph.uiPreferences.sideFraction) }
    var rowWidth by remember { mutableIntStateOf(0) }
    Row(Modifier.fillMaxSize().onSizeChanged { rowWidth = it.width }) {
        text(Modifier.weight(1f - fraction).fillMaxHeight())
        Box(
            Modifier
                .width(14.dp)
                .fillMaxHeight()
                .background(colors.surface)
                .semantics { contentDescription = "Resize the chord sheet" }
                .draggable(
                    state = rememberDraggableState { dx ->
                        if (rowWidth > 0) fraction = clampSideFraction(fraction - dx / rowWidth)
                    },
                    orientation = Orientation.Horizontal,
                    onDragStopped = { graph.uiPreferences.sideFraction = fraction },
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
        metronome = toolbar?.metronome == true,
        speedBadge = toolbar?.let { speedBadge(it.multiplierPct) },
        sheetVisible = sheetVisible == true,
        status = text,
        voicingLabel = selectedVoicingLabel(voicing).orEmpty(),
        instrumentLabel = instruments?.let { currentProgramName(instrumentFamilies(it)) }.orEmpty(),
    )
}

/** Song defaults from the toolbar, before the session sends `SongDefaultsState`. */
private fun fallbackDefaults(t: ToolbarState): SongDefaults {
    val tempo = t.bpmDisplay.toString()
    val time = "${t.beats}/${t.unit}"
    return SongDefaults(
        SongDefaultValue(tempo, false), SongDefaultValue(time, false), SongDefaultValue(t.key, false),
        SongDefaults.summaryOf(tempo, time, t.key),
    )
}

/** In Edit mode, each new status message shows as a short snackbar. */
@Composable
private fun StatusSnackbars(mode: AppMode, text: String?, snackbars: SnackbarHostState) {
    var last by remember { mutableStateOf(text) }
    val currentMode by rememberUpdatedState(mode)
    LaunchedEffect(text) {
        val t = text
        if (t != last) {
            last = t
            // Opening a song switches to Play along with its status: let the mode settle first.
            delay(150)
            if (currentMode == AppMode.EDIT && !t.isNullOrBlank()) snackbars.showSnackbar(t, duration = SnackbarDuration.Short)
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
            state?.let {
                InstrumentPickerSheet(
                    instrumentFamilies(it),
                    family = route.family,
                    onOpenFamily = { i -> go(route.open(i)) },
                    onBack = { go(route.back()) },
                    onChoose = actions::setInstrument,
                    onDismiss = { go(route.back()) },
                    onDone = close,
                )
            }
        }
        is SheetRoute.Speed -> {
            val pct = toolbar?.multiplierPct ?: 100.0
            SpeedSheet(
                pct,
                onSpeed = { actions.setMultiplierPct(it.toDouble()) },
                onReset = actions::resetMultiplier,
                onManual = { go(SheetRoute.Speed(manual = true)) },
                onDismiss = close,
            )
            if (route.manual) {
                SpeedDialog(
                    pct,
                    onApply = {
                        actions.setMultiplierPct(it.toDouble())
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
            val compact = with(density) { LocalWindowInfo.current.containerSize.width.toDp() } < 600.dp
            ChordIdentifierDialog(
                repo = repo,
                commands = tools.screen,
                insertAtCursor = tools::insertChord,
                compact = compact,
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
    return SongDefaults(v(s.tempo), v(s.time), v(s.key), s.summary)
}
