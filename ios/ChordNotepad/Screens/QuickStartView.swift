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
    private var colors: AppColors { .forScheme(dark: scheme == .dark) }
    private var palette: EditorPalette { .forScheme(dark: scheme == .dark) }

    var body: some View {
        VStack(spacing: 0) {
            bar
            if let content, !content.pages.isEmpty {
                let pager = QuickStartPager(pageCount: content.pages.count, index: page?.wrappedValue ?? ownPage)
                pageView(content.pages[pager.current])
                colors.line.swiftUI.frame(height: 1)
                checkbox
                buttons(pager)
            } else {
                ProgressView()
                    .tint(colors.primary.swiftUI)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(colors.surface.swiftUI.ignoresSafeArea())
        .accessibilityIdentifier("quick-start-screen")
    }

    private func go(_ index: Int) {
        if let page { page.wrappedValue = index } else { ownPage = index }
    }

    /// Android's TopAppBar with ✕ (close) and the title.
    private var bar: some View {
        HStack(spacing: 4) {
            Button(action: close) {
                MdiIcon("settings_close", tint: colors.text.swiftUI)
                    .frame(width: 48, height: 48)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(QuickStartTexts.close)
            .accessibilityIdentifier("quick-start-close")
            Text(QuickStartTexts.title)
                .font(.title2)
                .foregroundColor(colors.text.swiftUI)
                .lineLimit(1)
                .accessibilityAddTraits(.isHeader)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 4)
        .frame(height: 64)
        .dynamicTypeSize(...DynamicTypeSize.accessibility1)
    }

    @ViewBuilder
    private func pageView(_ page: QuickStartPage) -> some View {
        let column = VStack(alignment: .leading, spacing: 12) {
            Text(page.title)
                .font(.title2)
                .foregroundColor(colors.text.swiftUI)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            ForEach(Array(page.blocks.enumerated()), id: \.offset) { _, block in
                switch block.kind {
                case "snippet": snippet(block)
                case "text":
                    Text(block.text)
                        .font(.body)
                        .foregroundColor(colors.text.swiftUI)
                        .fixedSize(horizontal: false, vertical: true)
                // "image": the mobile tour has none (the desktop's screenshot isn't bundled).
                default: EmptyView()
                }
            }
        }
        .frame(maxWidth: 640, alignment: .leading)
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
        .frame(maxWidth: .infinity, alignment: .leading)
        if live {
            ScrollView { column }
                .frame(maxHeight: .infinity)
                .id(page.title)
        } else {
            column.topClipped()
        }
    }

    /// An example song as the editor draws it in the current theme: monospaced,
    /// chords highlighted, not editable; it scrolls sideways when wide.
    private func snippet(_ block: QuickStartBlock) -> some View {
        let text = Text(styled(block))
            .font(.system(size: 15, design: .monospaced))
            .foregroundColor(palette.text.swiftUI)
            .fixedSize()
            .padding(12)
        return Group {
            if live {
                ScrollView(.horizontal, showsIndicators: false) { text }
            } else {
                text.frame(maxWidth: .infinity, alignment: .leading).clipped()
            }
        }
        .fixedSize(horizontal: false, vertical: true)
        .background(palette.background.swiftUI, in: RoundedRectangle(cornerRadius: 6))
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(colors.line.swiftUI, lineWidth: 1))
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

    /// "Show at startup", the whole row a toggle.
    private var checkbox: some View {
        Button { setShowAtStartup(!showAtStartup) } label: {
            HStack(spacing: 0) {
                CheckMark(on: showAtStartup, colors: colors)
                    .padding(12)
                Text(QuickStartTexts.showAtStartup)
                    .font(.body)
                    .foregroundColor(colors.text.swiftUI)
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(QuickStartTexts.showAtStartup)
        .accessibilityValue(showAtStartup ? "1" : "0")
        .accessibilityAddTraits(.isToggle)
        .accessibilityIdentifier("quick-start-show")
    }

    private func buttons(_ pager: QuickStartPager) -> some View {
        HStack {
            Button { go(pager.previous().current) } label: {
                Text(QuickStartTexts.previous)
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(pager.isFirst ? colors.text.swiftUI.opacity(AppColors.disabledAlpha)
                                     : colors.primary.swiftUI)
                    .padding(.horizontal, 24)
                    .frame(minHeight: 40)
                    .overlay(Capsule().stroke(colors.line.swiftUI.opacity(pager.isFirst ? 0.5 : 1), lineWidth: 1))
                    .contentShape(Capsule())
            }
            .buttonStyle(.plain)
            .disabled(pager.isFirst)
            .accessibilityIdentifier("quick-start-previous")
            Spacer(minLength: 8)
            Text(QuickStartTexts.pageOf(pager.current + 1, pager.pageCount))
                .font(.subheadline)
                .foregroundColor(colors.text.swiftUI)
            Spacer(minLength: 8)
            Button { pager.isLast ? close() : go(pager.next().current) } label: {
                Text(pager.isLast ? QuickStartTexts.done : QuickStartTexts.next)
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(colors.onPrimary.swiftUI)
                    .padding(.horizontal, 24)
                    .frame(minHeight: 40)
                    .background(colors.primary.swiftUI, in: Capsule())
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier(pager.isLast ? "quick-start-done" : "quick-start-next")
        }
        .padding(.horizontal, 16)
        .padding(.bottom, 12)
        .dynamicTypeSize(...DynamicTypeSize.accessibility2)
    }
}

/// Material's checkbox: a rounded square, filled in the primary colour with a
/// tick when on.
struct CheckMark: View {
    let on: Bool
    let colors: AppColors

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 2)
                .fill(on ? colors.primary.swiftUI : Color.clear)
            RoundedRectangle(cornerRadius: 2)
                .stroke(on ? colors.primary.swiftUI : colors.muted.swiftUI, lineWidth: 2)
            if on {
                Path { path in
                    path.move(to: CGPoint(x: 4, y: 9.5))
                    path.addLine(to: CGPoint(x: 7.5, y: 13))
                    path.addLine(to: CGPoint(x: 14, y: 5.5))
                }
                .stroke(colors.onPrimary.swiftUI, style: StrokeStyle(lineWidth: 2, lineCap: .round, lineJoin: .round))
            }
        }
        .frame(width: 18, height: 18)
        .accessibilityHidden(true)
    }
}
