import ChordNotepadKit
import SwiftUI
import UIKit

extension SheetColor {
    var swiftUI: Color { Color(.sRGB, red: red, green: green, blue: blue, opacity: alpha) }
}

/// What the chord sheet's controls send; nil in the preview catalog.
struct ChordSheetActions {
    var selectView: (String) -> Void
    var zoom: (Int) -> Void
    var audition: (Int) -> Void
    var setHeight: (Int) -> Void
}

/// The chord sheet under the text: a drag handle, then the pane at the
/// split's height (docs/IOS.md, "Chord sheet"). Dragging resizes live;
/// releasing stores the height (`set_chord_sheet_height`, points on iOS).
/// Nothing at all while the sheet is hidden or there's no room.
struct ChordSheetSplitView: View {
    let state: ChordSheetState
    let source: ChordSheetSource
    /// The height the text and the sheet share.
    let available: Double
    let window: CGSize
    var interactive = true
    var actions: ChordSheetActions?

    /// The height while dragging, and after until the session echoes it back.
    @State private var dragged: Double?
    @State private var dragStart: Double?

    var body: some View {
        let wanted = dragged ?? ChordSheetSplit.wantedHeight(stored: state.height, windowWidth: window.width,
                                                             windowHeight: window.height)
        if let height = ChordSheetSplit.height(wanted: wanted, available: available, windowHeight: window.height) {
            VStack(spacing: 0) {
                handle(height: height)
                ChordSheetPane(state: state, source: source, height: height, interactive: interactive,
                               actions: actions)
                    .frame(height: height)
            }
            .onChange(of: state.height) { _, stored in
                if let dragged, Int(dragged.rounded()) == stored { self.dragged = nil }
            }
        }
    }

    private func handle(height: Double) -> some View {
        let colors = ChordSheetColors.forScheme(dark: scheme == .dark)
        return ZStack {
            colors.surfaceLow.swiftUI
            VStack {
                colors.line.swiftUI.frame(height: 1)
                Spacer(minLength: 0)
            }
            Capsule().fill(colors.grip.swiftUI).frame(width: 36, height: 4)
        }
        .frame(height: ChordSheetSplit.handleHeight)
        .contentShape(Rectangle())
        .gesture(DragGesture(minimumDistance: 2, coordinateSpace: .global)
            .onChanged { drag in
                guard interactive else { return }
                let start = dragStart ?? height
                dragStart = start
                let range = ChordSheetSplit.dragRange(available: available, windowHeight: window.height)
                dragged = min(max(start - drag.translation.height, range.lowerBound), range.upperBound)
            }
            .onEnded { _ in
                dragStart = nil
                if let dragged { actions?.setHeight(Int(dragged.rounded())) }
            })
        .accessibilityLabel(AccessibilityLabels.resizeSheet)
    }

    @Environment(\.colorScheme) private var scheme
}

/// The chord sheet: view tabs and zoom buttons above a horizontally
/// scrolling strip (piano roll, staff, fret cards, tab) with the marker lane
/// on top and a frozen gutter on the left. Tapping a chord auditions it; the
/// chord under the playhead is marked and kept in view; pinch zooms.
struct ChordSheetPane: View {
    let state: ChordSheetState
    @ObservedObject var source: ChordSheetSource
    let height: Double
    var interactive = true
    var actions: ChordSheetActions?

    @Environment(\.colorScheme) private var scheme
    @State private var reason: String?

    private var colors: ChordSheetColors { .forScheme(dark: scheme == .dark) }

    /// The request the strip's height makes (the marker lane excluded).
    private var request: SheetRequest? {
        let laneHeight = source.load.sheet.map { Double($0.buffer.laneHeight) } ?? ChordSheetPaneMetrics.defaultLaneHeight
        let content = ChordSheetPaneMetrics.contentHeight(
            stripHeight: ChordSheetPaneMetrics.stripHeight(paneHeight: height), laneHeight: laneHeight)
        return SheetRequest.of(state, height: content)
    }

