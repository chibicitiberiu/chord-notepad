import ChordNotepadKit
import Combine
import SwiftUI
import UIKit

/// The live main screen: ``MainScreen`` over the app's session, with the
/// system sheets it opens (Diagnostics, Examples) and the keyboard's height
/// for the collapsing header. The player's sheets and the tools are the
/// screen's own (`MainScreen`).
struct MainView: View {
    @ObservedObject var model: AppModel
    /// The model's editor, observed for the ribbon (undo, redo, notation).
    @ObservedObject var editor: EditorController
    @State private var renameName = ""

    var body: some View {
        MainScreen(snapshot: model.snapshot, editorModel: editor.model, editor: editor, ui: model.ui,
                   starting: model.phase == .starting || model.phase == .idle, failure: failure,
                   actions: actions, chordSheet: model.chordSheet, snackbar: model.snackbars.shown,
                   renameName: $renameName, page: page, sideFraction: model.sideFraction,
                   exportDialog: model.exportDialog)
            .animation(.easeOut(duration: 0.2), value: model.snackbars.shown)
            .sheet(isPresented: route(.diagnostics)) {
                DiagnosticsView(model: model)
            }
            .sheet(isPresented: route(.examples)) {
                ExamplesSheet(names: AppDocumentStore.exampleNames, colors: colors,
                              choose: { name in
                                  close()
                                  model.openExample(name)
                              },
                              done: close)
                    .presentationDetents([.medium, .large])
            }
            .onChange(of: model.ui.route) { _, route in
                if route == .rename {
                    renameName = renameFieldText(model.snapshot.document?.displayName ?? "")
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillChangeFrameNotification)) {
                keyboardChanged($0)
            }
            .onReceive(NotificationCenter.default.publisher(for: UIResponder.keyboardWillHideNotification)) { _ in
                if model.ui.keyboardHeight != 0 { model.ui.keyboardHeight = 0 }
            }
    }

    @Environment(\.colorScheme) private var scheme
    @Environment(\.openURL) private var openURL

    /// Settings, About, the licences or a licence's text, when the route opens one.
    private var page: AnyView? {
        switch model.ui.route {
        case .settings:
            guard let settings = model.settings else { return nil }
            return AnyView(SettingsScreen(controller: settings, schema: model.voicingSchema,
                                          act: { model.settingsAct($0) }))
        case .about:
            return AnyView(AboutScreen(info: AboutBuildInfo.from(info: Bundle.main.infoDictionary ?? [:],
                                                                 debug: AppEnvironment.debugBuild),
                                       actions: aboutActions))
        case .licences:
            return AnyView(LicencesScreen(entries: AppLicences.entries, actions: aboutActions))
        case .licence(let id, let fromAbout):
            let entry = AppLicences.entries.first { $0.id == id }
            return AnyView(LicenceDetailScreen(entry: entry, text: entry.flatMap(AppLicences.text),
                                               backTitle: fromAbout ? AboutTexts.appName : AboutTexts.licencesTitle,
                                               actions: aboutActions))
        case .userGuide:
            return AnyView(UserGuideScreen(close: { model.pageBack() },
                                           linkFailed: { model.notice(AboutTexts.openFailed) },
                                           loaded: { model.guideLoaded($0) }))
        case .quickStart:
            return AnyView(QuickStartScreen(
                content: model.snapshot.quickStart,
                showAtStartup: quickStartShowsAtStartup(picked: model.quickStartPicked, settings: model.snapshot.settings,
                                                        content: model.snapshot.quickStart),
                setShowAtStartup: { model.setShowQuickStart($0) },
                close: { model.closeTour() }))
        default:
            return nil
        }
    }

    private var aboutActions: AboutActions {
        AboutActions(back: { model.pageBack() },
                     openLicence: { id, fromAbout in model.ui.route = .licence(id: id, fromAbout: fromAbout) },
                     openLicences: { model.ui.route = .licences },
                     openLink: { link in
                         guard let url = URL(string: link) else { return }
                         openURL(url) { opened in
                             if !opened { model.notice(AboutTexts.openFailed) }
                         }
                     })
    }

    private var colors: AppColors { .forScheme(dark: scheme == .dark) }

    private var failure: String? {
        if case .failed(let message) = model.phase { return message }
        return nil
    }

    private func route(_ target: MainRoute) -> Binding<Bool> {
        Binding(get: { model.ui.route == target },
                set: { shown in
                    if !shown && model.ui.route == target { model.ui.route = .none }
                })
    }

    private func close() {
        model.ui.route = .none
        model.ui.renameRefusal = nil
    }

    private func open(_ route: MainRoute) {
        model.ui.route = route
    }

    /// How much of the window the software keyboard covers (a hardware
    /// keyboard's shortcut bar is short; it counts too). The keyboard's frame
    /// is in the screen's coordinates; the window is the whole screen only
    /// when the app is: in Split View, Slide Over and Stage Manager it covers
    /// what lies over the window (``keyboardOverlap(window:keyboard:)``).
    private func keyboardChanged(_ notification: Notification) {
        guard let frame = notification.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect else { return }
        guard let scene = UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene }).first,
              let window = scene.keyWindow ?? scene.windows.first else { return }
        let inScreen = window.convert(window.bounds, to: scene.screen.coordinateSpace)
        let height = keyboardOverlap(window: PointRect(inScreen), keyboard: PointRect(frame))
        if model.ui.keyboardHeight != height { model.ui.keyboardHeight = height }
    }

    private var actions: MainActions {
        MainActions(
            appBar: AppBarActions(menu: { open(.menu) },
                                  rename: { open(.rename) },
                                  mode: { model.selectMode($0) },
                                  save: { model.save() }),
            player: PlayerActions(songDefaults: { model.sheet(.open(.songDefaults)) },
                                  voicing: { model.sheet(.open(.voicing)) },
                                  instrument: { model.sheet(.open(.instrument(family: nil))) },
                                  rewind: { model.rewind() },
                                  playPause: { model.playPause() },
                                  toggleMetronome: { model.toggleMetronome() },
                                  speed: { model.sheet(.open(.speed(manual: false))) },
                                  toggleSheet: { model.toggleChordSheet() }),
            ribbon: { editor.perform($0) },
            chordSheet: ChordSheetActions(
                selectView: { model.session?.submit(.setChordSheetView(viewId: $0)) },
                zoom: { model.session?.submit(.chordSheetZoom(step: $0)) },
                audition: { model.audition(index: $0) },
                setHeight: { model.session?.submit(.setChordSheetHeight(px: $0)) }),
            menu: { model.choose($0) },
            close: { close() },
            rename: { model.rename($0) },
            saveAs: { name in
                close()
                model.saveAs(name: name)
            },
            discard: { model.answerDiscard($0) },
            dismissSnackbar: { model.dismissSnackbar($0) },
            notice: { model.notice($0) },
            sheet: { model.sheet($0) },
            find: { editor.find($0) },
            sideFraction: { model.keepSideFraction($0) },
            cancelExport: { model.cancelExport() })
    }
}

extension PointRect {
    init(_ rect: CGRect) {
        self.init(x: Double(rect.minX), y: Double(rect.minY), width: Double(rect.width), height: Double(rect.height))
    }
}
