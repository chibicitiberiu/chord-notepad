import Foundation

// The app's hardware keyboard shortcuts (an iPad's keyboard): Android's window
// shortcuts (ui/Shortcuts.kt: New, Open, Save, Save As and the font size) and
// the Qt desktop's Find and Replace keys, with Command for Ctrl and Apple's
// keys where the desktop's are the system's on iPadOS. They act anywhere on
// the main screen, Play mode included, as Android's root key handler does; the
// editor's own keys (undo, redo, the line commands) are the text view's
// (``EditorKeyBinding``). The app lists these in its menus (SwiftUI commands),
// so they show in the Command key's shortcut list and in iPadOS's menu bar.

/// What an app shortcut does.
public enum AppCommand: Sendable, Hashable, CaseIterable {
    case newSong, open, save, saveAs
    case find, findAndReplace, findNext, findPrevious
    case fontBigger, fontSmaller, fontReset
    /// The user guide (Android's F1).
    case userGuide
}

/// The menu a shortcut is listed in.
public enum AppShortcutMenu: Sendable, Hashable {
    case file, edit, view, help
}

/// One app shortcut: a key with Command (and Shift or Option), its title in
/// the menus and the shortcut list.
public struct AppShortcut: Sendable, Hashable {
    public var input: String
    public var shift: Bool
    public var option: Bool
    public var command: AppCommand
    public var title: String
    public var menu: AppShortcutMenu
    /// The system's own menu already has this key, sending this action up
    /// the responder chain (`open:`, `find:`, ...): the app answers the action
    /// (the editor's text view, first responder in both tabs) instead of
    /// listing the key again, which UIKit reports as a conflict.
    public var systemAction: String? = nil

    /// Every shortcut, in the order the menus list them; each takes Command.
    ///
    /// - Find and Replace is Option-Command-F (Apple's): the desktop's Ctrl+H
    ///   would be Command-H, the iPad's Home Screen key.
    /// - Find Next and Find Previous are Command-G and Shift-Command-G
    ///   (Apple's): the desktop's F3 is a media key on an iPad's keyboard, and
    ///   its Ctrl+G (Go to line) has no counterpart here.
    /// - Larger Text is Command-=, the unshifted key of Command-+ (Android takes
    ///   both); the editor's text view takes Command-+ too.
    /// - The user guide is Command-? (Apple's Help key): Android's F1 is a
    ///   media key on an iPad's keyboard, and SwiftUI's commands can't take it.
    public static let all: [AppShortcut] = [
        AppShortcut(input: "n", shift: false, option: false, command: .newSong, title: "New Song", menu: .file),
        AppShortcut(input: "o", shift: false, option: false, command: .open, title: "Open…", menu: .file,
                    systemAction: "open:"),
        AppShortcut(input: "s", shift: false, option: false, command: .save, title: "Save", menu: .file),
        AppShortcut(input: "s", shift: true, option: false, command: .saveAs, title: "Save As…", menu: .file),
        AppShortcut(input: "f", shift: false, option: false, command: .find, title: "Find…", menu: .edit,
                    systemAction: "find:"),
        AppShortcut(input: "f", shift: false, option: true, command: .findAndReplace, title: "Find and Replace…",
                    menu: .edit, systemAction: "findAndReplace:"),
        AppShortcut(input: "g", shift: false, option: false, command: .findNext, title: "Find Next", menu: .edit,
                    systemAction: "findNext:"),
        AppShortcut(input: "g", shift: true, option: false, command: .findPrevious, title: "Find Previous",
                    menu: .edit, systemAction: "findPrevious:"),
        AppShortcut(input: "=", shift: false, option: false, command: .fontBigger, title: "Larger Text", menu: .view),
        AppShortcut(input: "-", shift: false, option: false, command: .fontSmaller, title: "Smaller Text", menu: .view),
        AppShortcut(input: "0", shift: false, option: false, command: .fontReset, title: "Reset Text Size",
                    menu: .view),
        AppShortcut(input: "?", shift: false, option: false, command: .userGuide, title: "User Guide", menu: .help),
    ]

    /// The shortcuts listed in `menu`, in order.
    public static func listed(in menu: AppShortcutMenu) -> [AppShortcut] {
        all.filter { $0.menu == menu }
    }

    /// The command for a key pressed with Command and these modifiers, or nil.
    public static func command(input: String, command: Bool, shift: Bool, option: Bool) -> AppCommand? {
        guard command else { return nil }
        let key = input.count == 1 ? input.lowercased() : input
        return all.first { $0.input == key && $0.shift == shift && $0.option == option }?.command
    }

    /// The command a system menu action stands for (`find:` is Find), or nil.
    public static func command(systemAction action: String) -> AppCommand? {
        all.first { $0.systemAction == action }?.command
    }

    /// The shortcuts the app lists itself (the rest are the system menu's).
    public static func appListed(in menu: AppShortcutMenu) -> [AppShortcut] {
        listed(in: menu).filter { $0.systemAction == nil }
    }

    /// The shortcut for `command`.
    public static func of(_ command: AppCommand) -> AppShortcut? {
        all.first { $0.command == command }
    }
}

extension MainUiState {
    /// Whether the app's shortcuts act now: on the main screen with nothing
    /// over it (Android's are the song screen's: a sheet, a dialog or Settings
    /// has the keys then), and no question from the session pending.
    public func shortcutsAct(requestPending: Bool) -> Bool {
        route == .none && !requestPending
    }

    /// Replace is offered in the find bar: Edit mode (the desktop's Play
    /// workspace finds without its Replace row).
    public var findCanReplace: Bool { mode == .edit }
}
