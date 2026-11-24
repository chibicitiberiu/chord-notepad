import ChordNotepadKit
import SwiftUI
import UIKit

extension SheetColor {
    var uiColor: UIColor {
        UIColor(red: CGFloat(red), green: CGFloat(green), blue: CGFloat(blue), alpha: CGFloat(alpha))
    }
}

/// The editor's fonts and text attributes from the kit's style runs, shared
/// by the live text view (attributes on its text storage) and the catalog's
/// SwiftUI drawing of the same text.
enum EditorAppearance {
    /// The session's font (desktop points × 4/3, the configured family's
    /// kind) scaled by Dynamic Type like body text.
    static func font(kind: EditorFontKind, points: Int, category: UIContentSizeCategory) -> UIFont {
        let base = CGFloat(EditorFont.pointSize(points))
        let traits = UITraitCollection(preferredContentSizeCategory: category)
        let size = UIFontMetrics(forTextStyle: .body).scaledValue(for: base, compatibleWith: traits)
        switch kind {
        case .monospace:
            return UIFont.monospacedSystemFont(ofSize: size, weight: .regular)
        case .sans:
            return UIFont.systemFont(ofSize: size)
        case .serif:
            let system = UIFont.systemFont(ofSize: size)
            guard let descriptor = system.fontDescriptor.withDesign(.serif) else { return system }
            return UIFont(descriptor: descriptor, size: size)
        }
    }

    /// The UIKit size category of a SwiftUI text size (the catalog sets the
    /// SwiftUI environment only).
    static func category(_ size: DynamicTypeSize) -> UIContentSizeCategory {
        switch size {
        case .xSmall: return .extraSmall
        case .small: return .small
        case .medium: return .medium
        case .large: return .large
        case .xLarge: return .extraLarge
        case .xxLarge: return .extraExtraLarge
        case .xxxLarge: return .extraExtraExtraLarge
        case .accessibility1: return .accessibilityMedium
        case .accessibility2: return .accessibilityLarge
        case .accessibility3: return .accessibilityExtraLarge
        case .accessibility4: return .accessibilityExtraExtraLarge
        case .accessibility5: return .accessibilityExtraExtraExtraLarge
        @unknown default: return .large
        }
    }

    /// Plain text: the font and the text colour (also the typing attributes,
    /// so what is typed after a chord isn't blue until the next highlight).
    static func baseAttributes(font: UIFont, palette: EditorPalette) -> [NSAttributedString.Key: Any] {
        [.font: font, .foregroundColor: palette.text.uiColor]
    }

    /// Paint `runs` over `storage`: everything plain first, then each run.
    static func paint(_ runs: [StyleRun], on storage: NSTextStorage, font: UIFont, palette: EditorPalette) {
        let length = storage.length
        storage.beginEditing()
        storage.setAttributes(baseAttributes(font: font, palette: palette), range: NSRange(location: 0, length: length))
        for run in runs where run.end <= length && run.start < run.end {
            let range = NSRange(location: run.start, length: run.end - run.start)
            var attributes: [NSAttributedString.Key: Any] = [:]
            if let color = run.style.color { attributes[.foregroundColor] = color.uiColor }
            if run.style.underline == true { attributes[.underlineStyle] = NSUnderlineStyle.single.rawValue }
            if let background = run.style.background { attributes[.backgroundColor] = background.uiColor }
            storage.addAttributes(attributes, range: range)
        }
        storage.endEditing()
    }
}

/// What the empty editor says (never part of the text).
enum EditorPlaceholder {
    static let text = "Type or paste a song here"
}
