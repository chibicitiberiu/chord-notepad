import ChordNotepadKit
import SwiftUI
import UIKit

/// One recorded scene as a screen gets it: the folded snapshot, the editor's
/// model folded from the same outputs, and the chord sheet's recorded buffers.
struct CatalogScene {
    let snapshot: SessionSnapshot
    let editor: EditorModel
    let chordSheet: ChordSheetSource
}

/// One screen in the catalog: its name, the recorded scenes it is shown with
/// (ios/Fixtures), the windows it is drawn in and how to draw it.
struct CatalogScreen {
    let name: String
    let fixtures: [String]
    let devices: [CatalogRenderer.Device]
    let make: @MainActor (CatalogScene, CatalogRenderer.Device) -> AnyView

    init<Screen: View>(_ name: String, fixtures: [String], devices: [CatalogRenderer.Device] = CatalogRenderer.upright,
                       @ViewBuilder make: @escaping @MainActor (CatalogScene, CatalogRenderer.Device) -> Screen) {
        self.name = name
        self.fixtures = fixtures
        self.devices = devices
        self.make = { AnyView(make($0, $1)) }
    }
}

/// Every screen drawn from the recorded scenes, without Python
/// (docs/IOS.md, "Preview catalog"). `#Preview`s use the same fixtures, and
/// CI's CatalogTests render each entry in its windows, light and dark, at the
/// default and a large text size.
///
/// Adding a screen is one line in ``screens``.
@MainActor
enum PreviewCatalog {
    static let screens: [CatalogScreen] = [
        CatalogScreen("edit", fixtures: ["scarborough_edit", "empty_song", "editor_mid_edit", "editor_european"],
                      devices: CatalogRenderer.upright + [CatalogRenderer.ipadLandscape]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .edit))
        },
        CatalogScreen("play", fixtures: ["scarborough_piano_roll", "scarborough_fret", "scarborough_tab",
                                         "play_with_chord_sheet", "chord_sheet_staff", "quick_start_edit"],
                      devices: CatalogRenderer.all) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play))
        },
        // The software keyboard up in Edit: a grey stand-in for it under the screen.
        CatalogScreen("keyboard", fixtures: ["scarborough_edit"],
                      devices: [CatalogRenderer.iphoneLandscape, CatalogRenderer.devices[0]]) { scene, device in
            let keyboard = device.keyboardHeight
            VStack(spacing: 0) {
                PreviewCatalog.mainScreen(scene, MainUiState(mode: .edit, keyboardHeight: Double(keyboard)))
                Color(uiColor: .systemGray4)
                    .frame(height: keyboard)
                    .overlay { Text("Keyboard").font(.caption).foregroundStyle(.secondary) }
            }
        },
        CatalogScreen("menu", fixtures: ["scarborough_edit", "files_recent"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play, route: .menu))
        },
        // The session's unsaved-changes question (New on a changed song).
        CatalogScreen("discard", fixtures: ["discard_question"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .edit))
        },
        // An export saved: its status in Play's status line; in Edit, as a snackbar.
        CatalogScreen("export", fixtures: ["export_done"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play))
        },
        // "Preparing export…" over the song: an audio export at 42 % (a MIDI or
        // PDF export has no percentage), drawn as iOS draws an alert.
        CatalogScreen("export_preparing", fixtures: ["export_done"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play),
                                      exportDialog: ExportDialog(documentId: "app:exports/1/Lullaby (2).wav",
                                                                 kind: "audio", progress: 0.42))
        },
        CatalogScreen("export_edit", fixtures: ["export_done"], devices: [CatalogRenderer.devices[0]]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .edit),
                                      snackbar: scene.snapshot.status.map { Snackbar(text: $0.text, error: false, id: 1) })
        },
        // A document that can't be opened: the session's error as a snackbar.
        CatalogScreen("open_error", fixtures: ["errors"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play),
                                      snackbar: scene.snapshot.messages.first { $0.contains("Failed to open") }
                                          .map { Snackbar(text: $0, error: true, id: 1) })
        },
        CatalogScreen("examples", fixtures: ["empty_song"], devices: [CatalogRenderer.devices[0]]) { _, _ in
            CatalogColors { ExamplesSheet(names: AppDocumentStore.exampleNames, colors: $0, scrolls: false) }
        },
        CatalogScreen("rename", fixtures: ["scarborough_edit", "errors"]) { scene, _ in
            let failure = scene.snapshot.renameFailure
            let ui = failure.map {
                MainUiState(mode: .play, route: .renameFailed(name: $0.name, reason: $0.reason,
                                                               canSaveAs: $0.canSaveAs))
            } ?? MainUiState(mode: .play, route: .rename)
            PreviewCatalog.mainScreen(scene, ui, renameName: "Scarborough Fair (live)")
        },
        CatalogScreen("diagnostics", fixtures: ["empty_song"]) { _, _ in
            SelfTestContent(report: .sample, timings: SelfTestReport.sample.timings, running: false, scrolls: false)
        },
        // The player's sheets over Play, as Android's help screenshots show them (Amazing Grace,
        // speed 125 %, Steel Guitar, 3/4 and G as the song's own values).
        CatalogScreen("voicing", fixtures: ["player_sheets"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play, route: .voicing))
        },
        CatalogScreen("instrument", fixtures: ["player_sheets"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play, route: .instrument(family: nil)))
        },
        CatalogScreen("speed", fixtures: ["player_sheets"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play, route: .speed(manual: false)))
        },
        CatalogScreen("speed_manual", fixtures: ["player_sheets"]) { scene, _ in
            var ui = MainUiState(mode: .play, route: .speed(manual: true))
            ui.tools.speedEntry = SpeedEntry(pct: scene.snapshot.toolbar?.multiplierPct ?? 100)
            return PreviewCatalog.mainScreen(scene, ui)
        },
        CatalogScreen("song_defaults", fixtures: ["player_sheets"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play, route: .songDefaults))
        },
        // The ribbon's tools over Edit.
        CatalogScreen("insert_sheet", fixtures: ["grace_edit"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .edit, route: .insert))
        },
        // Transpose for the whole song, two semitones up (Android's transpose shot).
        CatalogScreen("transpose", fixtures: ["grace_edit"]) { scene, _ in
            var ui = MainUiState(mode: .edit, route: .transpose(selection: false))
            ui.tools.transpose = TransposeForm(semitones: 2)
            return PreviewCatalog.mainScreen(scene, ui)
        },
        // Each Insert dialog as it opens, from the session's pending request.
        CatalogScreen("insert", fixtures: DirectiveKind.allCases.map { "insert_\($0.wire)" },
                      devices: [CatalogRenderer.devices[0]]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .edit))
        },
        // The tempo typed out of range: the session's check under the field, Insert off.
        CatalogScreen("insert_error", fixtures: ["insert_bpm"]) { scene, _ in
            var ui = MainUiState(mode: .edit)
            if case .insertDirective(let request)? = scene.snapshot.request,
               var state = ui.directiveForm(for: request, snapshot: scene.snapshot) {
                state.form.bpm = scene.snapshot.directiveCheck?.fields["value"]?.stringValue ?? ""
                ui.tools.directive = state
            }
            return PreviewCatalog.mainScreen(scene, ui)
        },
        CatalogScreen("capo", fixtures: ["capo_advice"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .edit))
        },
        // C, E, G and B selected, Cmaj7 picked and sounding: full screen on the iPhone (side by
        // side on its side), a card on the iPad.
        CatalogScreen("identify", fixtures: ["identifier_cmaj7"],
                      devices: CatalogRenderer.upright + [CatalogRenderer.iphoneLandscape]) { scene, _ in
            var ui = MainUiState(mode: .edit, route: .identify)
            ui.tools.identifier = IdentifierModel(typed: scene.snapshot.identifier?.notesText ?? "", picked: "Cmaj7")
            return PreviewCatalog.mainScreen(scene, ui)
        },
        // Settings, from the session's settings edit on Amazing Grace (the voicings as Android's help
        // screenshots have them: My 7-String, Jazz Vocal Trio). On a phone the pages list; with two panes General.
        CatalogScreen("settings", fixtures: ["settings_open"]) { scene, _ in
            PreviewCatalog.settings(scene)
        },
        CatalogScreen("settings_general", fixtures: ["settings_open"], devices: [CatalogRenderer.devices[0]]) { scene, _ in
            PreviewCatalog.settings(scene, nav: SettingsNav(.general))
        },
        CatalogScreen("settings_playback", fixtures: ["settings_open"]) { scene, _ in
            PreviewCatalog.settings(scene, nav: SettingsNav(.playback))
        },
        CatalogScreen("settings_voicings", fixtures: ["settings_voicing_form"]) { scene, _ in
            PreviewCatalog.settings(scene, nav: SettingsNav(.voicings))
        },
        // The Add voicing menu open over the list (live, it is iOS's menu: a stand-in here).
        CatalogScreen("settings_add_voicing", fixtures: ["settings_voicing_form"],
                      devices: [CatalogRenderer.devices[0]]) { scene, _ in
            PreviewCatalog.settings(scene, nav: SettingsNav(.voicings), addMenuShown: true)
        },
        // My 7-String's form; on an iPad on its side the list and the form side by side.
        CatalogScreen("settings_voicing_form", fixtures: ["settings_voicing_form"],
                      devices: CatalogRenderer.upright + [CatalogRenderer.ipadLandscape]) { scene, _ in
            PreviewCatalog.settings(scene, nav: SettingsNav(.voicings, voicingDetail: true))
        },
        // Jazz Vocal Trio: its voices as cards (the phone's form scrolled to them, as Android's help
        // screenshot shows it), and the whole form as a table on an iPad on its side.
        CatalogScreen("settings_voicing_voices", fixtures: ["settings_voicing_ensemble"],
                      devices: [CatalogRenderer.devices[0]]) { scene, _ in
            CatalogColors { PreviewCatalog.voices(scene, colors: $0) }
        },
        CatalogScreen("settings_voicing_ensemble", fixtures: ["settings_voicing_ensemble"],
                      devices: [CatalogRenderer.ipadLandscape]) { scene, _ in
            PreviewCatalog.settings(scene, nav: SettingsNav(.voicings, voicingDetail: true))
        },
        // An unbuildable voicing the core refused: the banner, the red fields.
        CatalogScreen("settings_voicing_refused", fixtures: ["settings_voicing_refused"]) { scene, _ in
            PreviewCatalog.settings(scene, nav: SettingsNav(.voicings, voicingDetail: true))
        },
        // Leaving with those values and a tempo out of range: the question.
        CatalogScreen("settings_problems", fixtures: ["settings_voicing_refused"]) { scene, _ in
            var controller = SettingsController.showing(scene.snapshot, nav: SettingsNav(.voicings, voicingDetail: true))
            controller.setNumber(.bpm, "1000")
            controller.requestClose()
            return PreviewCatalog.settings(scene, controller: controller)
        },
        // A built-in, read-only, with Copy to a new voicing.
        CatalogScreen("settings_builtin", fixtures: ["settings_builtin"],
                      devices: [CatalogRenderer.devices[0], CatalogRenderer.ipadLandscape]) { scene, _ in
            PreviewCatalog.settings(scene, nav: SettingsNav(.voicings, voicingDetail: true))
        },
        CatalogScreen("settings_rename", fixtures: ["settings_voicing_form"], devices: [CatalogRenderer.devices[0]]) { scene, _ in
            var controller = SettingsController.showing(scene.snapshot, nav: SettingsNav(.voicings, voicingDetail: true))
            controller.askRename("My 7-String")
            return PreviewCatalog.settings(scene, controller: controller)
        },
        // Find and Replace (the Qt desktop's bar; Android has none): the Am chords, match case and
        // whole words, the second selected, "Em" to replace them with; in Play without the Replace
        // row (and beside the chord sheet on a phone on its side); after Replace all, its status.
        CatalogScreen("find", fixtures: ["scarborough_edit"]) { scene, _ in
            PreviewCatalog.mainScreen(PreviewCatalog.finding(scene, query: "Am", replacement: "Em", current: 2,
                                                             matchCase: true, wholeWord: true),
                                      MainUiState(mode: .edit))
        },
        CatalogScreen("find_play", fixtures: ["scarborough_piano_roll"],
                      devices: CatalogRenderer.upright + [CatalogRenderer.iphoneLandscape]) { scene, _ in
            PreviewCatalog.mainScreen(PreviewCatalog.finding(scene, query: "parsley", current: 1, canReplace: false),
                                      MainUiState(mode: .play))
        },
        CatalogScreen("find_replaced", fixtures: ["find_replaced"]) { scene, _ in
            PreviewCatalog.mainScreen(PreviewCatalog.finding(scene, query: "Am", replacement: "Em", current: 0,
                                                             matchCase: true, wholeWord: true),
                                      MainUiState(mode: .edit),
                                      snackbar: scene.snapshot.status.map { Snackbar(text: $0.text, error: false, id: 1) })
        },
        // iPad multitasking: an iPad Air on its side shared in Split View, about a third (also
        // Slide Over's width) and a half. Every layout reads the window, so these are a phone's.
        CatalogScreen("split_play", fixtures: ["scarborough_piano_roll"], devices: CatalogRenderer.split) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play))
        },
        CatalogScreen("split_edit", fixtures: ["scarborough_edit"], devices: CatalogRenderer.split) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .edit))
        },
        CatalogScreen("split_settings", fixtures: ["settings_open"], devices: CatalogRenderer.split) { scene, _ in
            PreviewCatalog.settings(scene)
        },
        CatalogScreen("split_identify", fixtures: ["identifier_cmaj7"], devices: CatalogRenderer.split) { scene, _ in
            var ui = MainUiState(mode: .edit, route: .identify)
            ui.tools.identifier = IdentifierModel(typed: scene.snapshot.identifier?.notesText ?? "", picked: "Cmaj7")
            return PreviewCatalog.mainScreen(scene, ui)
        },
        // About, the licences and one licence's text, from the bundle's licence list.
        CatalogScreen("about", fixtures: ["empty_song"]) { _, _ in
            AboutScreen(info: AboutBuildInfo(versionName: "0.6.2", buildNumber: "1", commit: "f31fbb5",
                                             buildType: "release"), live: false)
        },
        CatalogScreen("licences", fixtures: ["empty_song"]) { _, _ in
            LicencesScreen(entries: AppLicences.entries, live: false)
        },
        CatalogScreen("licence", fixtures: ["empty_song"], devices: [CatalogRenderer.devices[0]]) { _, _ in
            let entry = AppLicences.entries.first { $0.id == "fluidsynth" }
            LicenceDetailScreen(entry: entry, text: entry.flatMap(AppLicences.text), live: false)
        },
        // ☰ › Quick start: the tour's first page (its snippet in the editor's colours).
        CatalogScreen("quick_start", fixtures: ["quick_start_tour"]) { scene, _ in
            QuickStartScreen(content: scene.snapshot.quickStart,
                             showAtStartup: quickStartShowsAtStartup(picked: nil, settings: scene.snapshot.settings,
                                                                     content: scene.snapshot.quickStart),
                             page: .constant(0), live: false)
        },
        // ... and its second page on the phone: the 41-column example shrinks to fit the box.
        CatalogScreen("quick_start_chords", fixtures: ["quick_start_tour"], devices: [CatalogRenderer.devices[0]]) { scene, _ in
            QuickStartScreen(content: scene.snapshot.quickStart, showAtStartup: true, page: .constant(1), live: false)
        },
        // The guide's screenshots (ios/tools/help_shots.json), set up as Android's
        // (android/tools/help_shots.json): Amazing Grace playing, frozen on Em, in every window ...
        CatalogScreen("help_play", fixtures: ["grace_playing"], devices: CatalogRenderer.all) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play))
        },
        // ... the four views with the playhead on the first chord, the player with the
        // metronome on at 125 %, the playhead on Em ...
        CatalogScreen("help_play_phone", fixtures: ["grace_play", "grace_staff", "grace_fret", "grace_tab",
                                                    "grace_playing_metronome", "grace_playhead"],
                      devices: [CatalogRenderer.devices[0]]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play))
        },
        // ... and Edit: Amazing Grace (the bar, the ribbon, on a phone on its side) and the colour demo.
        CatalogScreen("help_edit", fixtures: ["grace_edit", "colours_edit"],
                      devices: CatalogRenderer.upright + [CatalogRenderer.iphoneLandscape]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .edit))
        },
        // ... the Voicing sheet once Settings has made My 7-String (Android's voicing-sheet) ...
        CatalogScreen("help_voicing", fixtures: ["grace_play"], devices: [CatalogRenderer.devices[0]]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play, route: .voicing))
        },
        // ... and Rename on Amazing Grace, as it opens (the name without its extension).
        CatalogScreen("help_rename", fixtures: ["grace_edit"], devices: [CatalogRenderer.devices[0]]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play, route: .rename), renameName: "Amazing Grace")
        },
    ]

    /// Settings over a scene's settings edit, at `nav`.
    static func settings(_ scene: CatalogScene, nav: SettingsNav = SettingsNav(), addMenuShown: Bool = false)
        -> SettingsScreen {
        settings(scene, controller: SettingsController.showing(scene.snapshot, nav: nav), addMenuShown: addMenuShown)
    }

    static func settings(_ scene: CatalogScene, controller: SettingsController, addMenuShown: Bool = false)
        -> SettingsScreen {
        SettingsScreen(controller: controller,
                       schema: scene.snapshot.voicingEditorSchema.map { EditorSchema.parse($0.schema) },
                       live: false, addMenuShown: addMenuShown)
    }

    /// An ensemble's voices as the phone's form shows them once scrolled to
    /// them: the bar, then the records field.
    @ViewBuilder
    static func voices(_ scene: CatalogScene, colors: AppColors) -> some View {
        let state = scene.snapshot.voicingEditor
        let schema = scene.snapshot.voicingEditorSchema.map { EditorSchema.parse($0.schema) }
        let form = state.flatMap { schema?.form($0.model) }
        let all = state.flatMap { state in
            form.map { buildForm($0, values: state.values, errors: state.fieldErrors, hints: state.hints) }
        } ?? []
        // From the voices' section title on, as the scrolled form shows them.
        let records = all.firstIndex { if case .records = $0 { return true } else { return false } } ?? 0
        let start = records > 0 && { if case .header = all[records - 1] { return true } else { return false } }()
            ? records - 1 : records
        let items = Array(all[start...])
        NavigationStack {
            Form {
                VoicingFormItems(items: items, formKey: "catalog", wide: false, colors: colors, live: false)
            }
            .navigationTitle(state?.selected ?? "")
            .navigationBarTitleDisplayMode(.inline)
        }
    }

    /// A scene with the find bar open on `query` over its text, match
    /// `current` (1-based; 0: none) selected as the bar selects it.
    static func finding(_ scene: CatalogScene, query: String, replacement: String? = nil, current: Int,
                        canReplace: Bool = true, matchCase: Bool = false, wholeWord: Bool = false) -> CatalogScene {
        var editor = scene.editor
        editor.showFind(FindBar.showing(editor, query: query, replacement: replacement, current: current,
                                        canReplace: canReplace, matchCase: matchCase, wholeWord: wholeWord))
        return CatalogScene(snapshot: scene.snapshot, editor: editor, chordSheet: scene.chordSheet)
    }

    /// The main screen of a scene in `ui`'s mode, with what is open over it.
    static func mainScreen(_ scene: CatalogScene, _ ui: MainUiState, renameName: String = "",
                           snackbar: Snackbar? = nil, exportDialog: ExportDialog? = nil) -> MainScreen {
        MainScreen(snapshot: scene.snapshot, editorModel: scene.editor, ui: ui, scrolls: false,
                   chordSheet: scene.chordSheet, snackbar: snackbar, renameName: .constant(renameName),
                   exportDialog: exportDialog)
    }

    /// A recorded scene, or nil (logged) when it's missing.
    static func fixture(_ name: String) -> Fixture? {
        do {
            return try Fixture(contentsOf: AppPaths.fixtures.appendingPathComponent("\(name).json"))
        } catch {
            Log.ui.error("Fixture \(name, privacy: .public): \(String(describing: error), privacy: .public)")
            return nil
        }
    }

    /// A recorded scene folded into a snapshot (an empty one if it's missing,
    /// so a preview still draws).
    static func snapshot(_ fixture: String) -> SessionSnapshot {
        do {
            return try self.fixture(fixture)?.snapshot() ?? SessionSnapshot()
        } catch {
            Log.ui.error("Fixture \(fixture, privacy: .public): \(String(describing: error), privacy: .public)")
            return SessionSnapshot()
        }
    }

    /// The chord sheet buffers a scene recorded.
    static func chordSheet(_ fixture: String) -> ChordSheetSource {
        ChordSheetSource(recorded: self.fixture(fixture))
    }

    /// A recorded scene folded into the editor's model (its text, highlight
    /// and the selection a session edit made).
    static func editor(_ fixture: String) -> EditorModel {
        do {
            return try self.fixture(fixture)?.editorModel() ?? EditorModel()
        } catch {
            Log.ui.error("Fixture \(fixture, privacy: .public): \(String(describing: error), privacy: .public)")
            return EditorModel()
        }
    }

    /// The snapshot, the editor and the chord sheet of a scene.
    static func scene(_ fixture: String) -> CatalogScene {
        CatalogScene(snapshot: snapshot(fixture), editor: editor(fixture), chordSheet: chordSheet(fixture))
    }
}

