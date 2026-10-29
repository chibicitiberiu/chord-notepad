package io.github.chibicitiberiu.chordnotepad.ui

import android.os.Build
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.ripple
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import io.github.chibicitiberiu.chordnotepad.AppGraph
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.bridge.DocumentState
import io.github.chibicitiberiu.chordnotepad.bridge.HostStatus
import io.github.chibicitiberiu.chordnotepad.bridge.PlayAction
import io.github.chibicitiberiu.chordnotepad.ui.editor.ChordEditor
import io.github.chibicitiberiu.chordnotepad.ui.icons.AppIcons
import io.github.chibicitiberiu.chordnotepad.ui.toolbar.SessionToolbar

// The desktop transport icons' pastel tints (main_window.py).
private val PlayGreen = Color(0xFF5FAF63)
private val PauseBlue = Color(0xFF588CC7)
private val StopCoral = Color(0xFFF08080)

/** Below this width the toolbar can be folded away (phones in portrait). */
private val CompactWidth = 600.dp

/**
 * The main screen: app bar (title, transport, menu), toolbar, editor and
 * status line, over the session's states. One adaptive layout: on narrow
 * screens the toolbar scrolls sideways and can be hidden.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun MainScreen(graph: AppGraph, onCloseApproved: () -> Unit) {
    val repo = graph.repository
    val actions = remember(graph) { MainActions(graph.commands, graph.editor) }
    val host by repo.hostStatus.collectAsState()
    val document by repo.document.collectAsState()
    val editorState by repo.editor.collectAsState()
    val toolbar by repo.toolbar.collectAsState()
    val status by repo.status.collectAsState()
    val recent by repo.recentDocuments.collectAsState()
    val snackbars = remember { SnackbarHostState() }
    var toolbarShown by rememberSaveable { mutableStateOf(true) }

    LaunchedEffect(Unit) { repo.closeApproved.collect { onCloseApproved() } }

    BoxWithConstraints(Modifier.fillMaxSize()) {
        val compact = maxWidth < CompactWidth
        Scaffold(
            modifier = Modifier.onPreviewKeyEvent { actions.handleShortcut(it) },
            topBar = {
                TopAppBar(
                    title = { Text(titleOf(document), maxLines = 1, overflow = TextOverflow.Ellipsis) },
                    actions = {
                        PlayPauseButton(
                            action = toolbar?.playAction ?: PlayAction.PLAY,
                            onClick = actions::playPause,
                            onLongClick = actions::playFromCursor,
                        )
                        IconButton(onClick = actions::stop) {
                            Icon(AppIcons.Stop, stringResource(R.string.stop), tint = StopCoral)
                        }
                        if (compact) {
                            IconButton(onClick = { toolbarShown = !toolbarShown }) {
                                Icon(
                                    if (toolbarShown) AppIcons.ExpandLess else AppIcons.ExpandMore,
                                    stringResource(if (toolbarShown) R.string.toolbar_hide else R.string.toolbar_show),
                                )
                            }
                        }
                        OverflowMenu(
                            actions = actions,
                            recent = recent?.items.orEmpty(),
                            canUndo = graph.editor.state.undoState.canUndo,
                            canRedo = graph.editor.state.undoState.canRedo,
                            onSelectAll = {
                                graph.editor.state.edit { selection = TextRange(0, length) }
                            },
                        )
                    },
                )
            },
            snackbarHost = { SnackbarHost(snackbars) },
        ) { padding ->
            Column(
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .consumeWindowInsets(padding)
                    .imePadding(),
            ) {
                if (host is HostStatus.Starting) LinearProgressIndicator(Modifier.fillMaxWidth())
                val bar = toolbar
                if (bar != null && (toolbarShown || !compact)) {
                    SessionToolbar(bar, actions, Modifier.fillMaxWidth())
                }
                ChordEditor(
                    controller = graph.editor,
                    editorState = editorState,
                    onStepFontSize = actions::stepFontSize,
                    modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 6.dp),
                )
                HorizontalDivider(Modifier.padding(top = 4.dp))
                Text(
                    statusText(host, status?.text),
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 4.dp),
                )
            }
        }
    }

    InterimRequests(graph)
    ErrorPresenter(graph.errorQueue, snackbars)
}

/** The document's name with the desktop's unsaved-changes marker (`song.txt*`). */
@Composable
private fun titleOf(document: DocumentState?): String {
    val doc = document ?: return stringResource(R.string.app_name)
    return doc.displayName + if (doc.isModified) "*" else ""
}

@Composable
private fun statusText(host: HostStatus, status: String?): String = when (host) {
    is HostStatus.Failed -> stringResource(R.string.status_failed, host.message)
    HostStatus.NotStarted, HostStatus.Starting -> status ?: stringResource(R.string.status_starting)
    else -> status.orEmpty()
}

/** Play/Pause; a long press plays from the cursor (the desktop's Shift+click). */
@OptIn(ExperimentalFoundationApi::class)
@Composable
private fun PlayPauseButton(action: PlayAction, onClick: () -> Unit, onLongClick: () -> Unit) {
    val pausing = action == PlayAction.PAUSE
    val label = stringResource(
        when (action) {
            PlayAction.PLAY -> R.string.play
            PlayAction.PAUSE -> R.string.pause
            PlayAction.RESUME -> R.string.resume
        },
    )
    Box(
        Modifier
            .size(48.dp)
            .clip(CircleShape)
            .combinedClickable(
                interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() },
                indication = ripple(bounded = false, radius = 20.dp),
                role = Role.Button,
                onClickLabel = label,
                onLongClickLabel = stringResource(R.string.play_from_cursor),
                onLongClick = onLongClick,
                onClick = onClick,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            if (pausing) AppIcons.Pause else AppIcons.Play,
            contentDescription = label,
            tint = if (pausing) PauseBlue else PlayGreen,
        )
    }
}

/** Material 3 with the device's colours where there are any; the editor keeps its own. */
@Composable
fun ChordNotepadTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val context = LocalContext.current
    val scheme = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            if (dark) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        dark -> darkColorScheme()
        else -> lightColorScheme()
    }
    MaterialTheme(colorScheme = scheme) { Surface(Modifier.fillMaxSize(), content = content) }
}
