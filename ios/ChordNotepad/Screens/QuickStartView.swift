import ChordNotepadKit
import SwiftUI

/// ☰ › Quick start (Android's `QuickStartScreen`): the tour's pages one at a
/// time (a title, paragraphs and read-only example snippets drawn with the
/// editor's colours), Previous / Next, a "Show at startup" checkbox and an ✕
/// that closes it from any page. The session sends the tour
/// (`request_quick_start`) and keeps the checkbox (`set_show_quick_start_on_startup`,
/// the same setting as Settings › General's switch).
struct QuickStartScreen: View {
    /// The tour, or nil while it is being fetched.
    let content: QuickStartContent?
    let showAtStartup: Bool
    /// The page shown (the catalog sets it; live, the screen keeps it).
    var page: Binding<Int>?
    var live = true
    var setShowAtStartup: (Bool) -> Void = { _ in }
    var close: () -> Void = {}

    @Environment(\.colorScheme) private var scheme
    @State private var ownPage = 0
    private static let snippetPadding = 12.0
    /// The page column's widest and its side margins (`pageView`).
    private static let columnMaxWidth = 640.0
    private static let columnMargin = 20.0
    /// The system monospaced font's character width per point of its size.
    private static let monospacedAdvance: Double = {
        let font = UIFont.monospacedSystemFont(ofSize: 100, weight: .regular)
        return Double(("0" as NSString).size(withAttributes: [.font: font]).width) / 100
    }()
    private var colors: AppColors { .forScheme(dark: scheme == .dark) }
    private var palette: EditorPalette { .forScheme(dark: scheme == .dark) }

    var body: some View {
        NavigationStack {
            GeometryReader { window in
                screen(columnWidth: min(Double(window.size.width) - 2 * Self.columnMargin, Self.columnMaxWidth))
            }
            .navigationTitle(QuickStartTexts.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(action: close) {
                        Image(systemName: AppSymbols.close)
                            .fontWeight(.semibold)
                    }
                    .accessibilityLabel(QuickStartTexts.close)
                    .accessibilityIdentifier("quick-start-close")
                }
            }
        }
        .accessibilityIdentifier("quick-start-screen")
    }

    private func screen(columnWidth: Double) -> some View {
        VStack(spacing: 0) {
            if let content, !content.pages.isEmpty {
                let pager = QuickStartPager(pageCount: content.pages.count, index: page?.wrappedValue ?? ownPage)
                pageView(content.pages[pager.current], columnWidth: columnWidth)
                colors.separator.frame(height: 0.5)
                VStack(spacing: 4) {
                    checkbox
                    buttons(pager)
                }
                .background(colors.bar.ignoresSafeArea(edges: .bottom))
            } else {
                ProgressView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(colors.background.ignoresSafeArea())
    }

    private func go(_ index: Int) {
        if let page { page.wrappedValue = index } else { ownPage = index }
    }

    @ViewBuilder
    private func pageView(_ page: QuickStartPage, columnWidth: Double) -> some View {
        let column = VStack(alignment: .leading, spacing: 12) {
            Text(page.title)
                .font(.title2.weight(.bold))
                .foregroundColor(colors.label)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            ForEach(Array(page.blocks.enumerated()), id: \.offset) { _, block in
                switch block.kind {
                case "snippet": snippet(block, width: columnWidth)
                case "text":
                    Text(block.text)
                        .font(.body)
                        .foregroundColor(colors.label)
                        .fixedSize(horizontal: false, vertical: true)
                // "image": the mobile tour has none (the desktop's screenshot isn't bundled).
                default: EmptyView()
                }
            }
        }
        .frame(maxWidth: Self.columnMaxWidth, alignment: .leading)
        .padding(.horizontal, Self.columnMargin)
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        ScrollView { column }
            .frame(maxHeight: .infinity)
            .id(page.title)
    }

    /// An example song as the editor draws it in the current theme: monospaced,
    /// chords highlighted, not editable. Lines never wrap (a chord stays over
    /// its lyric): the font shrinks so the longest line fits the box
    /// (`snippetFontSize`), and below the smallest size the box scrolls sideways.
    private func snippet(_ block: QuickStartBlock, width: Double) -> some View {
        let size = snippetFontSize(block.text, width: width - 2 * Self.snippetPadding,
                                   advance: Self.monospacedAdvance)
        let text = Text(styled(block))
            .font(.system(size: size, design: .monospaced))
            .foregroundColor(palette.text.swiftUI)
            .fixedSize()
            .padding(Self.snippetPadding)
        return ScrollView(.horizontal) { text }
            .fixedSize(horizontal: false, vertical: true)
            .background(colors.cell, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous).stroke(colors.separator, lineWidth: 0.5))
            .accessibilityLabel(block.text)
    }

    private func styled(_ block: QuickStartBlock) -> AttributedString {
        let ns = NSMutableAttributedString(string: block.text)
        for run in snippetStyleRuns(block, palette: palette) {
            let range = NSRange(location: run.start, length: run.end - run.start)
            if let color = run.style.color { ns.addAttribute(.foregroundColor, value: UIColor(color.swiftUI), range: range) }
            if run.style.underline == true {
                ns.addAttribute(.underlineStyle, value: NSUnderlineStyle.single.rawValue, range: range)
            }
            if let background = run.style.background {
                ns.addAttribute(.backgroundColor, value: UIColor(background.swiftUI), range: range)
            }
        }
        return (try? AttributedString(ns, including: \.uiKit)) ?? AttributedString(block.text)
    }

    /// "Show at startup": the system's switch.
    private var checkbox: some View {
        Toggle(QuickStartTexts.showAtStartup, isOn: Binding(get: { showAtStartup }, set: { setShowAtStartup($0) }))
            .padding(.horizontal, 20)
            .padding(.top, 10)
            .accessibilityIdentifier("quick-start-show")
    }

    /// Previous, "1 of 7", Next (Done on the last page): the system's buttons.
    private func buttons(_ pager: QuickStartPager) -> some View {
        HStack {
            Button(QuickStartTexts.previous) { go(pager.previous().current) }
                .buttonStyle(.bordered)
                .disabled(pager.isFirst)
                .accessibilityIdentifier("quick-start-previous")
            Spacer(minLength: 8)
            Text(QuickStartTexts.pageOf(pager.current + 1, pager.pageCount))
                .font(.subheadline)
                .foregroundColor(colors.secondaryLabel)
            Spacer(minLength: 8)
            Button(pager.isLast ? QuickStartTexts.done : QuickStartTexts.next) {
                pager.isLast ? close() : go(pager.next().current)
            }
            .buttonStyle(.borderedProminent)
            .accessibilityIdentifier(pager.isLast ? "quick-start-done" : "quick-start-next")
        }
        .controlSize(.large)
        .padding(.horizontal, 16)
        .padding(.top, 4)
        .padding(.bottom, 12)
        .dynamicTypeSize(...DynamicTypeSize.accessibility2)
    }
}