    var body: some View {
        let load = source.sheetLoad(for: request)
        VStack(spacing: 0) {
            header
            progress(load.loading)
            ZStack {
                if let sheet = load.sheet {
                    ChordSheetStrip(sheet: sheet, palette: source.palette(for: sheet, colors: colors),
                                    currentIndex: state.currentIndex, cursorIndex: state.cursorIndex,
                                    zoomSupported: state.zoomSupported, zoom: state.zoom,
                                    interactive: interactive, actions: actions)
                } else {
                    colors.surfaceLow.swiftUI
                }
                if let failure = load.failure {
                    Text(failure)
                        .font(.footnote)
                        .foregroundStyle(colors.muted.swiftUI)
                        .multilineTextAlignment(.center)
                        .padding(8)
                }
                if let reason {
                    VStack {
                        Spacer()
                        Text(reason)
                            .font(.footnote)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(.regularMaterial, in: Capsule())
                            .padding(8)
                    }
                    .transition(.opacity)
                }
            }
            .padding(.horizontal, ChordSheetPaneMetrics.stripInset)
            .padding(.bottom, ChordSheetPaneMetrics.stripInset)
        }
        .background(colors.surfaceLow.swiftUI)
        .onAppear { source.follow(request) }
        .onChange(of: request) { _, newRequest in source.follow(newRequest) }
        .task(id: reason) {
            guard reason != nil else { return }
            try? await Task.sleep(for: .seconds(2.5))
            withAnimation { reason = nil }
        }
    }

    /// The views as a segmented control (choosing one the core can't show
    /// says why and keeps the view) and the zoom buttons.
    private var header: some View {
        HStack(spacing: 4) {
            tabs
                .frame(maxWidth: .infinity, alignment: .leading)
            // Views the core says don't zoom show no zoom buttons; pinch follows the same flag.
            if state.zoomSupported {
                zoomButton(AppSymbols.zoomOut, AccessibilityLabels.zoomOut) { actions?.zoom(-1) }
                zoomButton(AppSymbols.zoomIn, AccessibilityLabels.zoomIn) { actions?.zoom(1) }
            }
        }
        .padding(.horizontal, 6)
        .frame(height: ChordSheetPaneMetrics.headerHeight)
        // The header is a fixed 32 pt; the largest text sizes would cut the labels.
        .dynamicTypeSize(...DynamicTypeSize.xLarge)
    }

    private var tabs: some View {
        Picker("Chord sheet view", selection: Binding(get: { state.activeView }, set: { id in
            guard id != state.activeView, let view = state.views.first(where: { $0.viewId == id }) else { return }
            if view.available {
                actions?.selectView(id)
            } else if let why = state.disabledReason, !why.isEmpty {
                withAnimation { reason = why }
            }
        })) {
            ForEach(state.views, id: \.viewId) { view in
                Text(view.label)
                    .accessibilityHint(view.available ? "" : (state.disabledReason ?? ""))
                    .tag(view.viewId)
            }
        }
        .pickerStyle(.segmented)
        .labelsHidden()
        .controlSize(.small)
        .accessibilityIdentifier("chord-sheet-views")
    }

    private func zoomButton(_ symbol: String, _ label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 17))
                .frame(width: 32, height: 30)
                .contentShape(Rectangle())
        }
        .buttonStyle(.borderless)
        .accessibilityLabel(label)
    }

    /// A thin bar while the strip is being fetched (first open, edits, view or zoom changes).
    private func progress(_ loading: Bool) -> some View {
        ZStack {
            if loading {
                LoadingBar(color: colors.primary.swiftUI)
            }
        }
        .frame(maxWidth: .infinity)
        .frame(height: ChordSheetPaneMetrics.progressHeight)
    }
}

/// An indeterminate 2 pt bar (ProgressView's linear style needs a value on iOS).
private struct LoadingBar: View {
    let color: Color
    @State private var phase = false

    var body: some View {
        GeometryReader { geometry in
            color.opacity(0.25)
                .overlay(alignment: .leading) {
                    color
                        .frame(width: geometry.size.width * 0.3)
                        .offset(x: phase ? geometry.size.width * 0.7 : 0)
                }
                .clipped()
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) { phase = true }
        }
    }
}

/// A pinch in progress: its scale so far and the viewport x it zooms about.
struct StripPinch: Equatable {
    var scale: Double
    var focusX: Double
    var committed = false
}

/// What the strip follows, handed to its handlers as one value: an
/// `onChange` action can run with the closure of the update before the
/// change, so it mustn't read the view's own `let`s (the likely cause of S0
/// issue 7: after ⏮ the strip stayed near the paused chord).
struct StripInputs: Equatable {
    let sheet: PreparedSheet
    let currentIndex: Int?
    let cursorIndex: Int?
    /// The strip's width less the gutter.
    let viewport: Double

    static func == (a: StripInputs, b: StripInputs) -> Bool {
        a.sheet.id == b.sheet.id && a.currentIndex == b.currentIndex && a.cursorIndex == b.cursorIndex
            && a.viewport == b.viewport
    }
}

/// A scroll the strip asks its scroll view for.
struct StripJump: Equatable {
    var x: Double
    var animated: Bool
    var id: Int
}