/// The sizes, colour schemes and text sizes the catalog is rendered in.
enum CatalogRenderer {
    struct Device {
        let name: String
        let size: CGSize
        let scale: CGFloat
        /// The software keyboard's height there (with its suggestions bar).
        var keyboardHeight: CGFloat = 0
        /// The window's size classes there (the catalog runs on the iPhone
        /// simulator, so an iPad's window gets them as traits).
        var horizontal: UIUserInterfaceSizeClass = .compact
        var vertical: UIUserInterfaceSizeClass = .regular
    }

    /// iPhone 17 and iPad Air 11-inch (M4), upright, in points.
    static let devices = [
        Device(name: "iphone", size: CGSize(width: 402, height: 874), scale: 3, keyboardHeight: 336),
        Device(name: "ipad", size: CGSize(width: 820, height: 1180), scale: 2, keyboardHeight: 398,
               horizontal: .regular),
    ]
    static let iphoneLandscape = Device(name: "iphone-landscape", size: CGSize(width: 874, height: 402), scale: 3,
                                        keyboardHeight: 209, vertical: .compact)
    static let ipadLandscape = Device(name: "ipad-landscape", size: CGSize(width: 1180, height: 820), scale: 2,
                                      keyboardHeight: 398, horizontal: .regular)
    /// The iPad Air on its side in Split View: about a third (also Slide Over's
    /// width) and a half of its 1180 pt. The exact widths vary by model.
    static let ipadThird = Device(name: "ipad-third", size: CGSize(width: 375, height: 820), scale: 2,
                                  keyboardHeight: 398)
    static let ipadHalf = Device(name: "ipad-half", size: CGSize(width: 585, height: 820), scale: 2,
                                 keyboardHeight: 398)
    static var split: [Device] { [ipadThird, ipadHalf] }
    static var upright: [Device] { devices }
    static var all: [Device] { devices + [iphoneLandscape, ipadLandscape] }
    static let schemes: [(String, ColorScheme)] = [("light", .light), ("dark", .dark)]
    /// The default size, and Accessibility Extra Large (two steps short of the
    /// largest with Larger Accessibility Sizes on).
    static let textSizes: [(String, DynamicTypeSize)] = [("default", .large), ("large", .accessibility3)]

