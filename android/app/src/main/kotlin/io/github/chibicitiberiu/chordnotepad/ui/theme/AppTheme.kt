package io.github.chibicitiberiu.chordnotepad.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color

/**
 * The app's tonal tokens (docs/design/android-ui-spec.md, "Colour and
 * themes"): one Material 3-style family, neutral with a hint of the indigo
 * primary. Each surface has a fixed role.
 */
@Immutable
data class AppColors(
    val dark: Boolean,
    /** The text and the app bar. */
    val surface: Color,
    /** The chord sheet, bottom sheets and the drawer. */
    val surfaceLow: Color,
    /** The Edit ribbon and the player. */
    val surface2: Color,
    /** Selected chips and dialogs. */
    val surfaceHigh: Color,
    /** Dividers. */
    val line: Color,
    val text: Color,
    val muted: Color,
    /** Monochrome icons (the player, the app bar). */
    val icon: Color,
    val primary: Color,
    val onPrimary: Color,
    /** The soft tint behind an active player button. */
    val primarySoft: Color,
    /** The song pill's text (𝄞 90 · 3/4 · G). */
    val pill: Color,
    /** Drag handles. */
    val grip: Color,
    val snackBackground: Color,
    val snackText: Color,
    // The editor's look. Light mode keeps the desktop's colours unchanged
    // (src/constants.py); dark mode has readable variants of the same hues.
    val chord: Color,
    val chordInvalid: Color,
    val directive: Color,
    val directiveInvalid: Color,
    val comment: Color,
    val playing: Color,
    val editorText: Color,
    /** The chord sheet's playing column (translucent yellow in both themes). */
    val sheetPlaying: Color,
) {
    companion object {
        /** The light theme. */
        val Light = AppColors(
            dark = false,
            surface = Color(0xFFFBFBFF),
            surfaceLow = Color(0xFFF4F5FA),
            surface2 = Color(0xFFECEEF5),
            surfaceHigh = Color(0xFFE2E5EF),
            line = Color(0xFFD5D8E2),
            text = Color(0xFF1A1B20),
            muted = Color(0xFF5C5F6B),
            icon = Color(0xFF454852),
            primary = Color(0xFF3F51B5),
            onPrimary = Color(0xFFFFFFFF),
            primarySoft = Color(0xFFDDE1FF),
            pill = Color(0xFF6A5A99),
            grip = Color(0xFFC3C6D1),
            snackBackground = Color(0xFF2F3036),
            snackText = Color(0xFFF2F2F6),
            // Tk's named colours, as the desktop editor paints them.
            chord = Color(0xFF0000FF),
            chordInvalid = Color(0xFFBEBEBE),
            directive = Color(0xFF8B4789),
            directiveInvalid = Color(0xFFFF0000),
            comment = Color(0xFFBEBEBE),
            playing = Color(0xFFFFFF00),
            editorText = Color(0xFF000000),
            sheetPlaying = Color(0x73FFEB3B),
        )

        /** The dark theme. */
        val Dark = AppColors(
            dark = true,
            surface = Color(0xFF121318),
            surfaceLow = Color(0xFF191B21),
            surface2 = Color(0xFF202229),
            surfaceHigh = Color(0xFF2A2C34),
            line = Color(0xFF353842),
            text = Color(0xFFE3E4EB),
            muted = Color(0xFFA3A7B3),
            icon = Color(0xFFC8CBD5),
            primary = Color(0xFFB6C3FF),
            onPrimary = Color(0xFF1B2A6B),
            primarySoft = Color(0xFF2E3A72),
            pill = Color(0xFFC4B5F2),
            grip = Color(0xFF555A66),
            snackBackground = Color(0xFFE3E4EB),
            snackText = Color(0xFF1A1B20),
            chord = Color(0xFF8AB4F8),
            chordInvalid = Color(0xFF7F848F),
            directive = Color(0xFFD39BE0),
            directiveInvalid = Color(0xFFFF8A80),
            comment = Color(0xFF7F848F),
            playing = Color(0xFF5A4F00),
            editorText = Color(0xFFE3E4EB),
            sheetPlaying = Color(0x2EFFEB3B),
        )
    }
}

/** The current [AppColors]; [ChordNotepadTheme] provides them. */
val LocalAppColors = staticCompositionLocalOf { AppColors.Light }

/** Shortcut for `LocalAppColors.current`. */
val appColors: AppColors
    @Composable
    @ReadOnlyComposable
    get() = LocalAppColors.current

/** The Material 3 scheme over the tokens, so stock components pick the same roles. */
fun AppColors.materialScheme(): ColorScheme {
    val base = if (dark) darkColorScheme() else lightColorScheme()
    return base.copy(
        primary = primary,
        onPrimary = onPrimary,
        primaryContainer = primarySoft,
        onPrimaryContainer = if (dark) text else Color(0xFF1B2A6B),
        secondaryContainer = primarySoft,
        onSecondaryContainer = text,
        background = surface,
        onBackground = text,
        surface = surface,
        onSurface = text,
        surfaceVariant = surfaceHigh,
        onSurfaceVariant = muted,
        surfaceContainerLowest = surface,
        surfaceContainerLow = surfaceLow,
        surfaceContainer = surface2,
        surfaceContainerHigh = surfaceHigh,
        surfaceContainerHighest = surfaceHigh,
        surfaceBright = surface,
        surfaceDim = surface2,
        outline = muted,
        outlineVariant = line,
        inverseSurface = snackBackground,
        inverseOnSurface = snackText,
        inversePrimary = if (dark) Color(0xFF3F51B5) else Color(0xFFB6C3FF),
    )
}

/**
 * Material 3 over the app's tokens, light or dark as the system says (no
 * dynamic colour: the surfaces have fixed roles).
 */
@Composable
fun ChordNotepadTheme(dark: Boolean = isSystemInDarkTheme(), content: @Composable () -> Unit) {
    val colors = if (dark) AppColors.Dark else AppColors.Light
    CompositionLocalProvider(LocalAppColors provides colors) {
        MaterialTheme(colorScheme = colors.materialScheme()) {
            Surface(Modifier.fillMaxSize(), color = colors.surface, content = content)
        }
    }
}
