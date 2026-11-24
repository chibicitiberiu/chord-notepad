import Foundation

/// The editor's hardware keyboard shortcuts: Android's (`ui/Shortcuts.kt`:
/// undo, redo and the font size) and the Qt desktop's line commands
/// (`qml/app/EditorPane.qml`), with Command for Ctrl as on a Mac.
///
/// Cut, copy, paste and select all are the text view's own; Command-Z and
/// Shift-Command-Z also reach the editor through the text view's undo
/// manager (the Edit menu, shake, three-finger swipe), and the key commands
/// here take them first so a hardware keyboard always gets the same history.
/// Moving lines is Option-Command-Up/Down: Shift-Command-Up/Down (the
/// desktop's) select to the start and end of the text on Apple platforms.
public struct EditorKeyBinding: Sendable, Hashable {
    /// The key's input as `UIKeyCommand` names it (a character, or one of
    /// ``EditorKeyBinding/upArrow`` and ``EditorKeyBinding/downArrow``).
    public var input: String
    public var shift: Bool
    public var option: Bool
    public var action: EditorAction
    /// The command's name in the iPad's shortcut list.
    public var title: String

    /// `UIKeyCommand.inputUpArrow` and `inputDownArrow`.
    public static let upArrow = "UIKeyInputUpArrow"
    public static let downArrow = "UIKeyInputDownArrow"

    /// Every binding; each takes Command too.
    public static let all: [EditorKeyBinding] = [
        EditorKeyBinding(input: "z", shift: false, option: false, action: .undo, title: "Undo"),
        EditorKeyBinding(input: "z", shift: true, option: false, action: .redo, title: "Redo"),
        // Command-= is the same key as Command-+ on most layouts.
        EditorKeyBinding(input: "=", shift: false, option: false, action: .fontBigger, title: "Larger Text"),
        EditorKeyBinding(input: "+", shift: false, option: false, action: .fontBigger, title: "Larger Text"),
        EditorKeyBinding(input: "+", shift: true, option: false, action: .fontBigger, title: "Larger Text"),
        EditorKeyBinding(input: "-", shift: false, option: false, action: .fontSmaller, title: "Smaller Text"),
        EditorKeyBinding(input: "0", shift: false, option: false, action: .fontReset, title: "Reset Text Size"),
        EditorKeyBinding(input: "/", shift: false, option: false, action: .toggleComment, title: "Toggle Comment"),
        EditorKeyBinding(input: "d", shift: false, option: false, action: .duplicateLines,
                         title: "Duplicate Line or Selection"),
        EditorKeyBinding(input: "k", shift: true, option: false, action: .deleteLines, title: "Delete Line"),
        EditorKeyBinding(input: upArrow, shift: false, option: true, action: .moveLinesUp, title: "Move Line Up"),
        EditorKeyBinding(input: downArrow, shift: false, option: true, action: .moveLinesDown,
                         title: "Move Line Down"),
    ]

    /// The action for a key pressed with Command and these modifiers, or nil.
    public static func action(input: String, command: Bool, shift: Bool, option: Bool) -> EditorAction? {
        guard command else { return nil }
        let key = input.count == 1 ? input.lowercased() : input
        return all.first { $0.input == key && $0.shift == shift && $0.option == option }?.action
    }
}
