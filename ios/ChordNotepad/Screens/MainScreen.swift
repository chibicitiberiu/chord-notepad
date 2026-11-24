import ChordNotepadKit
import SwiftUI

/// What the main screen's controls do; nil in the preview catalog (inert).
struct MainActions {
    var appBar: AppBarActions
    var player: PlayerActions
    /// The Edit ribbon's buttons and the floating undo chip.
    var ribbon: (EditorAction) -> Void
    var chordSheet: ChordSheetActions
    var menu: (MenuAction) -> Void
    /// Close what is open over the screen (the menu, a dialog).
    var close: () -> Void
    var rename: (String) -> Void
    /// Save As under a name (a rename the storage refused).
    var saveAs: (String) -> Void
    /// The unsaved-changes question's answer.
    var discard: (DiscardChoice) -> Void
    var dismissSnackbar: (Int) -> Void
    /// Why a greyed button does nothing.
    var notice: (String) -> Void
    /// A tap in the player's sheets, the ribbon's tools and their dialogs (the kit's reducer).
    var sheet: (SheetEvent) -> Void
    /// The find bar's controls and the ribbon's Find.
    var find: (FindAction) -> Void = { _ in }
    /// The landscape column's handle was let go at this share (kept across launches).
    var sideFraction: (Double) -> Void = { _ in }
}

/// The main screen (Android's `SongScreen.kt`): the app bar with its Edit /
/// Play tabs, the Edit ribbon or the player, the song text, the chord sheet
/// (Play only: below the text upright, beside it on its side), the ☰ menu,
/// the rename dialogs and the snackbars, from a ``SessionSnapshot``, the
/// editor's ``EditorModel`` and the screen's own ``MainUiState``.
///
/// The live app and the preview catalog draw the same view; the catalog
/// passes `scrolls: false`, since ImageRenderer can't draw UIKit views or a
/// ScrollView: the text is ``EditorPreview`` and the menu doesn't scroll.
/// The player's sheets, the ribbon's tools and their dialogs are drawn here
/// too, over the screen; Diagnostics and Examples are the live view's system
/// sheets (`MainView`).
struct MainScreen: View {
    let snapshot: SessionSnapshot
    var editorModel = EditorModel()
    /// The live editor (nil in the catalog).
    var editor: EditorController?
    var ui = MainUiState()
    /// Python and the session are still starting.
    var starting = false
    /// Why the app couldn't start.
    var failure: String?
    var scrolls = true
    var actions: MainActions?
    /// The chord sheet's buffers (the session's, or a fixture's); nil: no sheet.
    var chordSheet: ChordSheetSource?
    var snackbar: Snackbar?
    /// The rename dialog's field.
    var renameName: Binding<String> = .constant("")
    /// The full-screen page the route opens (Settings, About, the licences),
    /// over everything but the snackbar; the live view makes it.
    var page: AnyView?
    /// The landscape chord sheet column's share of the width, as last kept.
    var sideFraction = MainMetrics.sideFractionDefault

    @Environment(\.colorScheme) private var scheme
    @Environment(\.dynamicTypeSize) private var textSize
    /// The column's share while its handle is dragged.
    @State private var dragFraction: Double?
    @State private var sideDragStart: Double?

    private var colors: AppColors { .forScheme(dark: scheme == .dark) }
    private var sheetVisible: Bool { snapshot.chordSheet?.visible ?? false }

    /// The file name without its extension (Rename shows the whole one).
    private var title: String {
        snapshot.document.map { renameFieldText($0.displayName) } ?? "Chord Notepad"
    }

