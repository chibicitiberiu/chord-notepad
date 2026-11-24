import Foundation

// The chord sheet's colours come from the op buffer (the desktop renderers'
// palette, core/chordnotepad/chord_sheet/). As on Android
// (ui/chordsheet/ChordSheetTheme.kt, docs/design/android-ui-spec.md "Chord
// sheet"), the light theme keeps them and the dark one maps them: the strip
// takes the surface-low background, every second section a colour halfway to
// surface2, the playing column is a translucent primary tint, the hands' bars
// keep their blue and brown a little lighter, neutral inks and grids flip
// their lightness, and the other colours (voice parts, marker flags) are
// lifted to stay readable.

/// The app's tonal tokens the chord sheet uses (Android's `AppColors`,
/// docs/design/android-ui-spec.md "Colour and themes").
public struct ChordSheetColors: Sendable, Equatable {
    public var dark: Bool
    /// The chord sheet's own background.
    public var surfaceLow: SheetColor
    /// The Edit ribbon and the player; banded sections step halfway to it.
    public var surface2: SheetColor
    /// The selected view tab.
    public var surfaceHigh: SheetColor
    /// Dividers.
    public var line: SheetColor
    public var text: SheetColor
    public var muted: SheetColor
    /// The playhead's edge mark.
    public var primary: SheetColor
    /// Drag handles.
    public var grip: SheetColor
    /// The playing column: the primary colour as a translucent tint.
    public var sheetPlaying: SheetColor

    public static let light = ChordSheetColors(
        dark: false,
        surfaceLow: SheetColor(argb: 0xFFF4_F5FA),
        surface2: SheetColor(argb: 0xFFEC_EEF5),
        surfaceHigh: SheetColor(argb: 0xFFE2_E5EF),
        line: SheetColor(argb: 0xFFD5_D8E2),
        text: SheetColor(argb: 0xFF1A_1B20),
        muted: SheetColor(argb: 0xFF5C_5F6B),
        primary: SheetColor(argb: 0xFF3F_51B5),
        grip: SheetColor(argb: 0xFFC3_C6D1),
        sheetPlaying: SheetColor(argb: 0x243F_51B5))

    public static let dark = ChordSheetColors(
        dark: true,
        surfaceLow: SheetColor(argb: 0xFF19_1B21),
        surface2: SheetColor(argb: 0xFF20_2229),
        surfaceHigh: SheetColor(argb: 0xFF2A_2C34),
        line: SheetColor(argb: 0xFF35_3842),
        text: SheetColor(argb: 0xFFE3_E4EB),
        muted: SheetColor(argb: 0xFFA3_A7B3),
        primary: SheetColor(argb: 0xFFB6_C3FF),
        grip: SheetColor(argb: 0xFF55_5A66),
        sheetPlaying: SheetColor(argb: 0x33B6_C3FF))

    public static func forScheme(dark: Bool) -> ChordSheetColors { dark ? .dark : .light }
}

/// The colour strings of the core's renderers the theme treats specially
/// (`renderer_interface`, `piano_roll`).
public enum SheetInk {
    /// `renderer_interface.HAND_COLORS`: the right and left hands' bars.
    public static let rightHand = "#2a6f8a"
    public static let leftHand = "#8a5a3a"
    /// `renderer_interface.STRIP_BG`.
    public static let stripBackground = "#fbfbf8"
    /// `renderer_interface.SECTION_BAND`: the paper of every second section.
    public static let sectionBand = "#f6f6f2"
    /// `renderer_interface.NOTE_INK`: the colour of untinted glyph images.
    public static let note = "#22323a"
    /// The piano roll's gutter keys (`piano_roll.GUTTER_WHITE`, `GUTTER_BLACK`).
    public static let gutterWhite = "#ffffff"
    public static let gutterBlack = "#31424a"
    /// `piano_roll.GUTTER_BORDER` and the octave labels' ink (`piano_roll._INK`).
    public static let gutterBorder = "#b9c2c7"
    public static let gutterInk = "#22323a"
    /// `piano_roll.NOTE_LABEL`: the note names in the piano roll's bars.
    public static let noteLabel = "#fdfdff"
}

/// How the theme maps the buffer's colours (Android's `ChordSheetTheme.kt`).
public enum ChordSheetTheme {
    static let darkRightHand = SheetColor(argb: 0xFF78_A6D8)
    static let darkLeftHand = SheetColor(argb: 0xFFD0_9A6C)
    static let darkNoteLabel = SheetColor(argb: 0xFF1D_1E22)
    static let darkGutterWhite = SheetColor(argb: 0xFFD3_D6DD)