/// The scrolling strip: one `Canvas` that paints the lane, content, playhead
/// and gutter through the kit's painter on CoreGraphics, under a transparent
/// `UIScrollView` (live only) that gives the scrolling its physics and takes
/// the taps and pinches. Scrolling and the playhead only redraw.
struct ChordSheetStrip: View {
    let sheet: PreparedSheet
    let palette: ChordSheetPalette
    let currentIndex: Int?
    let cursorIndex: Int?
    let zoomSupported: Bool
    let zoom: Double
    var interactive = true
    var actions: ChordSheetActions?

    @Environment(\.displayScale) private var displayScale
    @State private var scroll: Double?
    @State private var shown: SheetBuffer?
    @State private var follower = PlayheadFollower()
    @State private var pinch: StripPinch?
    @State private var jump: StripJump?

    var body: some View {
        GeometryReader { geometry in
            let size = geometry.size
            let gutter = Double(sheet.buffer.gutterWidth)
            let scrollX = scroll ?? initialScroll(viewport: size.width - gutter)
            let inputs = StripInputs(sheet: sheet, currentIndex: currentIndex, cursorIndex: cursorIndex,
                                     viewport: Double(size.width) - gutter)
            ZStack(alignment: .topLeading) {
                Canvas { context, canvasSize in
                    let painter = SheetPainter(glyphs: SheetGlyphImages.shared.index, pixelScale: displayScale)
                    let frame = SheetFrame(size: SheetSize(width: canvasSize.width, height: canvasSize.height),
                                           scrollX: scrollX, currentIndex: currentIndex, cursorIndex: cursorIndex)
                    context.withCGContext { cg in
                        painter.paint(sheet, palette: palette, frame: frame,
                                      on: CGSheetCanvas(cg, scale: displayScale))
                    }
                }
                .scaleEffect(CGFloat(pinch?.scale ?? 1), anchor: pinchAnchor(width: Double(size.width), gutter: gutter))
                if interactive {
                    StripScrollOverlay(
                        contentWidth: Double(sheet.buffer.contentWidth) + gutter, jump: jump,
                        onScroll: { scroll = $0 },
                        onTap: { tap($0, gutter: gutter, scrollX: scroll ?? 0) },
                        onPinch: { state, scale, focus in pinchChanged(state, scale: scale, focusX: focus - gutter) })
                }
            }
            .clipped()
            .onAppear { sheetChanged(inputs) }
            .onChange(of: inputs) { old, new in
                if old.sheet.id != new.sheet.id {
                    sheetChanged(new)
                } else {
                    followPlayhead(new)
                }
            }
            .task(id: pinch?.committed) {
                // A pinch that didn't change the zoom (or whose buffer never came) springs back.
                guard pinch?.committed == true else { return }
                try? await Task.sleep(for: .seconds(1.5))
                pinch = nil
            }
        }
        .accessibilityElement()
        .accessibilityLabel("Chord sheet, \(sheet.buffer.slots.count) chords")
    }

    /// A pinch scales about its focus, from the strip's top (Android's transform origin).
    private func pinchAnchor(width: Double, gutter: Double) -> UnitPoint {
        guard width > 0 else { return .topLeading }
        return UnitPoint(x: CGFloat(((pinch?.focusX ?? 0) + gutter) / width), y: 0)
    }

    /// Where a strip seen for the first time starts: with the playhead in view.
    private func initialScroll(viewport: Double) -> Double {
        ChordSheetScroll.target(forChord: currentIndex ?? cursorIndex, in: sheet.buffer, viewportWidth: viewport,
                                currentScroll: 0) ?? 0
    }

    /// A new buffer: keep the same music in view, then follow the playhead.
    private func sheetChanged(_ inputs: StripInputs) {
        let viewport = inputs.viewport
        let buffer = inputs.sheet.buffer
        let previous = shown
        let target: Double
        if let previous, let scroll {
            target = ChordSheetScroll.afterNewBuffer(buffer, previous: previous, scroll: scroll, focusX: pinch?.focusX,
                                                     viewportWidth: viewport)
            if previous.zoom != buffer.zoom || previous.viewId != buffer.viewId { pinch = nil }
        } else {
            target = ChordSheetScroll.target(forChord: inputs.currentIndex ?? inputs.cursorIndex, in: buffer,
                                             viewportWidth: viewport, currentScroll: 0) ?? 0
        }
        shown = buffer
        scroll = target
        jump = StripJump(x: target, animated: false, id: (jump?.id ?? 0) + 1)
        followPlayhead(inputs)
    }

    /// Bring the chord the follower names into view (the desktop's 25 % / 70 % band).
    private func followPlayhead(_ inputs: StripInputs) {
        guard inputs.viewport > 0,
              let index = follower.update(currentIndex: inputs.currentIndex, cursorIndex: inputs.cursorIndex,
                                          sheetID: inputs.sheet.id, viewportWidth: inputs.viewport),
              let target = ChordSheetScroll.target(forChord: index, in: inputs.sheet.buffer,
                                                   viewportWidth: inputs.viewport, currentScroll: scroll ?? 0)
        else { return }
        if interactive {
            jump = StripJump(x: target, animated: true, id: (jump?.id ?? 0) + 1)
        } else {
            scroll = target
        }
    }