    /// How a window is captured: its layers drawn into a context (works off
    /// the screen, at any size), or the render server's snapshot of the window.
    enum Capture { case layers, snapshot }

    /// How many images ``renderAll(to:)`` writes.
    @MainActor static var imageCount: Int {
        PreviewCatalog.screens.reduce(0) { $0 + $1.fixtures.count * $1.devices.count } * schemes.count
            * textSizes.count
    }

    /// Render every entry into `folder` as `<screen>-<fixture>-<device>-<scheme>-<text>.png`.
    @MainActor static func renderAll(to folder: URL) throws -> [URL] {
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        var written: [URL] = []
        for screen in PreviewCatalog.screens {
            for fixture in screen.fixtures {
                let scene = PreviewCatalog.scene(fixture)
                for device in screen.devices {
                    for (schemeName, scheme) in schemes {
                        for (textName, textSize) in textSizes {
                            // Each render's images go with its pool: run 45453289126's
                            // renderer drew only black once some 340 images were held.
                            let png: Data? = autoreleasepool {
                                for _ in 0..<2 {
                                    if let image = render(screen.make(scene, device), device: device, scheme: scheme,
                                                          textSize: textSize),
                                       !isBlank(image) {
                                        return image.pngData()
                                    }
                                }
                                return nil
                            }
                            guard let png else {
                                throw CatalogError("\(screen.name)/\(fixture) on \(device.name), \(schemeName), "
                                                   + "\(textName): no image, or one of a single colour")
                            }
                            let url = folder.appendingPathComponent(
                                "\(screen.name)-\(fixture)-\(device.name)-\(schemeName)-\(textName).png")
                            try png.write(to: url)
                            written.append(url)
                        }
                    }
                }
            }
        }
        return written
    }