    /// The piano roll's keyboard in the dark theme: not inverted (that reads
    /// wrong), in the app's neutral greys, as the desktop paints it
    /// (`sheet_paint._DARK_KEYS`).
    static let darkKeys: [String: SheetColor] = [
        SheetInk.gutterWhite: SheetColor(argb: 0xFFC3_C6CF),
        SheetInk.gutterBlack: SheetColor(argb: 0xFF17_181B),
        SheetInk.gutterBorder: SheetColor(argb: 0xFF8A_8D96),
        SheetInk.gutterInk: SheetColor(argb: 0xFF1D_1E22),
    ]

    /// Below this HSL saturation a colour counts as neutral (ink, grid, shading).
    static let neutralSaturation = 0.3

    /// A buffer colour as the sheet paints it in `colors`' theme.
    public static func themed(_ spec: String, _ parsed: SheetColor, _ colors: ChordSheetColors) -> SheetColor {
        let low = spec.lowercased()
        // The strip's paper (also the staff gutter's) is the sheet's surface.
        if low == SheetInk.stripBackground { return colors.surfaceLow }
        if low == SheetInk.sectionBand { return sectionBand(colors) }
        guard colors.dark else { return parsed }
        switch low {
        case SheetInk.rightHand: return darkRightHand
        case SheetInk.leftHand: return darkLeftHand
        case SheetInk.gutterWhite: return darkGutterWhite
        case SheetInk.gutterBlack: return parsed
        case SheetInk.noteLabel: return darkNoteLabel
        default: return darkVariant(parsed)
        }
    }

    /// A colour of the piano roll's keyboard (its gutter) in `colors`' theme.
    public static func keyboardGutter(_ spec: String, _ parsed: SheetColor, _ colors: ChordSheetColors) -> SheetColor {
        colors.dark ? darkKeys[spec.lowercased()] ?? parsed : parsed
    }

    /// A banded section's paper: halfway (per sRGB channel) from surfaceLow to surface2.
    public static func sectionBand(_ colors: ChordSheetColors) -> SheetColor {
        let a = colors.surfaceLow
        let b = colors.surface2
        return SheetColor(red: (a.red + b.red) / 2, green: (a.green + b.green) / 2, blue: (a.blue + b.blue) / 2)
    }

    /// `color` for a dark background: neutrals flip their lightness and lose
    /// most of their tint (a warm off-white must not turn olive), hues get
    /// lighter (at least 66 % lightness).
    public static func darkVariant(_ color: SheetColor) -> SheetColor {
        let (h, s, l) = color.hsl
        let neutral = s < neutralSaturation
        let newL = neutral ? 0.92 - 0.82 * l : max(l, 0.66)
        let newS = neutral ? s * 0.3 : s
        return SheetColor(hue: h, saturation: min(max(newS, 0), 1), lightness: min(max(newL, 0), 1),
                          alpha: color.alpha)
    }
}

/// Every colour of one buffer, themed: what the painter looks colours up in.
public struct ChordSheetPalette: Sendable, Equatable {
    public let colors: ChordSheetColors
    /// The content's and the lane's colours (and every gutter but the piano roll's).
    public let content: [String: SheetColor]
    /// The piano roll keyboard's colours (its own look in both themes).
    public let keyboard: [String: SheetColor]
    /// The tint for glyph images whose key names no colour (black ink), or
    /// nil to draw them as they are: the dark theme's ink.
    public let defaultGlyphTint: SheetColor?

    /// The palette for the colour strings of `strings` (a buffer's string
    /// table; strings that aren't colours are left out).
    public init(strings: [String], colors: ChordSheetColors) {
        self.colors = colors
        var content: [String: SheetColor] = [:]
        var keyboard: [String: SheetColor] = [:]
        for spec in strings {
            guard let parsed = SheetColor(tk: spec) else { continue }
            content[spec] = ChordSheetTheme.themed(spec, parsed, colors)
            keyboard[spec] = ChordSheetTheme.keyboardGutter(spec, parsed, colors)
        }
        self.content = content
        self.keyboard = keyboard
        defaultGlyphTint = colors.dark
            ? ChordSheetTheme.themed(SheetInk.note, SheetColor(tk: SheetInk.note)!, colors) : nil
    }

    /// The themed tint for a glyph key's `#rrggbb`, or the default ink tint.
    public func glyphTint(_ tint: String?) -> SheetColor? {
        guard let tint else { return defaultGlyphTint }
        guard let parsed = SheetColor(tk: tint) else { return defaultGlyphTint }
        return ChordSheetTheme.themed(tint, parsed, colors)
    }
}
