pragma Singleton
import QtQuick

// Chord Notepad desktop theme: the one place for colours, sizes and type.
//
// Units. Fonts are in points. Every other dimension is a multiple of one
// unit `u`, measured from the base UI font (a quarter of its line height),
// so the whole UI follows the font and the platform's DPI. `px(n)` rounds
// n units to whole pixels. The only literal is `hairline` (1 px borders stay
// crisp). `scale` multiplies the base size, and through it `u`: one knob for
// the whole UI (Ctrl+Alt+= / - / 0 in the mockup). The editor's text size is
// separate (Ctrl+= / -).
//
// Look: one custom desktop look on every OS (MuseScore 4 / VS Code family):
// flat surfaces separated by a little contrast, hairline borders, compact
// controls, our own indigo accent used sparingly.
//
// Ported from the approved mockup (/mnt/data_linux/Bin/qt-spike/mockup).
// Python sets dpr and fontRevision through the main window (dpr.py); the
// numbered Qt Quick pitfalls are listed in chordnotepad_desktop/__init__.py.
QtObject {
    id: theme

    // --- Mode and scale ------------------------------------------------------
    property bool dark: false
    property real scale: 1.0

    // --- Type (points) --------------------------------------------------------
    readonly property string uiFont: "Inter"            // bundled (resources/fonts, OFL); fonts.py loads it
    readonly property string monoFont: "Noto Sans Mono" // the editor's default: chords align by column (bundled, editor_font.py)
    // fontRevision: a ratio change makes every font a new instance (sizes differ
    // by 0.001 pt per revision parity, invisible), so all Text relayouts at the new ratio.
    // Text laid out at the old ratio keeps its glyph positions otherwise (pitfall 10).
    property int fontRevision: 0
    // Points are sized as at 96 dpi everywhere. Qt's macOS platform (cocoa)
    // draws a point as one logical pixel (72 dpi); Windows, Linux and the
    // offscreen platform the tests use (on a Mac too) draw it as 4/3 (96 dpi).
    // Without this every font, and through `u` the whole UI, came out a
    // quarter smaller on a Mac, while the chord sheet (drawn in pixels at
    // 96 dpi, sheet_paint.PT_TO_PX) didn't. It goes by the platform plugin,
    // not the screen's dpi, so a Linux desktop's own font dpi still counts.
    // QT_FONT_DPI doesn't help: on macOS it scales the whole window by a
    // fractional ratio.
    readonly property real pointScale: Qt.platform.pluginName === "cocoa" ? 96 / 72 : 1.0
    readonly property real baseSize: 10 * scale * pointScale + (fontRevision % 2) * 0.001
    readonly property real fontCaption: baseSize * 0.85
    readonly property real fontSmall:   baseSize * 0.92
    readonly property real fontBody:    baseSize
    readonly property real fontTitle:   baseSize * 1.15
    readonly property real fontHeading: baseSize * 1.5
    readonly property real fontDisplay: baseSize * 2.0
    // The editor's size is the session's font_size in points (its zoom,
    // Ctrl+= / Ctrl+- / Ctrl+0 and the − 100% + chip, steps it), times scale.

    // Inter is unhinted on screen (PreferNoHinting), set on every UI font
    // explicitly: Qt.font objects and per-Text fonts don't reliably inherit the
    // application font's preference, and then follow the desktop's (KDE: often
    // full). Inter's TTFs carry TrueType bytecode (ttfautohint); full hinting at
    // a fractional ppem (125%) rounds advances and bends stems: uneven spacing
    // and a malformed "t". No hinting keeps true advances and shapes (pitfall 11).
    // Every Qt.font below names it; tests/qt/test_qt_theme.py checks that.
    readonly property int hinting: Font.PreferNoHinting
    readonly property font font:        Qt.font({ family: uiFont, pointSize: fontBody, hintingPreference: hinting })
    readonly property font fontS:       Qt.font({ family: uiFont, pointSize: fontSmall, hintingPreference: hinting })
    readonly property font fontC:       Qt.font({ family: uiFont, pointSize: fontCaption, hintingPreference: hinting })
    readonly property font fontMedium:  Qt.font({ family: uiFont, pointSize: fontBody, weight: Font.Medium, hintingPreference: hinting })
    readonly property font fontStrong:  Qt.font({ family: uiFont, pointSize: fontBody, weight: Font.DemiBold, hintingPreference: hinting })
    readonly property font fontStrongS: Qt.font({ family: uiFont, pointSize: fontSmall, weight: Font.DemiBold, hintingPreference: hinting })   // the status bar's hint reason
    readonly property font fontTitleF:  Qt.font({ family: uiFont, pointSize: fontTitle, weight: Font.DemiBold, hintingPreference: hinting })
    readonly property font fontHeadF:   Qt.font({ family: uiFont, pointSize: fontHeading, weight: Font.DemiBold, hintingPreference: hinting })
    readonly property font fontMonoS:   Qt.font({ family: monoFont, pointSize: fontSmall, hintingPreference: hinting })
    // Tabular figures (every digit as wide): the player's bar:beat and the
    // timeline's preview don't jitter as the numbers change.
    readonly property font fontTabular: Qt.font({ family: uiFont, pointSize: fontSmall, hintingPreference: hinting, features: { "tnum": 1 } })
    readonly property font fontTabularCaption: Qt.font({ family: uiFont, pointSize: fontCaption, hintingPreference: hinting, features: { "tnum": 1 } })
    // A song value's link to its directive, hovered (the player bar).
    readonly property font fontSLink: Qt.font({ family: uiFont, pointSize: fontSmall, underline: true, hintingPreference: hinting })
    readonly property font fontTabularLink: Qt.font({ family: uiFont, pointSize: fontSmall, underline: true, hintingPreference: hinting, features: { "tnum": 1 } })
    // The Edit toolbar's Convert mark: a bold "C" and a smaller bold "Do".
    readonly property font fontMarkC:   Qt.font({ family: uiFont, pointSize: fontCaption, weight: Font.Bold, hintingPreference: hinting })
    readonly property font fontMarkDo:  Qt.font({ family: uiFont, pointSize: fontCaption * 0.9, weight: Font.Bold, hintingPreference: hinting })
    readonly property font fontTabularStrong: Qt.font({ family: uiFont, pointSize: fontSmall, weight: Font.DemiBold, hintingPreference: hinting, features: { "tnum": 1 } })
    // The chord identifier: the piano's key names (a selected key's in
    // DemiBold, the mockup's), and the notes field and candidates in the mono font.
    readonly property font fontKey:       Qt.font({ family: uiFont, pointSize: fontCaption * 0.9, hintingPreference: hinting })
    readonly property font fontKeyStrong: Qt.font({ family: uiFont, pointSize: fontCaption * 0.9, weight: Font.DemiBold, hintingPreference: hinting })
    readonly property font fontMono:      Qt.font({ family: monoFont, pointSize: fontBody, hintingPreference: hinting })
    // A small-caps-style heading ("CANDIDATES"): caption size, DemiBold, spaced out.
    readonly property font fontCaps:      Qt.font({ family: uiFont, pointSize: fontCaption, weight: Font.DemiBold, letterSpacing: u * 0.15, hintingPreference: hinting })
    // The editor keeps the default hinting, unlike Inter: a monospace font's
    // advances are fixed, so hinting can't break the columns, and it is
    // crisper at 100% (the mockup's choice). The only font without `hinting`.
    readonly property int editorHinting: Font.PreferDefaultHinting
    function editorFont(family, pointSize) {
        return Qt.font({ family: family, pointSize: pointSize * scale * pointScale + (fontRevision % 2) * 0.001, hintingPreference: editorHinting })
    }

    // --- The unit ----------------------------------------------------------------
    readonly property FontMetrics metrics: FontMetrics { font: theme.font }
    readonly property real u: Math.max(2, Math.round(metrics.height) / 4)
    function px(n) { return Math.round(n * u) }
    // Device pixels. Main binds dpr to the window's real ratio, which Python
    // reads from QWindow.devicePixelRatio() (dpr.py): on KDE Wayland at 125%,
    // Screen.devicePixelRatio and the QML window's ratio both say 2.0 (pitfall 9).
    // Thin lines and icons are sized in whole device pixels so nothing straddles
    // a pixel: a 1-logical-px line at 1.25 would come out 1 or 2 device px wide
    // depending on where it lands (pitfall 13).
    property real dpr: 1.0
    // Bumped (at most once per frame) when things move without their own
    // geometry changing: window resize, splitters, sidebars, popups, workspace
    // switches, ratio changes. SnapTranslate re-snaps on it.
    property int layoutRevision: 0
    // Debounced to the next frame: layouts (SplitView, RowLayout) position their
    // children in the polish pass, after the change that triggered the bump
    // (pitfall 12).
    readonly property Timer _bumpTimer: Timer { interval: 16; onTriggered: theme.layoutRevision++ }
    function bumpLayout() { if (!_bumpTimer.running) _bumpTimer.start() }
    onDprChanged: bumpLayout()
    readonly property real hairline: 1 / dpr                               // exactly one device pixel
    function devW(logical) { return Math.max(1, Math.round(logical * dpr - 0.01)) / dpr }   // whole device px
    function snapOffset(sceneX) { return (Math.round(sceneX * dpr) - sceneX * dpr) / dpr }    // to the device grid
    readonly property real caretWidth: devW(1.5)       // 1 device px at 1.0, 2 at 1.25 and 1.5

    // --- Sizes (formulas in units) -------------------------------------------
    readonly property int controlHeight: px(7)          // buttons, fields, combos
    readonly property int controlSmall:  px(6)          // tight rows, steppers
    readonly property int toolButton:    px(7)          // square icon buttons
    readonly property int iconSize:      px(4.5)
    readonly property int iconSmall:     px(4)
    readonly property int padX:          px(2.5)        // horizontal text padding in controls
    readonly property int gap1: px(1)
    readonly property int gap2: px(2)
    readonly property int gap3: px(3)
    readonly property int gap4: px(4)
    readonly property int gap6: px(6)
    readonly property int focusWidth: Math.max(2, px(0.5))

    readonly property int radiusSmall:  px(1)           // menu items, checkboxes, scrollbars
    readonly property int radius:       px(1.5)         // controls
    readonly property int radiusPopup:  px(2)           // menus, popovers, cards
    readonly property int radiusDialog: px(2.5)

    readonly property int menuBarHeight:  px(7)
    readonly property int tabStripHeight: px(9)
    readonly property int toolbarHeight:  px(10)
    readonly property int panelHeader:    px(8)
    readonly property int statusHeight:   px(6)
    readonly property int menuItemHeight: px(6.5)
    readonly property int listRowHeight:  px(7.5)
    readonly property int splitHandle:    px(1.5)
    readonly property int railWidth:      px(11)        // the activity rail on the far left
    readonly property int sidebarWidth:   px(76)        // Directives / Chord identifier
    readonly property int sidebarMin:     px(56)
    readonly property int sidebarMax:     px(150)
    readonly property int tileSize:       px(10)        // palette tiles (square)
    readonly property int tileIcon:       px(5.5)       // the icon inside a palette tile
    readonly property int sheetPanelHeight: px(66)      // Edit: the chord sheet panel
    readonly property int playSheetHeight: px(95)       // Play: the chord-sheet strip under the text
    readonly property int playerHeight:   px(15)        // Play: the one-row player bar on top
    readonly property int playButton:     px(12)        // the round play / pause button (the largest control)
    readonly property int playerControl:  px(8)         // player bar buttons, combos and readouts
    readonly property int playerIcon:     px(5)         // icons in those
    readonly property int transportButton: px(9)        // ⏮ and ⏹
    readonly property int scrubberHeight: px(1.25)
    // The tempo readout's drag (Tk's scrubber, in logical pixels): a press
    // becomes a drag after scrubThreshold, and every scrubStep is one step.
    readonly property real scrubThreshold: 3
    readonly property real scrubStep: 4
    readonly property int editorPadX: px(5)
    readonly property int editorPadY: px(3.5)

    // --- Colours --------------------------------------------------------------
    // Surfaces, from back to front.
    readonly property color base:      dark ? "#1e1f22" : "#ffffff"   // editor, dialogs' body
    readonly property color panel:     dark ? "#252629" : "#f6f7f9"   // side panels, chord sheet
    readonly property color chrome:    dark ? "#2b2c30" : "#eceef2"   // menu bar, tab strip, toolbars, transport, status
    readonly property color popup:     dark ? "#2e3034" : "#ffffff"   // menus, tooltips, cards
    readonly property color control:   dark ? "#35373c" : "#ffffff"   // buttons, combos at rest
    readonly property color controlHover:   dark ? "#3d3f45" : "#f1f2f5"
    readonly property color controlPressed: dark ? "#46484f" : "#e5e7ec"
    readonly property color input:     dark ? "#1b1c1f" : "#ffffff"   // text fields
    readonly property color border:    dark ? "#393b41" : "#dadde3"
    readonly property color borderStrong: dark ? "#4b4e55" : "#c3c7cf"
    readonly property color text:      dark ? "#e3e4e8" : "#1d1e22"
    readonly property color muted:     dark ? "#9b9ea8" : "#5f6370"
    readonly property color disabled:  dark ? "#5f626b" : "#a9adb6"
    readonly property color icon:      dark ? "#c3c6cf" : "#474b55"
    readonly property color shadow:    dark ? "#66000000" : "#1f000000"

    // The accent: lines and text (accent), fills (accentFill + textOnAccent).
    // Never name a property on<Capital>: QML reads it as a handler (pitfall 1,
    // the mockup's v1 bug: "onAccent" became a handler).
    readonly property color accent:        dark ? "#8b9bff" : "#3f51b5"
    readonly property color accentFill:    dark ? "#5263d9" : "#3f51b5"
    readonly property color accentHover:   dark ? "#5d6ee3" : "#4a5cc4"
    readonly property color accentPressed: dark ? "#4858c8" : "#3646a3"
    readonly property color textOnAccent:  "#ffffff"
    readonly property color selectedRow:   Qt.rgba(accent.r, accent.g, accent.b, dark ? 0.22 : 0.13)
    readonly property color focusRing:     Qt.rgba(accent.r, accent.g, accent.b, 0.45)
    readonly property color hover:   Qt.rgba(text.r, text.g, text.b, dark ? 0.07 : 0.05)
    readonly property color pressed: Qt.rgba(text.r, text.g, text.b, dark ? 0.12 : 0.09)
    readonly property color checkedBg: Qt.rgba(text.r, text.g, text.b, dark ? 0.12 : 0.08)

    // The Convert mark's two notations (the mockup's blue C, orange Do).
    readonly property color markAmerican: dark ? "#64b5f6" : "#1e88e5"
    readonly property color markEuropean: dark ? "#ffb74d" : "#fb8c00"
    readonly property color error:     dark ? "#ff8a80" : "#c62828"
    // A soft amber for notices that aren't errors (the status bar's read-only badge).
    readonly property color warning:   dark ? "#f2b95c" : "#9a5b00"
    readonly property color warningBg: Qt.rgba(warning.r, warning.g, warning.b, dark ? 0.16 : 0.13)
    readonly property color errorBg:   Qt.rgba(error.r, error.g, error.b, dark ? 0.16 : 0.10)

    // Editor: light keeps today's desktop (Tk) colours, dark uses Android's.
    readonly property color editorBg:         base
    readonly property color editorText:       dark ? "#e3e4e8" : "#000000"
    readonly property color chord:            dark ? "#8ab4f8" : "#0000ff"
    readonly property color chordInvalid:     dark ? "#7f848f" : "#bebebe"
    readonly property color directive:        dark ? "#d39be0" : "#8b4789"
    readonly property color directiveInvalid: dark ? "#ff8a80" : "#ff0000"
    readonly property color comment:          dark ? "#7f848f" : "#bebebe"
    readonly property color playing:          dark ? "#5a4f00" : "#ffff00"
    readonly property color selection:        dark ? "#3a4579" : "#cdd5f6"
    // The find bar's matches (a tint in the text) and the selected match
    // (the selection's colour while the bar is open), and a selected word's
    // other occurrences: green, away from the selection's indigo and the
    // playing chord's yellow.
    readonly property color findMatch:        dark ? "#2d4b35" : "#cdecd2"
    readonly property color findCurrent:      dark ? "#3c7448" : "#9fdcaa"
    readonly property color occurrence:       dark ? "#3c3f47" : "#dde1e8"
    // The chord sheet's playing column: the accent as a tint over the strip.
    readonly property color sheetPlaying:     Qt.rgba(accent.r, accent.g, accent.b, dark ? 0.20 : 0.14)

    readonly property int fast: 80

    function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }
    // fg laid over bg at strength (0-1), opaque (the placeholder, faded text).
    function blend(fg, bg, strength) {
        return Qt.rgba(fg.r * strength + bg.r * (1 - strength), fg.g * strength + bg.g * (1 - strength),
                       fg.b * strength + bg.b * (1 - strength), 1)
    }
    // An icon for a control's icon.source: the CNStyle controls draw it with
    // PixelIcon, which takes the name from the URL's last part (icons.py).
    function iconUrl(name) { return "image://icons/" + name }
}