    /// `view` in a `device`-sized window of the app's scene, with the
    /// device's size classes, `scheme` and `textSize`, captured. A window, not
    /// ImageRenderer, so the system's controls (lists, navigation bars,
    /// switches, segmented controls, text fields) draw as they do live; the
    /// window lies off the screen with no safe area, as the catalog has always
    /// drawn the screens (under the status bar's height of nothing).
    @MainActor static func render(_ view: AnyView, device: Device, scheme: ColorScheme, textSize: DynamicTypeSize,
                                  capture: Capture = .snapshot) -> UIImage? {
        guard let scene = UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene }).first else {
            return nil
        }
        let window = UIWindow(windowScene: scene)
        let root = view
            .frame(width: device.size.width, height: device.size.height)
            .environment(\.colorScheme, scheme)
            .environment(\.dynamicTypeSize, textSize)
        let host = UIHostingController(rootView: AnyView(root))
        host.safeAreaRegions = []
        host.overrideUserInterfaceStyle = scheme == .dark ? .dark : .light
        host.traitOverrides.preferredContentSizeCategory = EditorAppearance.category(textSize)
        host.traitOverrides.horizontalSizeClass = device.horizontal
        host.traitOverrides.verticalSizeClass = device.vertical
        window.frame = CGRect(origin: CGPoint(x: 0, y: scene.screen.bounds.height + 400), size: device.size)
        window.overrideUserInterfaceStyle = host.overrideUserInterfaceStyle
        window.rootViewController = host
        window.isHidden = false
        defer {
            window.isHidden = true
            window.rootViewController = nil
        }
        settle(window)
        let insets = host.view.safeAreaInsets
        if insets != .zero {
            host.additionalSafeAreaInsets = UIEdgeInsets(top: -insets.top, left: -insets.left,
                                                         bottom: -insets.bottom, right: -insets.right)
            settle(window)
        }
        lastInsets = (window.safeAreaInsets, host.view.safeAreaInsets)
        let format = UIGraphicsImageRendererFormat()
        format.scale = device.scale
        format.opaque = true
        let renderer = UIGraphicsImageRenderer(size: device.size, format: format)
        return renderer.image { context in
            switch capture {
            case .layers:
                window.layer.render(in: context.cgContext)
            case .snapshot:
                window.drawHierarchy(in: CGRect(origin: .zero, size: device.size), afterScreenUpdates: true)
            }
        }
    }

    /// The window's and the screen's safe area at the last render (the probe reports them).
    @MainActor static var lastInsets: (window: UIEdgeInsets, host: UIEdgeInsets) = (.zero, .zero)

    /// Layout, then a few turns of the run loop for what SwiftUI and UIKit
    /// put off (a list's cells, a navigation bar's items).
    @MainActor private static func settle(_ window: UIWindow) {
        for _ in 0..<3 {
            window.layoutIfNeeded()
            RunLoop.main.run(until: Date().addingTimeInterval(0.02))
        }
        window.layoutIfNeeded()
    }
}