    var body: some View {
        GeometryReader { window in
            let size = window.size
            let layout = ScreenLayout.of(width: Double(size.width), height: Double(size.height), mode: ui.mode,
                                         sheetVisible: sheetVisible)
            let header = layout.headerHeight(mode: ui.mode)
            let collapsed = collapseHeader(mode: ui.mode, keyboardVisible: ui.keyboardHeight > 0,
                                           textRoom: Double(size.height) - header)
            VStack(spacing: 0) {
                if !collapsed {
                    headerView(layout: layout, width: Double(size.width))
                }
                if starting {
                    colors.primary.swiftUI.opacity(0.5).frame(height: 2)
                }
                if let failure {
                    Text("Chord Notepad couldn't start: \(failure)")
                        .font(.footnote)
                        .foregroundColor(colors.error.swiftUI)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                }
                content(layout: layout, size: size, header: collapsed ? 0 : header)
                if ui.mode == .play && !layout.sideBySide {
                    player(compact: false)
                }
            }
            .overlay(alignment: .bottomTrailing) {
                if collapsed { undoChip }
            }
            .overlay(alignment: .bottom) {
                if ui.route == .identify { snackbarView(layout) }
            }
            .overlay { routeOverlay }
            .overlay(alignment: .bottom) {
                // Over a sheet, so a greyed control's reason shows (Android: a Toast); under the
                // identifier, which covers the screen as Android's dialog does.
                if ui.route != .identify { snackbarView(layout) }
            }
        }
        .background(colors.surface.swiftUI)
    }

    @ViewBuilder
    private func snackbarView(_ layout: ScreenLayout) -> some View {
        if let snackbar {
            SnackbarView(snackbar: snackbar, colors: colors) { actions?.dismissSnackbar(snackbar.id) }
                .padding(.bottom, ui.route.isFullPage ? 16
                         : CGFloat(snackbarClearance(mode: ui.mode, sideBySide: layout.sideBySide)))
                .transition(.move(edge: .bottom).combined(with: .opacity))
        }
    }

    private func sheet(_ event: SheetEvent) {
        actions?.sheet(event)
    }

    // MARK: - The header

    @ViewBuilder
    private func headerView(layout: ScreenLayout, width: Double) -> some View {
        let tabLabels = modeTabLabelsShown(windowWidth: width, accessibilityText: textSize.isAccessibilitySize)
        VStack(spacing: 0) {
            if layout.oneLineHeader {
                AppBar(title: title, modified: snapshot.document?.isModified ?? false, mode: ui.mode, colors: colors,
                       tabLabels: tabLabels, titleMaxWidth: CGFloat(oneLineTitleMaxWidth(width)),
                       actions: actions?.appBar) {
                    colors.line.swiftUI.frame(width: 1).frame(maxHeight: .infinity)
                    ribbon.frame(maxWidth: .infinity)
                }
            } else {
                AppBar(title: title, modified: snapshot.document?.isModified ?? false, mode: ui.mode, colors: colors,
                       tabLabels: tabLabels, actions: actions?.appBar)
                if ui.mode == .edit {
                    ribbon
                }
            }
            colors.line.swiftUI.frame(height: 1)
        }
        // The bar is a fixed 48 pt: its title follows the text size up to a point.
        .dynamicTypeSize(...DynamicTypeSize.accessibility2)
    }

    private var ribbon: some View {
        EditRibbon(canUndo: editorModel.canUndo, canRedo: editorModel.canRedo, notation: editorModel.notation,
                   readOnly: editorModel.readOnly, perform: actions?.ribbon,
                   tool: actions.map { actions in { actions.sheet(.ribbon($0)) } },
                   find: actions.map { actions in { actions.find(.open(replace: true)) } }, scrolls: scrolls)
    }

    // MARK: - The text, the chord sheet and the player

