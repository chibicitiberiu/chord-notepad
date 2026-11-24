import ChordNotepadKit
import SwiftUI

/// `UserDefaults` as the kit's ``PreferenceStore`` (the side column's width;
/// the privacy manifest's CA92.1: read and written by this app only).
final class UserDefaultsPreferences: PreferenceStore {
    private let defaults: UserDefaults

    init(_ defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    func double(forKey key: String) -> Double? {
        defaults.object(forKey: key) as? Double
    }

    func set(_ value: Double, forKey key: String) {
        defaults.set(value, forKey: key)
    }
}

/// The app's keyboard shortcuts as menu commands (the kit's ``AppShortcut``
/// table): File (New Song, Save, Save As…), View (the text size) and Help
/// (the user guide). As menu commands they act wherever the keys are, Play
/// mode included (Android's are the song screen's root handler), and the iPad
/// lists them when Command is held, and in iPadOS's menu bar. Open… and the
/// find keys are already the system menu's (`open:`, `find:`,
/// `findAndReplace:`, `findNext:`, `findPrevious:`): listing them again is a
/// conflict UIKit reports (run 45493241329), so the editor's text view, first
/// responder in both tabs, answers those actions (``EditorTextView``).
struct AppCommands: Commands {
    let model: AppModel

    var body: some Commands {
        CommandGroup(replacing: .newItem) { buttons([.newSong]) }
        CommandGroup(replacing: .saveItem) { buttons([.save, .saveAs]) }
        CommandGroup(before: .toolbar) { buttons(AppShortcut.appListed(in: .view).map(\.command)) }
        CommandGroup(replacing: .help) { buttons(AppShortcut.appListed(in: .help).map(\.command)) }
    }

    /// A button with its key for each of `commands`.
    private func buttons(_ commands: [AppCommand]) -> some View {
        ForEach(commands.compactMap { AppShortcut.of($0) }, id: \.command) { shortcut in
            Button(shortcut.title) {
                MainActor.assumeIsolated { model.shortcut(shortcut.command) }
            }
            .keyboardShortcut(KeyEquivalent(Character(shortcut.input)), modifiers: shortcut.modifiers)
        }
    }
}

extension AppShortcut {
    var modifiers: EventModifiers {
        var flags: EventModifiers = .command
        if shift { flags.insert(.shift) }
        if option { flags.insert(.option) }
        return flags
    }
}

extension AppModel {
    /// An app shortcut (a menu command): on the main screen with nothing over
    /// it, as Android's root key handler; ignored while a sheet, a dialog or
    /// a page has the screen, or before the session runs.
    func shortcut(_ command: AppCommand) {
        guard phase == .running, ui.shortcutsAct(requestPending: snapshot.request != nil) else {
            Log.ui.info("Shortcut \(String(describing: command), privacy: .public) ignored: \(String(describing: self.ui.route), privacy: .public)")
            return
        }
        Log.ui.info("Shortcut \(String(describing: command), privacy: .public)")
        switch command {
        case .newSong: choose(.newSong)
        case .open: choose(.open)
        case .save: save()
        case .saveAs: choose(.saveAs)
        case .find: editor.find(.open(replace: false))
        case .findAndReplace: editor.find(.open(replace: true))
        case .findNext: editor.find(.again(backward: false))
        case .findPrevious: editor.find(.again(backward: true))
        case .fontBigger: editor.perform(.fontBigger)
        case .fontSmaller: editor.perform(.fontSmaller)
        case .fontReset: editor.perform(.fontReset)
        case .userGuide: choose(.userGuide)
        }
    }

    /// The landscape column's handle was let go: kept for the next launch.
    func keepSideFraction(_ fraction: Double) {
        preferences.sideFraction = fraction
        sideFraction = preferences.sideFraction
    }

    /// `-CNScreen find` (CI): once the song is on screen, in Edit, Find and
    /// Replace with "the" typed and "a" as the replacement, then
    /// `Diagnostics/tool-find.json`, which the screenshot waits for.
    func runFindScreen() async {
        // The song's own open decides the tab (Play, as a saved song): switch after it.
        _ = await waitFor(timeout: .seconds(120)) {
            $0.highlight?.spans.isEmpty == false && $0.document?.documentId != nil
        }
        try? await Task.sleep(for: .seconds(1))
        selectMode(.edit)
        _ = await waitFor(timeout: .seconds(10)) { _ in self.ui.mode == .edit }
        editor.find(.open(replace: true))
        editor.find(.query("the"))
        editor.find(.replacement("a"))
        let bar = editor.model.find
        let ok = ui.mode == .edit && bar.open && bar.replacing && bar.current > 0 && bar.matches.count > 1
        Log.ui.info("Find screen: \(ok ? "ready" : "failed", privacy: .public) \(bar.countText, privacy: .public)")
        Diagnostics.shared.writeJSON(ToolScreenReport(name: "find", ok: ok, route: bar.countText),
                                     name: "tool-find.json")
    }
}
