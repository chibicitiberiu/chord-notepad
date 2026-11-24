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

/// ☰ › About (Android's `AboutScreen`): name, version and build, what the app
/// is, who wrote it, its licence and source, the support link the FOSS
/// flavour shows, and the way to the open source licences.
struct AboutScreen: View {
    let info: AboutBuildInfo
    var live = true
    var actions: AboutActions?

    @Environment(\.colorScheme) private var scheme
    private var colors: AppColors { .forScheme(dark: scheme == .dark) }

    var body: some View {
        VStack(spacing: 0) {
            PageBar(title: AboutTexts.title, colors: colors) { actions?.back() }
            if live {
                ScrollView { column }
            } else {
                column.frame(maxHeight: .infinity, alignment: .top).clipped()
            }
        }
        .background(colors.surface.swiftUI.ignoresSafeArea())
        .accessibilityIdentifier("about-screen")
    }

    private var column: some View {
        VStack(spacing: 0) {
            Text(AboutTexts.appName)
                .font(.largeTitle.weight(.bold))
                .foregroundColor(colors.text.swiftUI)
                .multilineTextAlignment(.center)
            VStack(alignment: .leading, spacing: 4) {
                ForEach(Array(info.rows.enumerated()), id: \.offset) { _, row in
                    HStack(alignment: .firstTextBaseline, spacing: 8) {
                        Text(row.label + ":").font(.subheadline.weight(.bold))
                        Text(row.value).font(.subheadline)
                    }
                    .foregroundColor(colors.text.swiftUI)
                    .accessibilityElement(children: .combine)
                }
            }
            .padding(.vertical, 16)
            Text(AboutTexts.description)
                .font(.body)
                .foregroundColor(colors.text.swiftUI)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.vertical, 8)
            Text(AboutTexts.copyright)
                .font(.subheadline)
                .foregroundColor(colors.text.swiftUI)
                .padding(.top, 12)
            link(AboutTexts.license, identifier: "about-license") { actions?.openLicence(appLicenceId, true) }
            link(AboutTexts.source, identifier: "about-source") { actions?.openLink(AboutLinks.source) }
            Text(AboutTexts.warranty)
                .font(.caption)
                .foregroundColor(colors.text.swiftUI)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 8)
            if let support = AboutLinks.support {
                link(AboutTexts.support, identifier: "about-support") { actions?.openLink(support) }
            }
            Rule(colors: colors).padding(.vertical, 16)
            Button { actions?.openLicences() } label: {
                HStack(spacing: 16) {
                    Text(AboutTexts.licences)
                        .font(.body)
                        .foregroundColor(colors.text.swiftUI)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    MdiIcon("app_chevron_right", tint: colors.muted.swiftUI)
                }
                .padding(.horizontal, 16)
                .frame(minHeight: 56)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("about-licences")
        }
        .frame(maxWidth: 640)
        .padding(.horizontal, 24)
        .padding(.vertical, 16)
        .frame(maxWidth: .infinity)
    }

    private func link(_ text: String, identifier: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(text)
                .font(.subheadline)
                .underline()
                .foregroundColor(colors.primary.swiftUI)
                .multilineTextAlignment(.center)
                .padding(.vertical, 8)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(.isLink)
        .accessibilityIdentifier(identifier)
    }
}

/// About › Open source licences (Android's `LicencesScreen`): every component
/// the app is built from, by kind.
struct LicencesScreen: View {
    let entries: [LicenceEntry]
    var live = true
    var actions: AboutActions?

    @Environment(\.colorScheme) private var scheme
    private var colors: AppColors { .forScheme(dark: scheme == .dark) }

    var body: some View {
        VStack(spacing: 0) {
            PageBar(title: AboutTexts.licencesTitle, colors: colors) { actions?.back() }
            if live {
                ScrollView { LazyVStack(alignment: .leading, spacing: 0) { rows } }
            } else {
                VStack(alignment: .leading, spacing: 0) { rows }
                    .frame(maxHeight: .infinity, alignment: .top)
                    .clipped()
            }
        }
        .background(colors.surface.swiftUI.ignoresSafeArea())
        .accessibilityIdentifier("licences-screen")
    }

    @ViewBuilder
    private var rows: some View {
        Text(AboutTexts.licencesIntro)
            .font(.subheadline)
            .foregroundColor(colors.text.swiftUI)
            .fixedSize(horizontal: false, vertical: true)
            .padding(16)
        ForEach(Array(Licences.sections(entries).enumerated()), id: \.offset) { _, section in
            Text(section.group.title)
                .font(.subheadline.weight(.semibold))
                .foregroundColor(colors.primary.swiftUI)
                .padding(.horizontal, 16)
                .padding(.top, 16)
                .padding(.bottom, 4)
                .accessibilityAddTraits(.isHeader)
            ForEach(section.entries) { entry in
                ListRow(headline: entry.title, supporting: entry.license, colors: colors,
                        identifier: "licence-\(entry.id)") {
                    actions?.openLicence(entry.id, false)
                }
            }
        }
    }
}

/// One component's licence (Android's `LicenceDetailScreen`): what it is, who
/// holds the copyright, where its source and website are (opened only on a
/// tap), then the full licence text.
struct LicenceDetailScreen: View {
    let entry: LicenceEntry?
    /// The licence text (nil: it couldn't be read).
    let text: String?
    var live = true
    var actions: AboutActions?

    @Environment(\.colorScheme) private var scheme
    private var colors: AppColors { .forScheme(dark: scheme == .dark) }

    var body: some View {
        VStack(spacing: 0) {
            PageBar(title: entry?.name ?? AboutTexts.licencesTitle, colors: colors) { actions?.back() }
            if live {
                ScrollView { column }
            } else {
                column.frame(maxHeight: .infinity, alignment: .top).clipped()
            }
        }
        .background(colors.surface.swiftUI.ignoresSafeArea())
        .accessibilityIdentifier("licence-screen")
    }

    @ViewBuilder
    private var column: some View {
        if let entry {
            VStack(alignment: .leading, spacing: 8) {
                Text(entry.title)
                    .font(.headline)
                    .foregroundColor(colors.text.swiftUI)
                Group {
                    Text(entry.license)
                    if let copyright = entry.copyright { Text(AboutTexts.copyright(copyright)) }
                    if let note = entry.note { Text(note) }
                }
                .font(.subheadline)
                .foregroundColor(colors.text.swiftUI)
                .fixedSize(horizontal: false, vertical: true)
                if let url = entry.url { link("\(AboutTexts.website): \(url)", url) }
                if let source = entry.sourceURL { link("\(AboutTexts.sourceCode): \(source)", source) }
                Rule(colors: colors).padding(.vertical, 8)
                if let text, !text.isEmpty {
                    Text(text)
                        .font(.system(size: 12, design: .monospaced))
                        .lineSpacing(2)
                        .foregroundColor(colors.text.swiftUI)
                        .fixedSize(horizontal: false, vertical: true)
                        .textSelection(.enabled)
                        .accessibilityIdentifier("licence-text")
                } else {
                    Text(AboutTexts.textMissing)
                        .foregroundColor(colors.text.swiftUI)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
        }
    }

    private func link(_ text: String, _ url: String) -> some View {
        Button { actions?.openLink(url) } label: {
            Text(text)
                .font(.subheadline)
                .underline()
                .foregroundColor(colors.primary.swiftUI)
                .multilineTextAlignment(.leading)
                .fixedSize(horizontal: false, vertical: true)
                .frame(maxWidth: .infinity, alignment: .leading)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(.isLink)
    }
}
