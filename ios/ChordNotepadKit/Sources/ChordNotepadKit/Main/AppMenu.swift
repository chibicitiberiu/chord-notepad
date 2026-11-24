import Foundation

// The ☰ menu (Android's ui/main/AppDrawer.kt): Documents (New song, Open…,
// the recent songs, Save as…, the exports) and App (Settings, Examples, User
// guide, Quick start, About), plus Diagnostics on iOS. Entries whose screens
// the iOS app doesn't have yet are listed, greyed, with "Coming soon": the
// user guide, the Quick Start tour and Export PDF (the session sends the
// pages' layout, `PaintPdfRequest`, and Android paints it itself; iOS has no
// painter yet).

/// What a menu entry does.
public enum MenuAction: Sendable, Hashable {
    case newSong
    case open
    case openRecent(DocumentRef)
    case saveAs
    case exportMidi
    case exportAudio
    case exportPdf
    case settings
    case examples
    case userGuide
    case quickStart
    case about
    /// The self-test and "Export diagnostics" (iOS only).
    case diagnostics
}

extension DocumentRef: Hashable {
    public func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }
}

/// Android's per-entry icon tints (`IconTints`), as RGB.
public enum MenuTint: UInt32, Sendable {
    case newSong = 0x2E7D32
    case open = 0x1E88E5
    case recent = 0x8E24AA
    case export = 0xEF6C00
    case settings = 0x546E7A
    case examples = 0xC62828
    case guide = 0x00897B
    case quickStart = 0xF9A825
    case about = 0x5C6BC0

    public var color: SheetColor { SheetColor(argb: 0xFF00_0000 | rawValue) }
}

/// One row of the menu.
public struct MenuEntry: Sendable, Hashable {
    public var action: MenuAction
    public var label: String
    /// The icon's asset name (Android's MDI drawable), or `sf.` and an SF Symbol's name.
    public var icon: String
    public var tint: SheetColor
    /// False: listed but not built on iOS yet.
    public var enabled: Bool

    public init(_ action: MenuAction, _ label: String, icon: String, tint: SheetColor, enabled: Bool) {
        self.action = action
        self.label = label
        self.icon = icon
        self.tint = tint
        self.enabled = enabled
    }
}

/// One part of the menu, under an optional heading.
public enum MenuSection: Sendable, Hashable {
    case entries([MenuEntry])
    /// The recent songs, or "No recent songs".
    case recent([MenuEntry])
    case separator
}

/// The menu's contents, top to bottom.
public enum AppMenu {
    /// What the iOS app can do from the menu now: the rest waits for the
    /// guide, the Quick Start tour and a PDF painter (BACKLOG.md).
    public static let available: Set<String> = [
        "new", "open", "recent", "saveAs", "exportMidi", "exportAudio", "settings", "examples", "about",
        "diagnostics",
    ]

    public static func sections(recent: [DocumentRef]) -> [MenuSection] {
        func entry(_ action: MenuAction, _ key: String, _ label: String, _ icon: String, _ tint: MenuTint) -> MenuEntry {
            MenuEntry(action, label, icon: icon, tint: tint.color, enabled: available.contains(key))
        }
        let diagnosticsTint = SheetColor(argb: 0xFF54_6E7A)
        return [
            .entries([
                entry(.newSong, "new", "New song", "mdi_file_plus", .newSong),
                entry(.open, "open", "Open…", "mdi_folder_open", .open),
            ]),
            .recent(recent.map {
                MenuEntry(.openRecent($0), $0.displayName, icon: "mdi_file_music", tint: MenuTint.recent.color,
                          enabled: available.contains("recent"))
            }),
            .separator,
            .entries([
                entry(.saveAs, "saveAs", "Save as…", "mdi_content_save_edit", .open),
                entry(.exportMidi, "exportMidi", "Export MIDI…", "mdi_export", .export),
                entry(.exportAudio, "exportAudio", "Export audio…", "mdi_waveform", .export),
                entry(.exportPdf, "exportPdf", "Export PDF…", "mdi_file_pdf_box", .export),
            ]),
            .separator,
            .entries([
                entry(.settings, "settings", "Settings", "mdi_cog", .settings),
                entry(.examples, "examples", "Examples", "mdi_music_box_multiple", .examples),
                entry(.userGuide, "userGuide", "User guide", "mdi_book_open_variant", .guide),
                entry(.quickStart, "quickStart", "Quick start", "mdi_school", .quickStart),
                entry(.about, "about", "About", "mdi_information", .about),
                MenuEntry(.diagnostics, "Diagnostics", icon: "sf.stethoscope", tint: diagnosticsTint, enabled: true),
            ]),
        ]
    }
}

