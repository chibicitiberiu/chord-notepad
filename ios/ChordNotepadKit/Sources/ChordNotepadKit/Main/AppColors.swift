import Foundation

/// The main screen's colours, light and dark: iOS's system colours (the
/// accent is the system blue), for code that needs a value rather than the
/// app's dynamic `UIColor`s. The editor's own are ``EditorPalette``.
public struct AppColors: Sendable, Equatable {
    public var dark: Bool
    /// The app bar and the text's background.
    public var surface: SheetColor
    /// The menu's background.
    public var surfaceLow: SheetColor
    /// The player's and the ribbon's background.
    public var surface2: SheetColor
    /// Dialogs and the hint card.
    public var surfaceHigh: SheetColor
    public var line: SheetColor
    public var text: SheetColor
    public var muted: SheetColor
    /// The player's side buttons.
    public var icon: SheetColor
    public var primary: SheetColor
    public var onPrimary: SheetColor
    /// A side button that is on.
    public var primarySoft: SheetColor
    /// The song pill's text.
    public var pill: SheetColor
    public var grip: SheetColor
    public var snackBackground: SheetColor
    public var snackText: SheetColor
    /// The error colour (Material's).
    public var error: SheetColor

    public static let light = AppColors(
        dark: false,
        surface: SheetColor(argb: 0xFFFF_FFFF),
        surfaceLow: SheetColor(argb: 0xFFF2_F2F7),
        surface2: SheetColor(argb: 0xFFF9_F9F9),
        surfaceHigh: SheetColor(argb: 0xFFE5_E5EA),
        line: SheetColor(argb: 0xFFC6_C6C8),
        text: SheetColor(argb: 0xFF00_0000),
        muted: SheetColor(argb: 0xFF8A_8A8E),
        icon: SheetColor(argb: 0xFF3C_3C43),
        primary: SheetColor(argb: 0xFF00_7AFF),
        onPrimary: SheetColor(argb: 0xFFFF_FFFF),
        primarySoft: SheetColor(argb: 0xFFE0_EEFF),
        pill: SheetColor(argb: 0xFF00_7AFF),
        grip: SheetColor(argb: 0xFFC7_C7CC),
        snackBackground: SheetColor(argb: 0xFF2C_2C2E),
        snackText: SheetColor(argb: 0xFFFF_FFFF),
        error: SheetColor(argb: 0xFFFF_3B30))

    public static let darkColors = AppColors(
        dark: true,
        surface: SheetColor(argb: 0xFF00_0000),
        surfaceLow: SheetColor(argb: 0xFF1C_1C1E),
        surface2: SheetColor(argb: 0xFF16_1616),
        surfaceHigh: SheetColor(argb: 0xFF2C_2C2E),
        line: SheetColor(argb: 0xFF38_383A),
        text: SheetColor(argb: 0xFFFF_FFFF),
        muted: SheetColor(argb: 0xFF8D_8D93),
        icon: SheetColor(argb: 0xFFEB_EBF5),
        primary: SheetColor(argb: 0xFF0A_84FF),
        onPrimary: SheetColor(argb: 0xFFFF_FFFF),
        primarySoft: SheetColor(argb: 0xFF0B_2A4D),
        pill: SheetColor(argb: 0xFF0A_84FF),
        grip: SheetColor(argb: 0xFF48_484A),
        snackBackground: SheetColor(argb: 0xFF3A_3A3C),
        snackText: SheetColor(argb: 0xFFFF_FFFF),
        error: SheetColor(argb: 0xFFFF_453A))

    public static func forScheme(dark: Bool) -> AppColors { dark ? .darkColors : .light }

    /// The app bar's save button (the system blue).
    public static let saveTint = SheetColor(argb: 0xFF00_7AFF)
    /// The pill's chevron (the system grey).
    public static let offTint = SheetColor(argb: 0xFF8E_8E93)
    /// A disabled icon's opacity.
    public static let disabledAlpha = 0.38
}