/// Whether `image` is one colour all over (what a failed render draws).
func isBlank(_ image: UIImage) -> Bool {
    guard let cgImage = image.cgImage else { return true }
    let side = 24
    var pixels = [UInt8](repeating: 0, count: side * side * 4)
    let drawn = pixels.withUnsafeMutableBytes { buffer -> Bool in
        guard let context = CGContext(data: buffer.baseAddress, width: side, height: side, bitsPerComponent: 8,
                                      bytesPerRow: side * 4, space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return false }
        context.interpolationQuality = .medium
        context.draw(cgImage, in: CGRect(x: 0, y: 0, width: side, height: side))
        return true
    }
    guard drawn else { return true }
    let first = Array(pixels[0..<4])
    return stride(from: 0, to: pixels.count, by: 4).allSatisfy { Array(pixels[$0..<$0 + 4]) == first }
}

struct CatalogError: Error, CustomStringConvertible {
    let description: String

    init(_ description: String) {
        self.description = description
    }
}

extension SelfTestReport {
    /// A passed report with plausible values, for the catalog.
    static let sample = SelfTestReport(
        date: "2026-11-24T10:00:00Z",
        build: BuildInfo(version: "0.6.2", build: "1", commit: "catalog", date: "2026-11-24"),
        device: "iPhone iOS 26.5",
        timings: LaunchTimings(pythonBoot: 0.42, sessionStart: 3.1, firstText: 3.4),
        offlineRender: Render(ok: true, peak: 9120, frames: 22050, seconds: 0.08, error: nil),
        liveAudio: AudioStatus(session: true, initialized: true, error: nil, soundfont: "GeneralUser-GS.sf2"),
        auditionMessages: [],
        audioCategory: "AVAudioSessionCategoryPlayback",
        audioOptions: ["mixWithOthers"],
        audioRoute: ["Speaker: Speaker"],
        sampleRate: 48000,
        ioBufferDuration: 0.0107,
        problems: [])
}

