import ChordNotepadKit
import Combine
import SwiftUI
import UIKit

/// The live main screen: ``MainScreen`` over the app's session, with the
/// sheets it opens (Diagnostics, the player's pickers) and the keyboard's
/// height for the collapsing header.
struct MainView: View {
    @ObservedObject var model: AppModel
    /// The model's editor, observed for the ribbon (undo, redo, notation).
    @ObservedObject var editor: EditorController
    @State private var renameName = ""

    var body: some View {
        MainScreen(snapshot: model.snapshot, editorModel: editor.model, editor: editor, ui: model.ui,
                   starting: model.phase == .starting || model.phase == .idle, failure: failure,
                   actions: actions, chordSheet: model.chordSheet, snackbar: model.snackbars.shown,
                   renameName: $renameName)
            .animation(.easeOut(duration: 0.2), value: model.snackbars.shown)
            .sheet(isPresented: route(.diagnostics)) {
                DiagnosticsView(model: model)
            }
            .sheet(isPresented: route(.voicing)) {
                VoicingSheet(state: model.snapshot.voicingMenu, colors: colors, choose: model.setVoicing,
                             done: close)
                    .presentationDetents([.medium, .large])
            }
            .sheet(isPresented: route(.instrument)) {
                InstrumentSheet(state: model.snapshot.instrumentMenu, colors: colors, choose: model.setInstrument,
                                done: close)
                    .presentationDetents([.medium, .large])
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
            .sheet(isPresented: route(.speed)) {
                ValuesSheet(title: "Speed", rows: ValuesSheet.speed(model.snapshot.toolbar), colors: colors,
                            done: close)
                    .presentationDetents([.medium])
            }
            .sheet(isPresented: route(.songDefaults)) {
                ValuesSheet(title: "Playback settings", rows: ValuesSheet.songDefaults(model.snapshot.songDefaults),
                            colors: colors, done: close)
                    .presentationDetents([.medium])
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

    /// The software keyboard's height over the screen (a hardware keyboard's
    /// shortcut bar is short; it counts too).
    private func keyboardChanged(_ notification: Notification) {
        guard let frame = notification.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? CGRect else { return }
        let screen = UIScreen.main.bounds
        let height = max(0, screen.maxY - frame.minY)
        if model.ui.keyboardHeight != Double(height) { model.ui.keyboardHeight = Double(height) }
    }

    private var actions: MainActions {
        MainActions(
            appBar: AppBarActions(menu: { open(.menu) },
                                  rename: { open(.rename) },
                                  mode: { model.selectMode($0) },
                                  save: { model.save() }),
            player: PlayerActions(songDefaults: { open(.songDefaults) },
                                  voicing: { open(.voicing) },
                                  instrument: { open(.instrument) },
                                  rewind: { model.rewind() },
                                  playPause: { model.playPause() },
                                  toggleMetronome: { model.toggleMetronome() },
                                  speed: { open(.speed) },
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
            notice: { model.notice($0) })
    }
}
