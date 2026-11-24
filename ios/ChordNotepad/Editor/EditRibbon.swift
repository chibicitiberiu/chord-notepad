import ChordNotepadKit
import SwiftUI

/// The Edit ribbon under the header (Android's `ui/main/EditRibbon.kt`, one
/// 48 pt row): Undo, Redo, Find (iOS's) | Insert, Transpose, Capo, Identify |
/// AB/Do, Convert. When the row is wider than the window it scrolls sideways; a
/// fade and a › chevron show there's more to the right, a fade on the left
/// once scrolled (`RibbonEdges`).
///
/// It sits at the top rather than above the keyboard (an
/// `inputAccessoryView`), as on Android: it stays put with a hardware
/// keyboard or none, and the preview catalog can draw it. The same view is
/// live and in the catalog (`perform` nil: inert, the row cut at the edge).
struct EditRibbon: View {
    let canUndo: Bool
    let canRedo: Bool
    /// `american` or `european`; nil before the session says.
    let notation: String?
    var readOnly = false
    var perform: ((EditorAction) -> Void)?
    /// The tool buttons (Insert, Transpose, Capo, Identify).
    var tool: ((RibbonTool) -> Void)?
    /// Find (and Replace): the bar under the text.
    var find: (() -> Void)?
    /// False in the catalog: no ScrollView.
    var scrolls = true

    @Environment(\.colorScheme) private var colorScheme
    @State private var offset: CGFloat = 0
    @State private var contentWidth: CGFloat = 0
    @State private var viewport: CGFloat = 0

    /// The ribbon's height (Android's `BAR_HEIGHT_DP`).
    static let height: CGFloat = 48

    var body: some View {
        let palette = EditorPalette.forScheme(dark: colorScheme == .dark)
        ViewThatFits(in: .horizontal) {
            row(palette)
                .frame(maxWidth: .infinity, alignment: .leading)
            overflowing(palette)
        }
        .frame(height: Self.height)
        .frame(maxWidth: .infinity)
        .background(palette.ribbon.swiftUI)
        // The captions follow the text size up to a point: the row is a fixed 48 pt.
        .dynamicTypeSize(...DynamicTypeSize.xLarge)
    }

    private func row(_ palette: EditorPalette) -> some View {
        HStack(spacing: 1) {
            button("Undo", enabled: canUndo, action: .undo) {
                Image(systemName: "arrow.uturn.backward").foregroundStyle(RibbonTints.undo)
            }
            button("Redo", enabled: canRedo, action: .redo) {
                Image(systemName: "arrow.uturn.forward").foregroundStyle(RibbonTints.undo)
            }
            findButton(palette)
            separator(palette)
            toolButton("Insert", .insert, "mdi_plus", IconTints.insert)
            toolButton("Transpose", .transpose, "ic_transpose", IconTints.transpose, width: 32)
            toolButton("Capo", .capo, "ic_capo", IconTints.capo)
            toolButton("Identify", .identify, "mdi_piano", IconTints.identify)
            separator(palette)
            notationSegments(palette)
            button("Convert", enabled: !readOnly, action: .convertNotation) {
                ConvertIcon()
            }
            .id("ribbon-end")
        }
        .padding(.horizontal, 4)
        .fixedSize(horizontal: true, vertical: false)
    }