/// Every catalog entry in a list (for Previews; not reachable in the app).
struct CatalogView: View {
    var body: some View {
        NavigationStack {
            List {
                ForEach(PreviewCatalog.screens, id: \.name) { screen in
                    Section(screen.name) {
                        ForEach(screen.fixtures, id: \.self) { fixture in
                            NavigationLink(fixture) {
                                screen.make(PreviewCatalog.scene(fixture), screen.devices[0])
                            }
                        }
                    }
                }
            }
            .navigationTitle("Catalog")
        }
    }
}

/// The main screen's colours for the environment's scheme, for a view drawn on its own.
struct CatalogColors<Content: View>: View {
    @Environment(\.colorScheme) private var scheme
    @ViewBuilder let content: (AppColors) -> Content

    var body: some View {
        content(AppColors.forScheme(dark: scheme == .dark))
    }
}

#Preview("Catalog") {
    CatalogView()
}

#Preview("Play, piano roll") {
    PreviewCatalog.mainScreen(PreviewCatalog.scene("scarborough_piano_roll"), MainUiState(mode: .play))
}

#Preview("Edit, dark") {
    PreviewCatalog.mainScreen(PreviewCatalog.scene("editor_mid_edit"), MainUiState(mode: .edit))
        .preferredColorScheme(.dark)
}
