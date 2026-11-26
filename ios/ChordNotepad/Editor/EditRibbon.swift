import ChordNotepadKit
import SwiftUI

/// The Edit ribbon under the header (Android's `ui/main/EditRibbon.kt`, one
/// 48 pt row): Undo, Redo, Find (iOS's) | Insert, Transpose, Capo, Identify |
/// AB/Do, Convert. Drawn as an iOS toolbar: each button a symbol and its
/// caption in the accent colour (grey when it can't act), AB/Do a segmented
/// control. When the row is wider than the window it scrolls sideways; a
/// fade and a › chevron show there's more to the right, a fade on the left
/// once scrolled (`RibbonEdges`).
///
/// It sits at the top rather than above the keyboard (an
/// `inputAccessoryView`), as on Android: it stays put with a hardware
/// keyboard or none. The same view is live and in the catalog (`perform`
/// nil: inert, the row cut at the edge).
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

    @State private var offset: CGFloat = 0
    @State private var contentWidth: CGFloat = 0
    @State private var viewport: CGFloat = 0

    /// The ribbon's height (Android's `BAR_HEIGHT_DP`).
    static let height: CGFloat = 48

    private var background: Color { Color(uiColor: .systemBackground) }

    var body: some View {
        ViewThatFits(in: .horizontal) {
            row
                .frame(maxWidth: .infinity, alignment: .leading)
            overflowing
        }
        .frame(height: Self.height)
        .frame(maxWidth: .infinity)
        .background(background)
        // The captions follow the text size up to a point: the row is a fixed 48 pt.
        .dynamicTypeSize(...DynamicTypeSize.xLarge)
    }

    private var row: some View {
        HStack(spacing: 1) {
            button(AccessibilityLabels.undo, AppSymbols.undo, enabled: canUndo) { perform?(.undo) }
            button(AccessibilityLabels.redo, AppSymbols.redo, enabled: canRedo) { perform?(.redo) }
            // Find (and Replace): Android's ribbon has none; the desktop's is Edit › Find and Replace.
            button("Find", AppSymbols.find, label: AccessibilityLabels.find, id: "ribbon-find") { find?() }
            separator
            toolButton(AccessibilityLabels.insert, .insert, AppSymbols.insert)
            toolButton(AccessibilityLabels.transpose, .transpose, AppSymbols.transpose)
            toolButton(AccessibilityLabels.capo, .capo, AppSymbols.capo)
            toolButton(AccessibilityLabels.identify, .identify, AppSymbols.identify)
            separator
            notationSegments
            convertButton
                .id("ribbon-end")
        }
        .padding(.horizontal, 4)
        .fixedSize(horizontal: true, vertical: false)
    }

    /// Wider than the window: live, a sideways scroll with Android's fades
    /// and chevron; in the catalog, the row cut at the edge with the same ends.
    @ViewBuilder
    private var overflowing: some View {
        let edges = RibbonEdges.of(Double(offset), Double(max(contentWidth - viewport, 0)))
        ScrollViewReader { proxy in
            ZStack {
                if scrolls {
                    ScrollView(.horizontal, showsIndicators: false) {
                        row
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
                        .overlay(alignment: .leading) { row.padding(.trailing, 24) }
                        .clipped()
                }
            }
            .background(GeometryReader { geometry in
                Color.clear.onAppear { viewport = geometry.size.width }
                    .onChange(of: geometry.size.width) { _, width in viewport = width }
            })
            .overlay(alignment: .leading) {
                if scrolls && edges.fadeLeft {
                    LinearGradient(colors: [background, background.opacity(0)], startPoint: .leading,
                                   endPoint: .trailing)
                        .frame(width: 36)
                        .allowsHitTesting(false)
                }
            }
            .overlay(alignment: .trailing) {
                if !scrolls || edges.more {
                    ZStack(alignment: .trailing) {
                        LinearGradient(stops: [.init(color: background.opacity(0), location: 0),
                                               .init(color: background, location: 0.7)],
                                       startPoint: .leading, endPoint: .trailing)
                            .frame(width: 36)
                            .allowsHitTesting(false)
                        Button {
                            withAnimation { proxy.scrollTo("ribbon-end", anchor: .trailing) }
                        } label: {
                            Image(systemName: AppSymbols.chevronRight)
                                .font(.body.weight(.semibold))
                                .frame(width: 28, height: Self.height)
                                .contentShape(Rectangle())
                        }
                        .buttonStyle(.borderless)
                        .accessibilityLabel(AccessibilityLabels.moreTools)
                        .accessibilityIdentifier("ribbon-more")
                    }
                }
            }
        }
    }

    private func toolButton(_ caption: String, _ tool: RibbonTool, _ symbol: String) -> some View {
        button(caption, symbol, id: "ribbon-\(caption.lowercased())") { self.tool?(tool) }
    }

    /// A symbol over its caption, both in the accent colour (the system's
    /// borderless button), grey while it can't act.
    private func button(_ caption: String, _ symbol: String, label: String? = nil, enabled: Bool = true,
                        id: String? = nil, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 1) {
                AppIcon(symbol, tint: nil, size: 18)
                    .frame(height: 24)
                Text(caption)
                    .font(.caption2)
                    .lineLimit(1)
            }
            .padding(.horizontal, 6)
            .frame(minWidth: 44, minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.borderless)
        // Inert in the catalog (perform nil) but not dimmed, so it shows what a person sees.
        .disabled(!enabled)
        .accessibilityLabel(label ?? caption)
        .modifier(OptionalIdentifier(id: id))
    }

    private var convertButton: some View {
        Button {
            perform?(.convertNotation)
        } label: {
            VStack(spacing: 1) {
                ConvertIcon()
                    .frame(height: 24)
                Text(AccessibilityLabels.convert)
                    .font(.caption2)
                    .lineLimit(1)
            }
            .padding(.horizontal, 6)
            .frame(minWidth: 44, minHeight: 44)
            .contentShape(Rectangle())
        }
        .buttonStyle(.borderless)
        .disabled(readOnly)
        .accessibilityLabel(AccessibilityLabels.convert)
    }

    private var separator: some View {
        Color(uiColor: .separator)
            .frame(width: 0.5, height: 28)
            .padding(.horizontal, 5)
    }

    /// AB | Do: the notation the text is read in, as a segmented control.
    private var notationSegments: some View {
        Picker(AccessibilityLabels.americanNotation,
               selection: Binding(get: { notation ?? "" },
                                  set: { value in if value != notation { perform?(.setNotation(value)) } })) {
            Text("AB")
                .accessibilityLabel(AccessibilityLabels.americanNotation)
                .tag("american")
            Text("Do")
                .accessibilityLabel(AccessibilityLabels.europeanNotation)
                .tag("european")
        }
        .pickerStyle(.segmented)
        .labelsHidden()
        .fixedSize()
        .padding(.horizontal, 4)
        .accessibilityIdentifier("ribbon-notation")
    }
}

/// An accessibility identifier when there is one.
private struct OptionalIdentifier: ViewModifier {
    let id: String?

    func body(content: Content) -> some View {
        if let id {
            content.accessibilityIdentifier(id)
        } else {
            content
        }
    }
}

/// Convert's icon: a C with ↘ at the top left, ↖ Do at the bottom right
/// (Android's `ConvertIcon`), in the button's colour.
private struct ConvertIcon: View {
    var body: some View {
        ZStack(alignment: .topLeading) {
            Text("C")
                .font(.system(size: 13, weight: .bold))
                .offset(x: 2, y: -2)
            Image(systemName: "arrow.down.right")
                .font(.system(size: 9, weight: .bold))
                .offset(x: 13, y: 1)
            Image(systemName: "arrow.up.left")
                .font(.system(size: 9, weight: .bold))
                .offset(x: 2, y: 13)
            Text("Do")
                .font(.system(size: 11, weight: .bold))
                .offset(x: 12, y: 10)
        }
        .frame(width: 28, height: 24, alignment: .topLeading)
        .accessibilityHidden(true)
    }
}