/// What is open over the main screen. One at a time, as Android's `SheetRoute`.
public enum MainRoute: Sendable, Hashable {
    case none
    case menu
    case rename
    /// The storage refused a rename.
    case renameFailed(name: String, reason: String, canSaveAs: Bool)
    case diagnostics
    /// The bundled example songs (Android's Examples sheet).
    case examples
    case voicing
    /// The families (`family` nil) or one family's programs.
    case instrument(family: Int?)
    /// The speed sheet; `manual` is the typed-value dialog on top of it.
    case speed(manual: Bool)
    /// The song pill's Playback settings.
    case songDefaults
    /// The ribbon's ＋ Insert.
    case insert
    /// Transpose, for the selection or the whole song.
    case transpose(selection: Bool)
    /// The chord identifier.
    case identify
    /// ☰ › Settings, full screen (its pages are the settings controller's;
    /// ``AppModel`` keeps one while this is open).
    case settings
    /// ☰ › About, full screen.
    case about
    /// About › Open source licences.
    case licences
    /// One licence's text: from the licences list, or from About itself (the
    /// app's own licence), so ← goes back where it came from (Android's P7).
    case licence(id: String, fromAbout: Bool)

    /// Where a full-screen page's ← goes (Android's `Pages.parent`): a
    /// licence to its list (or to About), the list to About, the rest to the
    /// main screen.
    public var parent: MainRoute {
        switch self {
        case .licence(_, let fromAbout): return fromAbout ? .about : .licences
        case .licences: return .about
        default: return .none
        }
    }

    /// Settings, About, the licences or a licence's text: a page that covers
    /// the whole screen.
    public var isFullPage: Bool {
        switch self {
        case .settings, .about, .licences, .licence: return true
        default: return false
        }
    }

    /// The licence entry id of a licence's page, else nil.
    public var licenceId: String? {
        if case .licence(let id, _) = self { return id }
        return nil
    }

    /// What a song that was asked to open (from Files or another app) does
    /// to what is open: it lands on the main screen (Android's P1).
    public var onSongOpened: SongOpened {
        switch self {
        case .none: return .stay
        case .settings: return .leaveSettings
        default: return .close
        }
    }
}

/// See ``MainRoute/onSongOpened``.
public enum SongOpened: Sendable, Equatable {
    /// Already on the main screen.
    case stay
    /// Close what is open.
    case close
    /// Leave Settings as ← does: it asks first while a value is wrong.
    case leaveSettings
}

/// The main screen's own state, which the session doesn't keep: the tab, what
/// is open over it and the keyboard. The live app keeps one on the main actor;
/// the preview catalog makes one per scene.
public struct MainUiState: Sendable, Equatable {
    public var modes: ModeController
    public var route: MainRoute = .none
    /// The software keyboard's height over the screen (0: down).
    public var keyboardHeight = 0.0
    /// A name the session refused stays in the rename dialog with its reason.
    public var renameRefusal: String?
    /// The rename dialog's field (the catalog's scene shows one typed).
    public var renameInput: String?
    /// The sheets' and the tools' dialogs' fields (``handle(_:snapshot:editor:)``).
    public var tools = ToolsUiState()

    public var mode: AppMode { modes.mode }

    public init(mode: AppMode? = nil, route: MainRoute = .none, keyboardHeight: Double = 0) {
        modes = ModeController(mode)
        self.route = route
        self.keyboardHeight = keyboardHeight
    }

    /// The session refused a rename: a storage that can't rename closes the
    /// dialog and offers Save As; any other reason stays in the dialog.
    public mutating func renameFailed(_ failure: RenameFailure) {
        if failure.canSaveAs {
            route = .renameFailed(name: failure.name, reason: failure.reason, canSaveAs: true)
            renameRefusal = nil
        } else {
            renameRefusal = failure.reason
        }
    }

    /// The document's name changed: a rename that was waiting went through.
    public mutating func documentRenamed() {
        if route == .rename {
            route = .none
            renameRefusal = nil
            renameInput = nil
        }
    }
}
