import Foundation

/// The main screen's colours (Android's `AppColors` in ui/theme/AppTheme.kt
/// and the tints of ui/icons/MdiIcon.kt), light and dark. The editor's own
/// are ``EditorPalette``.
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
        surface: SheetColor(argb: 0xFFFB_FBFF),
        surfaceLow: SheetColor(argb: 0xFFF4_F5FA),
        surface2: SheetColor(argb: 0xFFEC_EEF5),
        surfaceHigh: SheetColor(argb: 0xFFE2_E5EF),
        line: SheetColor(argb: 0xFFD5_D8E2),
        text: SheetColor(argb: 0xFF1A_1B20),
        muted: SheetColor(argb: 0xFF5C_5F6B),
        icon: SheetColor(argb: 0xFF45_4852),
        primary: SheetColor(argb: 0xFF3F_51B5),
        onPrimary: SheetColor(argb: 0xFFFF_FFFF),
        primarySoft: SheetColor(argb: 0xFFDD_E1FF),
        pill: SheetColor(argb: 0xFF6A_5A99),
        grip: SheetColor(argb: 0xFFC3_C6D1),
        snackBackground: SheetColor(argb: 0xFF2F_3036),
        snackText: SheetColor(argb: 0xFFF2_F2F6),
        error: SheetColor(argb: 0xFFBA_1A1A))

    public static let darkColors = AppColors(
        dark: true,
        surface: SheetColor(argb: 0xFF12_1318),
        surfaceLow: SheetColor(argb: 0xFF19_1B21),
        surface2: SheetColor(argb: 0xFF20_2229),
        surfaceHigh: SheetColor(argb: 0xFF2A_2C34),
        line: SheetColor(argb: 0xFF35_3842),
        text: SheetColor(argb: 0xFFE3_E4EB),
        muted: SheetColor(argb: 0xFFA3_A7B3),
        icon: SheetColor(argb: 0xFFC8_CBD5),
        primary: SheetColor(argb: 0xFFB6_C3FF),
        onPrimary: SheetColor(argb: 0xFF1B_2A6B),
        primarySoft: SheetColor(argb: 0xFF2E_3A72),
        pill: SheetColor(argb: 0xFFC4_B5F2),
        grip: SheetColor(argb: 0xFF55_5A66),
        snackBackground: SheetColor(argb: 0xFFE3_E4EB),
        snackText: SheetColor(argb: 0xFF1A_1B20),
        error: SheetColor(argb: 0xFFFF_B4AB))

    public static func forScheme(dark: Bool) -> AppColors { dark ? .darkColors : .light }

    /// Android's `IconTints.Save` (the app bar's save button).
    public static let saveTint = SheetColor(argb: 0xFF1E_88E5)
    /// Android's `IconTints.Off` (the pill's chevron).
    public static let offTint = SheetColor(argb: 0xFF9E_9E9E)
    /// A disabled icon's opacity.
    public static let disabledAlpha = 0.38
}
