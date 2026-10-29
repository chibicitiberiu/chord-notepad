package io.github.chibicitiberiu.chordnotepad.ui

import androidx.activity.compose.BackHandler
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import io.github.chibicitiberiu.chordnotepad.AppGraph
import io.github.chibicitiberiu.chordnotepad.about.BuildInfo
import io.github.chibicitiberiu.chordnotepad.bridge.ScreenCommands
import io.github.chibicitiberiu.chordnotepad.ui.about.APP_LICENCE_ID
import io.github.chibicitiberiu.chordnotepad.ui.about.AboutScreen
import io.github.chibicitiberiu.chordnotepad.ui.about.LicenceDetailScreen
import io.github.chibicitiberiu.chordnotepad.ui.about.LicencesScreen
import io.github.chibicitiberiu.chordnotepad.ui.about.Pages
import io.github.chibicitiberiu.chordnotepad.ui.help.QuickStartLaunch
import io.github.chibicitiberiu.chordnotepad.ui.help.QuickStartRoute
import io.github.chibicitiberiu.chordnotepad.ui.help.UserGuideScreen
import io.github.chibicitiberiu.chordnotepad.ui.main.Navigation
import io.github.chibicitiberiu.chordnotepad.ui.main.SongScreen
import io.github.chibicitiberiu.chordnotepad.ui.requests.SessionRequests
import io.github.chibicitiberiu.chordnotepad.ui.settings.SettingsPage
import io.github.chibicitiberiu.chordnotepad.ui.settings.SettingsScreen
import io.github.chibicitiberiu.chordnotepad.ui.tools.ToolActions

/**
 * The main screen ([SongScreen]), or a page the drawer opened over it
 * (Settings, User guide, Quick start, About and the licences).
 * They replace the editor rather than cover it, so nothing underneath keeps
 * the keyboard focus. Back closes the app (asking about unsaved changes) from
 * the editor, and goes up one page from About; Settings handles it itself.
 */
@Composable
fun MainScreen(graph: AppGraph, onCloseApproved: () -> Unit) {
    val actions = remember(graph) { MainActions(graph.commands, graph.editor, graph.mode) }
    val document by graph.repository.document.collectAsState()
    val snackbars = remember { SnackbarHostState() }
    var page by rememberSaveable { mutableStateOf(Pages.MAIN) }

    // CloseApproved goes through the app-scoped CloseCoordinator, so a close
    // approved while the activity is being recreated still finishes the new one.
    val finish by graph.close.finishRequested.collectAsState()
    LaunchedEffect(finish) {
        if (finish) {
            graph.close.consumeFinish()
            onCloseApproved()
        }
    }
    // Android has no File > Exit: Back is the desktop's window close. With
    // unsaved changes it asks first (request_close -> the unsaved-changes
    // dialog -> CloseApproved -> finish); otherwise the system handles it.
    BackHandler(enabled = page == Pages.MAIN && document?.isModified == true) {
        graph.close.onCloseRequested()
        actions.requestClose()
    }
    // Settings handles Back itself (up a page, or leave asking about changes).
    // The User Guide goes back through its own pages first (UserGuideScreen).
    BackHandler(enabled = page != Pages.MAIN && page != Pages.SETTINGS && page != Pages.SETTINGS_VOICINGS && page != Pages.USER_GUIDE) {
        page = Pages.parent(page)
    }

    // First run: the Quick Start tour opens once per process start, when the
    // setting (known a moment after launch) says so. The flag lives in the
    // app-scoped graph, so a rotation does not bring it back.
    val settings by graph.repository.settings.collectAsState()
    LaunchedEffect(settings, page) {
        if (page == Pages.MAIN) {
            val decision = QuickStartLaunch.decide(settings, graph.quickStartShown)
            graph.quickStartShown = decision.decided
            if (decision.open) page = Pages.QUICK_START
        }
    }

    val nav = remember {
        object : Navigation {
            override fun settings(voicings: Boolean) {
                page = if (voicings) Pages.SETTINGS_VOICINGS else Pages.SETTINGS
            }
            override fun userGuide() {
                page = Pages.USER_GUIDE
            }
            override fun quickStart() {
                page = Pages.QUICK_START
            }
            override fun about() {
                page = Pages.ABOUT
            }
        }
    }

    when {
        page == Pages.MAIN -> SongScreen(graph, actions, snackbars, nav)
        page == Pages.USER_GUIDE -> UserGuideScreen(onClose = { page = Pages.MAIN })
        page == Pages.QUICK_START -> QuickStartRoute(graph, onClose = { page = Pages.MAIN })
        page == Pages.SETTINGS || page == Pages.SETTINGS_VOICINGS -> SettingsScreen(
            repo = graph.repository,
            commands = remember(graph) { ScreenCommands(graph.pyHost) },
            onClosed = { page = Pages.MAIN },
            initialPage = if (page == Pages.SETTINGS_VOICINGS) SettingsPage.VOICINGS else null,
        )
        page == Pages.ABOUT -> AboutScreen(
            info = BuildInfo.current,
            onBack = { page = Pages.MAIN },
            onOpenLicence = { page = Pages.detail(APP_LICENCE_ID) },
            onOpenLicences = { page = Pages.LICENCES },
        )
        page == Pages.LICENCES -> LicencesScreen(onBack = { page = Pages.ABOUT }, onOpen = { page = Pages.detail(it) })
        else -> Pages.detailId(page)?.let { id ->
            LicenceDetailScreen(id, onBack = { page = Pages.parent(page) })
        }
    }

    SessionRequests(
        graph.repository.pendingRequest, graph.requests, graph.repository,
        onSuggestCapo = remember(graph) {
            val tools = ToolActions(graph.commands, ScreenCommands(graph.pyHost), graph.editor)
            tools::suggestCapo
        },
    )
    ErrorPresenter(graph.errorQueue, snackbars)
}