    /// The text keeps its place in the view tree whatever the layout, so the
    /// live text view (and its scroll position) stays when the tab changes,
    /// as both of Android's modes share one scroll.
    private func content(layout: ScreenLayout, size: CGSize, header: Double) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                VStack(spacing: 0) {
                    text
                    if editorModel.find.open {
                        FindBarView(bar: editorModel.find, colors: colors, live: scrolls) { actions?.find($0) }
                    }
                }
                if layout.sideBySide {
                    sideColumn(size: size, header: header)
                }
            }
            if layout.sheetBelow, let state = snapshot.chordSheet, let chordSheet {
                ChordSheetSplitView(state: state, source: chordSheet,
                                    available: Double(size.height) - header - MainMetrics.playerHeight,
                                    window: size, interactive: scrolls, actions: actions?.chordSheet)
            }
        }
    }

    /// Landscape Play: after the text, a handle, then a column with the chord
    /// sheet and the compact player. The handle sets the column's share
    /// (30–70 %, wider when the player needs it).
    @ViewBuilder
    private func sideColumn(size: CGSize, header: Double) -> some View {
        let row = Double(size.width)
        let lower = minSideFraction(row)
        let fraction = clampSideFraction(dragFraction ?? sideFraction, min: lower)
        let column = (row - MainMetrics.sideHandleWidth) * fraction
        let paneHeight = Double(size.height) - header - MainMetrics.playerHeight
        handle(row: row, lower: lower)
        VStack(spacing: 0) {
            if let state = snapshot.chordSheet, let chordSheet {
                ChordSheetPane(state: state, source: chordSheet, height: paneHeight, interactive: scrolls,
                               actions: actions?.chordSheet)
                    .frame(height: CGFloat(max(paneHeight, 0)))
            }
            player(compact: true)
        }
        .frame(width: CGFloat(column))
    }

    private func handle(row: Double, lower: Double) -> some View {
        ZStack {
            colors.surface.swiftUI
            HStack(spacing: 0) {
                colors.line.swiftUI.frame(width: 1)
                Spacer(minLength: 0)
            }
            Capsule().fill(colors.grip.swiftUI).frame(width: 4, height: 36)
        }
        .frame(width: CGFloat(MainMetrics.sideHandleWidth))
        .contentShape(Rectangle())
        .gesture(DragGesture(minimumDistance: 2)
            .onChanged { drag in
                guard scrolls, row > 0 else { return }
                let start = sideDragStart ?? clampSideFraction(dragFraction ?? sideFraction, min: lower)
                sideDragStart = start
                dragFraction = clampSideFraction(start - Double(drag.translation.width) / row, min: lower)
            }
            .onEnded { _ in
                // Kept when the handle is let go, as Android's onDragStopped.
                if let dragFraction { actions?.sideFraction(dragFraction) }
                sideDragStart = nil
                dragFraction = nil
            })
        .accessibilityLabel("Resize the chord sheet")
    }

    @ViewBuilder
    private var text: some View {
        if scrolls, let editor {
            SongEditor(controller: editor)
                .overlay(alignment: .topLeading) {
                    if editorModel.text.isEmpty && ui.mode == .edit { placeholder }
                }
        } else {
            EditorPreview(model: editorModel, playhead: playheadUTF16, play: ui.mode == .play)
        }
    }

    /// The session's playhead in the editor's text (UTF-16), for the catalog's marker.
    private var playheadUTF16: Int? {
        snapshot.playback?.playheadOffset.map { OffsetMapper(editorModel.text).toUTF16($0) }
    }

    /// The empty editor's "Type or paste a song here", never part of the text.
    private var placeholder: some View {
        Text(EditorPlaceholder.text)
            .font(.system(.body, design: .monospaced))
            .foregroundStyle(.secondary)
            .padding(.horizontal, EditorTextView.horizontalInset)
            .padding(.vertical, EditorTextView.verticalInset)
            .allowsHitTesting(false)
    }

    private func player(compact: Bool) -> some View {
        let fallback = failure.map { "Chord Notepad couldn't start: \($0)" } ?? (starting ? "Starting…" : nil)
        var state = PlayerState.of(snapshot, fallbackStatus: fallback)
        if let failure { state.status = "Chord Notepad couldn't start: \(failure)" }
        return PlayerBar(state: state, colors: colors, compact: compact, actions: actions?.player,
                         explainLocked: { actions?.notice($0) })
    }

    /// With the header collapsed (Edit, keyboard up, little room): undo and redo
    /// float by the keyboard, as on Android.
    private var undoChip: some View {
        HStack(spacing: 0) {
            chipButton("arrow.uturn.backward", "Undo", enabled: editorModel.canUndo) { actions?.ribbon(.undo) }
            colors.line.swiftUI.frame(width: 1, height: 22)
            chipButton("arrow.uturn.forward", "Redo", enabled: editorModel.canRedo) { actions?.ribbon(.redo) }
        }
        .background(colors.surfaceHigh.swiftUI, in: Capsule())
        .shadow(color: .black.opacity(0.2), radius: 3, y: 1)
        .padding(.trailing, 10)
        .padding(.bottom, 8)
        .dynamicTypeSize(...DynamicTypeSize.xLarge)
    }

    private func chipButton(_ symbol: String, _ label: String, enabled: Bool,
                            action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.body.weight(.medium))
                .foregroundColor(RibbonTints.undo.opacity(enabled ? 1 : AppColors.disabledAlpha))
                .frame(width: 44, height: 40)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityLabel(label)
    }

    // MARK: - Over the screen

    @ViewBuilder
    private var routeOverlay: some View {
        // The session's unsaved-changes question is over everything else.
        if case .confirmDiscard? = snapshot.request {
            DiscardDialog(colors: colors) { actions?.discard($0) }
        } else {
            ZStack {
                routeView
                if case .insertDirective(let request)? = snapshot.request {
                    insertDialog(request)
                }
                if let advice = snapshot.capoAdvice, advice.active {
                    CapoDialog(state: advice, chosen: ui.capoChosen(advice), canApply: ui.capoCanApplyNow(advice),
                               colors: colors, live: scrolls, event: sheet)
                }
            }
        }
    }

    /// The pending Insert request's dialog; it asks the session to check its
    /// first fields when it appears (a kind it doesn't know is cancelled then).
    @ViewBuilder
    private func insertDialog(_ request: InsertDirectiveRequest) -> some View {
        ZStack {
            if let state = ui.directiveForm(for: request, snapshot: snapshot) {
                let choices = snapshot.insertChoices(request)
                InsertDirectiveDialog(request: request, state: state,
                                      verdict: ui.directiveVerdict(for: request, snapshot: snapshot),
                                      keys: choices.keys, units: choices.units, colors: colors, live: scrolls,
                                      event: sheet)
            }
        }
        .task(id: request.requestId) { sheet(.directiveShown) }
    }

    @ViewBuilder
    private var routeView: some View {
        switch ui.route {
        case .menu:
            AppMenuPanel(recent: recentEntries(snapshot.recentDocuments, max: snapshot.settings?.values.maxRecentFiles),
                         colors: colors, scrolls: scrolls,
                         choose: { actions?.menu($0) }, close: { actions?.close() })
        case .rename:
            RenameDialog(displayName: snapshot.document?.displayName ?? "", colors: colors, name: renameName,
                         refusal: ui.renameRefusal, live: scrolls,
                         rename: { actions?.rename($0) }, cancel: { actions?.close() })
        case .renameFailed(let name, let reason, let canSaveAs):
            RenameFailedDialog(name: name, reason: reason, canSaveAs: canSaveAs, colors: colors,
                               saveAs: { actions?.saveAs($0) }, dismiss: { actions?.close() })
        case .voicing:
            VoicingPickerSheet(state: snapshot.voicingMenu, colors: colors, live: scrolls, event: sheet)
        case .instrument(let family):
            InstrumentPickerSheet(state: snapshot.instrumentMenu, family: family, colors: colors, live: scrolls,
                                  event: sheet)
        case .speed(let manual):
            ZStack {
                SpeedSheet(pct: snapshot.toolbar?.multiplierPct ?? 100, slider: ui.tools.speedSlider, colors: colors,
                           live: scrolls, event: sheet)
                if manual, let entry = ui.tools.speedEntry {
                    SpeedDialog(entry: entry, colors: colors, live: scrolls, event: sheet)
                }
            }
        case .songDefaults:
            if let defaults = snapshot.songDefaults {
                ZStack {
                    SongDefaultsSheet(state: defaults, keys: snapshot.toolbar?.keyOptions ?? [], colors: colors,
                                      directive: EditorPalette.forScheme(dark: scheme == .dark).directive.swiftUI,
                                      live: scrolls, event: sheet)
                    if let tempo = ui.tools.tempoEntry {
                        TempoDialog(text: tempo, colors: colors, live: scrolls, event: sheet)
                    }
                }
            }
        case .insert:
            InsertSheet(colors: colors, live: scrolls, event: sheet)
        case .transpose(let selection):
            TransposeDialog(hasSelection: selection, form: ui.tools.transpose, colors: colors, live: scrolls,
                            event: sheet)
        case .identify:
            ChordIdentifierView(state: snapshot.identifier, model: ui.tools.identifier,
                                expired: ui.tools.identifierExpired, status: snapshot.status?.text, colors: colors,
                                live: scrolls, event: sheet)
        case .settings, .about, .licences, .licence, .userGuide, .quickStart:
            if let page { page }
        default:
            EmptyView()
        }
    }
}
