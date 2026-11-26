import ChordNotepadKit
import SwiftUI
import UIKit

// The app's iOS look: the system's dynamic colours and tint, SF Symbols
// (``AppSymbols``) and the system's controls. The kit's ``AppColors`` hold
// the same colours as values; the views use these, which follow light and
// dark, Increase Contrast and the window's traits as the system's controls do.

extension AppColors {
    /// The tint: the system's accent (blue), as the system's controls use it.
    var accent: Color { .accentColor }
    var label: Color { Color(uiColor: .label) }
    var secondaryLabel: Color { Color(uiColor: .secondaryLabel) }
    var tertiaryLabel: Color { Color(uiColor: .tertiaryLabel) }
    var separator: Color { Color(uiColor: .separator) }
    /// A screen's background (the text, the bars).
    var background: Color { Color(uiColor: .systemBackground) }
    /// A grouped list's background and its rows' cells.
    var groupedBackground: Color { Color(uiColor: .systemGroupedBackground) }
    var cell: Color { Color(uiColor: .secondarySystemGroupedBackground) }
    /// The bars' background (the player, the ribbon, the find bar).
    var bar: Color { Color(uiColor: .secondarySystemBackground) }
    /// A control's fill (a search field, a chip).
    var fill: Color { Color(uiColor: .tertiarySystemFill) }
    var red: Color { Color(uiColor: .systemRed) }
}

/// An SF Symbol, or one of the app's own template images (``AppSymbols``),
/// in `tint` at `size` points.
struct AppIcon: View {
    let name: String
    var tint: Color?
    var size: CGFloat = 20
    var weight: Font.Weight = .regular

    init(_ name: String, tint: Color? = nil, size: CGFloat = 20, weight: Font.Weight = .regular) {
        self.name = name
        self.tint = tint
        self.size = size
        self.weight = weight
    }

    var body: some View {
        Group {
            if AppSymbols.isOwnImage(name) {
                // Drawn on a 24 pt grid, like a symbol's body at this size.
                Image(name)
                    .renderingMode(.template)
                    .resizable()
                    .scaledToFit()
                    .frame(width: size * 1.2, height: size * 1.2)
            } else {
                Image(systemName: name)
                    .font(.system(size: size, weight: weight))
            }
        }
        .modifier(Tinted(tint: tint))
        .accessibilityHidden(true)
    }
}

/// `tint` as the foreground, or the surroundings' (a button's) when nil.
private struct Tinted: ViewModifier {
    let tint: Color?

    func body(content: Content) -> some View {
        if let tint {
            content.foregroundStyle(tint)
        } else {
            content
        }
    }
}

/// The old icon names the views still pass, drawn as SF Symbols (a view
/// that is redrawn in the iOS look uses ``AppIcon`` and ``AppSymbols``).
struct MdiIcon: View {
    let name: String
    let tint: Color
    var size: CGFloat = 24
    var width: CGFloat?

    init(_ name: String, tint: Color, size: CGFloat = 24, width: CGFloat? = nil) {
        self.name = name
        self.tint = tint
        self.size = size
        self.width = width
    }

    static let symbols: [String: String] = [
        "mdi_menu": AppSymbols.menu, "mdi_pencil": AppSymbols.edit, "mdi_play_circle": AppSymbols.play,
        "mdi_content_save": AppSymbols.save, "mdi_music": AppSymbols.voicing,
        "mdi_guitar_acoustic": AppSymbols.instrument, "mdi_skip_previous": AppSymbols.rewind,
        "mdi_play": AppSymbols.playFill, "mdi_pause": AppSymbols.pauseFill, "mdi_metronome": AppSymbols.metronome,
        "mdi_speedometer": AppSymbols.speed, "mdi_dock_bottom": AppSymbols.chordSheet,
        "mdi_music_clef_treble": AppSymbols.songDefaults, "mdi_chevron_down": AppSymbols.chevronDown,
        "mdi_plus": AppSymbols.insert, "mdi_piano": AppSymbols.identify, "mdi_label": AppSymbols.label,
        "mdi_repeat": AppSymbols.loop, "mdi_radiobox_marked": AppSymbols.checkmark, "mdi_radiobox_blank": "",
        "mdi_circle": "circle.fill", "mdi_circle_outline": "circle", "mdi_chevron_right": AppSymbols.chevronRight,
        "mdi_arrow_left": AppSymbols.back, "mdi_file_music": AppSymbols.recent,
        "settings_add": AppSymbols.add, "settings_remove": AppSymbols.remove,
        "settings_arrow_upward": AppSymbols.moveUp, "settings_arrow_downward": AppSymbols.moveDown,
        "settings_close": AppSymbols.close, "settings_content_copy": AppSymbols.copy,
        "settings_delete": AppSymbols.delete, "settings_edit": AppSymbols.rename, "settings_error": AppSymbols.error,
        "settings_lock": AppSymbols.lock, "app_arrow_back": AppSymbols.back,
        "app_arrow_drop_down": "chevron.up.chevron.down", "app_chevron_right": AppSymbols.chevronRight,
    ]

    var body: some View {
        let symbol = Self.symbols[name] ?? name
        Group {
            if symbol.isEmpty {
                Color.clear
            } else if AppSymbols.isOwnImage(symbol) {
                Image(symbol)
                    .renderingMode(.template)
                    .resizable()
                    .scaledToFit()
            } else {
                Image(systemName: symbol)
                    .font(.system(size: size * 0.75))
            }
        }
        .foregroundStyle(tint)
        .frame(width: width ?? size, height: size)
        .accessibilityHidden(true)
    }
}