    /// Wider than the window: live, a sideways scroll with Android's fades
    /// and chevron; in the catalog, the row cut at the edge with the same ends.
    @ViewBuilder
    private func overflowing(_ palette: EditorPalette) -> some View {
        let edges = RibbonEdges.of(Double(offset), Double(max(contentWidth - viewport, 0)))
        ScrollViewReader { proxy in
            ZStack {
                if scrolls {
                    ScrollView(.horizontal, showsIndicators: false) {
                        row(palette)
                            .padding(.trailing, 24)
                            .background(GeometryReader { geometry in
                                Color.clear
                                    .onAppear { contentWidth = geometry.size.width }
                                    .onChange(of: geometry.frame(in: .named("ribbon")).minX) { _, x in
                                        offset = -x
                                    }
                            })
                    }
                    .coordinateSpace(name: "ribbon")
                } else {
                    // The row's own width must not widen the screen: a flexible
                    // stand-in takes the window's width, the row lies over it, cut.
                    Color.clear
                        .frame(maxWidth: .infinity)
                        .overlay(alignment: .leading) { row(palette).padding(.trailing, 24) }
                        .clipped()
                }
            }
            .background(GeometryReader { geometry in
                Color.clear.onAppear { viewport = geometry.size.width }
                    .onChange(of: geometry.size.width) { _, width in viewport = width }
            })
            .overlay(alignment: .leading) {
                if scrolls && edges.fadeLeft {
                    LinearGradient(colors: [palette.ribbon.swiftUI, palette.ribbon.swiftUI.opacity(0)],
                                   startPoint: .leading, endPoint: .trailing)
                        .frame(width: 36)
                        .allowsHitTesting(false)
                }
            }
            .overlay(alignment: .trailing) {
                if !scrolls || edges.more {
                    ZStack(alignment: .trailing) {
                        LinearGradient(stops: [.init(color: palette.ribbon.swiftUI.opacity(0), location: 0),
                                               .init(color: palette.ribbon.swiftUI, location: 0.7)],
                                       startPoint: .leading, endPoint: .trailing)
                            .frame(width: 36)
                            .allowsHitTesting(false)
                        Button {
                            withAnimation { proxy.scrollTo("ribbon-end", anchor: .trailing) }
                        } label: {
                            MdiIcon("mdi_chevron_right", tint: palette.muted.swiftUI, size: 22)
                                .frame(width: 28, height: Self.height)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("Show more tools")
                        .accessibilityIdentifier("ribbon-more")
                    }
                }
            }
        }
    }

    /// Find: the find bar with its Replace row (Android's ribbon has no Find;
    /// the desktop's is Edit › Find and Replace).
    private func findButton(_ palette: EditorPalette) -> some View {
        Button {
            find?()
        } label: {
            VStack(spacing: 1) {
                Image(systemName: "magnifyingglass")
                    .font(.system(size: 19, weight: .medium))
                    .foregroundStyle(RibbonTints.convertBlue)
                    .frame(height: 24)
                Text("Find")
                    .font(.caption2.weight(.medium))
                    .foregroundStyle(palette.ribbonText.swiftUI)
                    .lineLimit(1)
            }
            .padding(.horizontal, 6)
            .frame(minWidth: 44, minHeight: 44)
            .contentShape(RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Find and Replace")
        .accessibilityIdentifier("ribbon-find")
    }

    private func toolButton(_ label: String, _ tool: RibbonTool, _ icon: String, _ tint: SheetColor,
                            width: CGFloat = 24) -> some View {
        let palette = EditorPalette.forScheme(dark: colorScheme == .dark)
        return Button {
            self.tool?(tool)
        } label: {
            VStack(spacing: 1) {
                MdiIcon(icon, tint: tint.swiftUI, width: width)
                Text(label)
                    .font(.caption2.weight(.medium))
                    .foregroundStyle(palette.ribbonText.swiftUI)
                    .lineLimit(1)
            }
            .padding(.horizontal, 6)
            .frame(minWidth: 44, minHeight: 44)
            .contentShape(RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
        .accessibilityIdentifier("ribbon-\(label.lowercased())")
    }

    private func button<Icon: View>(_ label: String, enabled: Bool, action: EditorAction,
                                    @ViewBuilder icon: () -> Icon) -> some View {
        let palette = EditorPalette.forScheme(dark: colorScheme == .dark)
        return Button {
            perform?(action)
        } label: {
            VStack(spacing: 1) {
                icon()
                    .font(.system(size: 19, weight: .medium))
                    .frame(height: 24)
                Text(label)
                    .font(.caption2.weight(.medium))
                    .foregroundStyle(palette.ribbonText.swiftUI)
                    .lineLimit(1)
            }
            .padding(.horizontal, 6)
            .frame(minWidth: 44, minHeight: 44)
            .contentShape(RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
        .opacity(enabled ? 1 : 0.38)
        // Inert in the catalog (perform nil) but not dimmed, so it shows what a person sees.
        .disabled(!enabled)
        .accessibilityLabel(label)
    }

    private func separator(_ palette: EditorPalette) -> some View {
        palette.line.swiftUI
            .frame(width: 1, height: 28)
            .padding(.horizontal, 4)
    }

    /// AB | Do: the notation the text is read in.
    private func notationSegments(_ palette: EditorPalette) -> some View {
        HStack(spacing: 0) {
            ForEach(["american", "european"], id: \.self) { value in
                let on = notation == value
                let label = value == "american" ? "AB" : "Do"
                Button {
                    if !on { perform?(.setNotation(value)) }
                } label: {
                    Text(label)
                        .font(.footnote.weight(.medium))
                        .foregroundStyle((on ? palette.primary : palette.muted).swiftUI)
                        .padding(.horizontal, 9)
                        .frame(maxHeight: .infinity)
                        .background((on ? palette.primarySoft : palette.surfaceLow).swiftUI)
                }
                .buttonStyle(.plain)
                .accessibilityLabel(value == "american" ? "American notation" : "European notation")
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
        .frame(height: 30)
        .clipShape(Capsule())
        .overlay(Capsule().stroke(palette.line.swiftUI, lineWidth: 1))
        .padding(.horizontal, 2)
    }
}

/// Android's per-function icon tints (`IconTints`).
enum RibbonTints {
    static let undo = Color(.sRGB, red: 0x5C / 255, green: 0x6B / 255, blue: 0xC0 / 255)
    static let convertBlue = Color(.sRGB, red: 0x1E / 255, green: 0x88 / 255, blue: 0xE5 / 255)
    static let convertOrange = Color(.sRGB, red: 0xFB / 255, green: 0x8C / 255, blue: 0x00 / 255)
}

/// Convert's icon: a blue C with ↘ at the top left, an orange ↖ Do at the
/// bottom right (Android's `ConvertIcon`).
private struct ConvertIcon: View {
    var body: some View {
        ZStack(alignment: .topLeading) {
            Text("C")
                .font(.system(size: 13, weight: .bold))
                .foregroundStyle(RibbonTints.convertBlue)
                .offset(x: 2, y: -2)
            Image(systemName: "arrow.down.right")
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(RibbonTints.convertBlue)
                .offset(x: 13, y: 1)
            Image(systemName: "arrow.up.left")
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(RibbonTints.convertOrange)
                .offset(x: 2, y: 13)
            Text("Do")
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(RibbonTints.convertOrange)
                .offset(x: 12, y: 10)
        }
        .frame(width: 28, height: 24, alignment: .topLeading)
        .accessibilityHidden(true)
    }
}
