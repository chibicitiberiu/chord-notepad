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
/// table): File (New Song, Open…, Save, Save As…), Edit (Find…, Find and
/// Replace…, Find Next, Find Previous) and View (the text size). As menu
/// commands they act wherever the keys are, Play mode included (Android's
/// are the song screen's root handler), and the iPad lists them when Command
/// is held, and in iPadOS's menu bar.
struct AppCommands: Commands {
    let model: AppModel

    var body: some Commands {
        CommandGroup(replacing: .newItem) { buttons(.file, upTo: .open) }
        CommandGroup(replacing: .saveItem) { buttons(.file, from: .save) }
        CommandGroup(replacing: .textEditing) { buttons(.edit) }
        CommandGroup(before: .toolbar) { buttons(.view) }
    }

    /// The shortcuts listed in `menu` (optionally from or up to a command, for
    /// the File menu's two groups).
    @ViewBuilder
    private func buttons(_ menu: AppShortcutMenu, from first: AppCommand? = nil, upTo last: AppCommand? = nil)
        -> some View {
        let all = AppShortcut.listed(in: menu)
        let start = first.flatMap { f in all.firstIndex { $0.command == f } } ?? 0
        let end = last.flatMap { l in all.firstIndex { $0.command == l } } ?? all.count - 1
        ForEach(Array(all[start...end]), id: \.command) { shortcut in
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
        _ = await waitFor(timeout: .seconds(120)) { $0.highlight?.spans.isEmpty == false }
        selectMode(.edit)
        editor.find(.open(replace: true))
        editor.find(.query("the"))
        editor.find(.replacement("a"))
        let bar = editor.model.find
        let ok = bar.open && bar.replacing && bar.current > 0 && bar.matches.count > 1
        Log.ui.info("Find screen: \(ok ? "ready" : "failed", privacy: .public) \(bar.countText, privacy: .public)")
        Diagnostics.shared.writeJSON(ToolScreenReport(name: "find", ok: ok, route: bar.countText),
                                     name: "tool-find.json")
    }
}
