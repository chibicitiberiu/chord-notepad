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
        // An export done: its status in Play's status line; in Edit, as a snackbar.
        CatalogScreen("export", fixtures: ["export_done"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play))
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
        // A family's programs: Guitar, Steel Guitar chosen.
        CatalogScreen("instrument_programs", fixtures: ["player_sheets"]) { scene, _ in
            PreviewCatalog.mainScreen(scene, MainUiState(mode: .play, route: .instrument(family: 3)))
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
        let items = state.flatMap { state in
            form.map { buildForm($0, values: state.values, errors: state.fieldErrors, hints: state.hints) }
        } ?? []
        VStack(spacing: 0) {
            PageBar(title: state?.selected ?? "", colors: colors)
            PageColumn(live: false, spacing: 8, maxWidth: 900) {
                ForEach(items, id: \.key) { item in
                    if case .records(let records) = item {
                        RecordsInput(item: records, formKey: "catalog", wide: false, colors: colors, live: false)
                    }
                }
            }
        }
        .background(colors.surface.swiftUI)
    }

    /// The main screen of a scene in `ui`'s mode, with what is open over it.
    static func mainScreen(_ scene: CatalogScene, _ ui: MainUiState, renameName: String = "",
                           snackbar: Snackbar? = nil) -> MainScreen {
        MainScreen(snapshot: scene.snapshot, editorModel: scene.editor, ui: ui, scrolls: false,
                   chordSheet: scene.chordSheet, snackbar: snackbar, renameName: .constant(renameName))
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
    }

    /// iPhone 17 and iPad Air 11-inch (M4), upright, in points.
    static let devices = [
        Device(name: "iphone", size: CGSize(width: 402, height: 874), scale: 3, keyboardHeight: 336),
        Device(name: "ipad", size: CGSize(width: 820, height: 1180), scale: 2, keyboardHeight: 398),
    ]
    static let iphoneLandscape = Device(name: "iphone-landscape", size: CGSize(width: 874, height: 402), scale: 3,
                                        keyboardHeight: 209)
    static let ipadLandscape = Device(name: "ipad-landscape", size: CGSize(width: 1180, height: 820), scale: 2,
                                      keyboardHeight: 398)
    static var upright: [Device] { devices }
    static var all: [Device] { devices + [iphoneLandscape, ipadLandscape] }
    static let schemes: [(String, ColorScheme)] = [("light", .light), ("dark", .dark)]
    static let textSizes: [(String, DynamicTypeSize)] = [("default", .large), ("large", .accessibility2)]

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
                            let view = screen.make(scene, device)
                                .frame(width: device.size.width, height: device.size.height)
                                .environment(\.colorScheme, scheme)
                                .environment(\.dynamicTypeSize, textSize)
                            let renderer = ImageRenderer(content: view)
                            renderer.scale = device.scale
                            renderer.proposedSize = ProposedViewSize(device.size)
                            guard let png = renderer.uiImage?.pngData() else {
                                throw CatalogError("\(screen.name)/\(fixture) didn't render")
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
