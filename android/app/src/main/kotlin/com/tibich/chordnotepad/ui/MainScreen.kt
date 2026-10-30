package com.tibich.chordnotepad.ui

import androidx.activity.compose.BackHandler
import androidx.activity.compose.LocalActivity
import androidx.compose.material3.SnackbarHostState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import com.tibich.chordnotepad.AppGraph
import com.tibich.chordnotepad.about.BuildInfo
import com.tibich.chordnotepad.bridge.ScreenCommands
import com.tibich.chordnotepad.bridge.StartupScreen
import com.tibich.chordnotepad.ui.about.APP_LICENCE_ID
import com.tibich.chordnotepad.ui.about.AboutScreen
import com.tibich.chordnotepad.ui.about.LicenceDetailScreen
import com.tibich.chordnotepad.ui.about.LicencesScreen
import com.tibich.chordnotepad.ui.about.Pages
import com.tibich.chordnotepad.ui.help.QuickStartRoute
import com.tibich.chordnotepad.ui.help.UserGuideScreen
import com.tibich.chordnotepad.ui.main.Navigation
import com.tibich.chordnotepad.ui.main.SongScreen
import com.tibich.chordnotepad.ui.requests.SessionRequests
import com.tibich.chordnotepad.ui.settings.SettingsPage
import com.tibich.chordnotepad.ui.settings.SettingsScreen
import com.tibich.chordnotepad.ui.support.SupportPrompt
import com.tibich.chordnotepad.ui.support.SupportThankYou
import com.tibich.chordnotepad.ui.tools.ToolActions

/**
 * The main screen ([SongScreen]), or a page the drawer opened over it
 * (Settings, User guide, Quick start, About and the licences), and the
 * startup screen the session picked (Quick Start or the support prompt).
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
    // The startup screen comes from the session (its answer to app_started),
    // so a rotation doesn't bring it back once dismissed. Closing it tells the
    // session at once; the repository forgets it meanwhile.
    val startup by graph.repository.startup.collectAsState()
    val dismissStartup = remember(graph) {
        {
            graph.repository.startupDismissed()
            graph.commands.dismissStartupScreen()
        }
    }
    LaunchedEffect(startup?.screen) {
        if (startup?.screen == StartupScreen.QUICK_START) page = Pages.QUICK_START
    }
    val closeQuickStart = {
        page = Pages.MAIN
        if (graph.repository.startup.value?.screen == StartupScreen.QUICK_START) dismissStartup()
    }

    // Settings handles Back itself (up a page, or leave asking about changes).
    // The User Guide goes back through its own pages first (UserGuideScreen).
    BackHandler(enabled = page != Pages.MAIN && page != Pages.SETTINGS && page != Pages.SETTINGS_VOICINGS && page != Pages.USER_GUIDE) {
        if (page == Pages.QUICK_START) {
            closeQuickStart()
        } else {
            page = Pages.parent(page)
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
        page == Pages.QUICK_START -> QuickStartRoute(graph, onClose = closeQuickStart)
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

    // Over the editor only, and not while a dialog of the session's is up.
    val pending by graph.repository.pendingRequest.collectAsState()
    if (startup?.screen == StartupScreen.SUPPORT_PROMPT && page == Pages.MAIN && pending == null) {
        val activity = LocalActivity.current
        val price by graph.supportBilling.price.collectAsState()
        SupportPrompt(
            price = price,
            onSupport = { activity?.let(graph.supportBilling::launchPurchase) },
            onDismiss = dismissStartup,
        )
    }
    // After a purchase that completed while the app runs (from the prompt or Settings).
    SupportThankYou(graph.supportBilling)
}