    private func tap(_ point: CGPoint, gutter: Double, scrollX: Double) {
        let buffer = sheet.buffer
        guard point.y >= Double(buffer.laneHeight), point.x >= gutter else { return }
        if let slot = buffer.slot(at: Float(scrollX + point.x - gutter)) {
            actions?.audition(slot.chordIndex)
        }
    }

    private func pinchChanged(_ state: UIGestureRecognizer.State, scale: Double, focusX: Double) {
        guard zoomSupported else { return }
        switch state {
        case .began:
            // The focus stays where the fingers first met.
            pinch = StripPinch(scale: scale, focusX: focusX)
        case .changed:
            pinch = StripPinch(scale: scale, focusX: pinch?.focusX ?? focusX)
        case .ended:
            let steps = ChordSheetZoom.pinchSteps(zoomSupported: zoomSupported, scale: scale, currentZoom: zoom)
            Log.ui.info("pinch scale=\(scale) -> \(steps) zoom steps")
            if steps == 0 {
                withAnimation(.easeOut(duration: 0.2)) { pinch = nil }
            } else {
                pinch = StripPinch(scale: scale, focusX: pinch?.focusX ?? focusX, committed: true)
                actions?.zoom(steps)
            }
        default:
            withAnimation(.easeOut(duration: 0.2)) { pinch = nil }
        }
    }
}

/// A transparent scroll view over the strip: its content is as wide as the
/// gutter and the content, and its offset is the strip's scroll. It also
/// takes the taps (audition) and pinches (zoom).
struct StripScrollOverlay: UIViewRepresentable {
    let contentWidth: Double
    let jump: StripJump?
    let onScroll: (Double) -> Void
    let onTap: (CGPoint) -> Void
    let onPinch: (UIGestureRecognizer.State, Double, Double) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> UIScrollView {
        let view = UIScrollView()
        view.backgroundColor = .clear
        view.showsHorizontalScrollIndicator = false
        view.showsVerticalScrollIndicator = false
        view.alwaysBounceVertical = false
        view.contentInsetAdjustmentBehavior = .never
        view.scrollsToTop = false
        view.delegate = context.coordinator
        view.addGestureRecognizer(UITapGestureRecognizer(target: context.coordinator,
                                                         action: #selector(Coordinator.tapped(_:))))
        view.addGestureRecognizer(UIPinchGestureRecognizer(target: context.coordinator,
                                                           action: #selector(Coordinator.pinched(_:))))
        return view
    }

    func updateUIView(_ view: UIScrollView, context: Context) {
        let coordinator = context.coordinator
        coordinator.parent = self
        coordinator.updating = true
        defer { coordinator.updating = false }
        let size = CGSize(width: contentWidth, height: 0)
        if view.contentSize != size { view.contentSize = size }
        if let jump, jump.id != coordinator.lastJump {
            coordinator.lastJump = jump.id
            let maxX = max(0, contentWidth - view.bounds.width)
            let x = min(max(jump.x, 0), view.bounds.width > 0 ? maxX : jump.x)
            if abs(view.contentOffset.x - x) > 0.25 {
                view.setContentOffset(CGPoint(x: x, y: 0), animated: jump.animated)
            }
        }
    }

    final class Coordinator: NSObject, UIScrollViewDelegate {
        var parent: StripScrollOverlay
        var lastJump: Int?
        var updating = false

        init(_ parent: StripScrollOverlay) {
            self.parent = parent
        }

        func scrollViewDidScroll(_ scrollView: UIScrollView) {
            let x = scrollView.contentOffset.x
            if updating {
                // Not inside SwiftUI's update of this view.
                DispatchQueue.main.async { self.parent.onScroll(x) }
            } else {
                parent.onScroll(x)
            }
        }

        @objc func tapped(_ recognizer: UITapGestureRecognizer) {
            guard let view = recognizer.view as? UIScrollView else { return }
            let point = recognizer.location(in: view)
            // Point in the strip's frame (the scroll view's bounds move with the offset).
            parent.onTap(CGPoint(x: point.x - view.contentOffset.x, y: point.y - view.contentOffset.y))
        }

        @objc func pinched(_ recognizer: UIPinchGestureRecognizer) {
            guard let view = recognizer.view as? UIScrollView else { return }
            let focus = recognizer.location(in: view).x - view.contentOffset.x
            parent.onPinch(recognizer.state, recognizer.scale, focus)
        }
    }
}
