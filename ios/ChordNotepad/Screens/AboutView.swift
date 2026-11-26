import ChordNotepadKit
import SwiftUI

/// What the About and licence pages do; nil in the catalog.
struct AboutActions {
    var back: () -> Void
    /// Open a licence's text (`fromAbout`: the app's own, from About).
    var openLicence: (_ id: String, _ fromAbout: Bool) -> Void
    var openLicences: () -> Void
    /// Open a link in the browser (only when the user taps one).
    var openLink: (String) -> Void
}

/// The licence list and texts the app ships (`<app>/licenses`, the
/// "Licences" build phase), read once.
@MainActor
enum AppLicences {
    static var directory: URL { AppPaths.bundle.appendingPathComponent("licenses", isDirectory: true) }

    /// The list, or empty (logged) when it can't be read.
    static let entries: [LicenceEntry] = {
        do {
            return try Licences.load(from: directory)
        } catch {
            Log.ui.error("Licences: \(String(describing: error), privacy: .public)")
            return []
        }
    }()

    /// The text of `entry`, or nil when it can't be read.
    static func text(_ entry: LicenceEntry) -> String? {
        try? Licences.text(of: entry, textsDirectory: directory.appendingPathComponent(Licences.texts))
    }
}

/// ☰ › About (Android's `AboutScreen`) as an iOS grouped list: name and what
/// the app is, the version and build, who wrote it, its licence and source
/// (no support link: see `AboutLinks.support`), and the way to the open
/// source licences. Done goes back to the song.
struct AboutScreen: View {
    let info: AboutBuildInfo
    var live = true
    var actions: AboutActions?

    @Environment(\.colorScheme) private var scheme
    private var colors: AppColors { .forScheme(dark: scheme == .dark) }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    VStack(spacing: 6) {
                        Text(AboutTexts.appName)
                            .font(.largeTitle.weight(.bold))
                            .multilineTextAlignment(.center)
                        Text(AboutTexts.description)
                            .font(.subheadline)
                            .foregroundColor(colors.secondaryLabel)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .frame(maxWidth: .infinity)
                    .listRowBackground(Color.clear)
                }
                Section {
                    ForEach(Array(info.rows.enumerated()), id: \.offset) { _, row in
                        LabeledContent(row.label, value: row.value)
                    }
                }
                Section {
                    Text(AboutTexts.copyright)
                    link(AboutTexts.license, identifier: "about-license") { actions?.openLicence(appLicenceId, true) }
                    link(AboutTexts.source, identifier: "about-source") { actions?.openLink(AboutLinks.source) }
                    if let support = AboutLinks.support {
                        link(AboutTexts.support, identifier: "about-support") { actions?.openLink(support) }
                    }
                } footer: {
                    Text(AboutTexts.warranty)
                }
                Section {
                    Button { actions?.openLicences() } label: {
                        HStack {
                            Text(AboutTexts.licences)
                                .foregroundColor(colors.label)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            Chevron()
                        }
                        .contentShape(Rectangle())
                    }
                    .accessibilityIdentifier("about-licences")
                }
            }
            .listStyle(.insetGrouped)
            .pageBar(title: AboutTexts.title, back: nil) { actions?.back() }
        }
        .accessibilityIdentifier("about-screen")
    }

    private func link(_ text: String, identifier: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(text)
                .multilineTextAlignment(.leading)
        }
        .accessibilityAddTraits(.isLink)
        .accessibilityIdentifier(identifier)
    }
}

/// A list row's disclosure chevron, as a navigation link draws it.
struct Chevron: View {
    var body: some View {
        Image(systemName: AppSymbols.chevronRight)
            .font(.footnote.weight(.semibold))
            .foregroundColor(Color(uiColor: .tertiaryLabel))
            .accessibilityHidden(true)
    }
}

/// About › Open source licences (Android's `LicencesScreen`): every component
/// the app is built from, by kind. Back goes to About.
struct LicencesScreen: View {
    let entries: [LicenceEntry]
    var live = true
    var actions: AboutActions?

    @Environment(\.colorScheme) private var scheme
    private var colors: AppColors { .forScheme(dark: scheme == .dark) }

    var body: some View {
        NavigationStack {
            List {
                Section {
                } footer: {
                    Text(AboutTexts.licencesIntro)
                }
                ForEach(Array(Licences.sections(entries).enumerated()), id: \.offset) { _, section in
                    Section(section.group.title) {
                        ForEach(section.entries) { entry in
                            Button { actions?.openLicence(entry.id, false) } label: {
                                HStack(spacing: 8) {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(entry.title)
                                            .foregroundColor(colors.label)
                                        Text(entry.license)
                                            .font(.footnote)
                                            .foregroundColor(colors.secondaryLabel)
                                    }
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    Chevron()
                                }
                                .contentShape(Rectangle())
                            }
                            .accessibilityIdentifier("licence-\(entry.id)")
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .pageBar(title: AboutTexts.licencesTitle, back: AboutTexts.appName) { actions?.back() }
        }
        .accessibilityIdentifier("licences-screen")
    }
}

/// One component's licence (Android's `LicenceDetailScreen`): what it is, who
/// holds the copyright, where its source and website are (opened only on a
/// tap), then the full licence text. Back goes where it came from.
struct LicenceDetailScreen: View {
    let entry: LicenceEntry?
    /// The licence text (nil: it couldn't be read).
    let text: String?
    /// Back's title: the licences, or About for the app's own licence.
    var backTitle = AboutTexts.licencesTitle
    var live = true
    var actions: AboutActions?

    @Environment(\.colorScheme) private var scheme
    private var colors: AppColors { .forScheme(dark: scheme == .dark) }

    var body: some View {
        NavigationStack {
            List {
                if let entry {
                    Section {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(entry.title)
                                .font(.headline)
                            Text(entry.license)
                                .foregroundColor(colors.secondaryLabel)
                        }
                        if let copyright = entry.copyright {
                            Text(AboutTexts.copyright(copyright))
                                .font(.subheadline)
                        }
                        if let note = entry.note {
                            Text(note)
                                .font(.subheadline)
                        }
                        if let url = entry.url { link(AboutTexts.website, url) }
                        if let source = entry.sourceURL { link(AboutTexts.sourceCode, source) }
                    }
                    Section {
                        if let text, !text.isEmpty {
                            Text(text)
                                .font(.system(size: 12, design: .monospaced))
                                .lineSpacing(2)
                                .fixedSize(horizontal: false, vertical: true)
                                .textSelection(.enabled)
                                .accessibilityIdentifier("licence-text")
                        } else {
                            Text(AboutTexts.textMissing)
                        }
                    }
                }
            }
            .listStyle(.insetGrouped)
            .pageBar(title: entry?.name ?? AboutTexts.licencesTitle, back: backTitle) { actions?.back() }
        }
        .accessibilityIdentifier("licence-screen")
    }

    /// A website or the source: its name, the address under it; opened in Safari when tapped.
    private func link(_ name: String, _ url: String) -> some View {
        Button { actions?.openLink(url) } label: {
            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                Text(url)
                    .font(.footnote)
                    .foregroundColor(colors.secondaryLabel)
                    .multilineTextAlignment(.leading)
            }
        }
        .accessibilityAddTraits(.isLink)
    }
}
