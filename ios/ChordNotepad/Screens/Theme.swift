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

