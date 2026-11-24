import ChordNotepadKit
import SwiftUI

// The chord identifier (Android's ui/identifier/ChordIdentifierScreen.kt):
// full screen on a phone, a card on an iPad (the kit's `identifierLayout`).
// Everything it shows comes from the session's IdentifierState and the
// kit's IdentifierModel; the session's status line is repeated at the
// bottom, so "Inserted chord: C" is seen while the editor is covered.

/// The desktop's selected-key blue and sounding amber (ui/chord_identifier.py);
/// the keys are white and black in either theme, so these read in both.
private enum KeyColors {
    static let selected = Color(.sRGB, red: 0x4A / 255, green: 0x90 / 255, blue: 0xE2 / 255)
    static let sounding = Color(.sRGB, red: 0xF5 / 255, green: 0xA6 / 255, blue: 0x23 / 255)
    static let soundingOutline = Color(.sRGB, red: 0x9A / 255, green: 0x62 / 255, blue: 0x00 / 255)
}

struct ChordIdentifierView: View {
    let state: IdentifierState?
    let model: IdentifierModel
    /// The sounding token whose time ran out.
    let expired: Int
    let status: String?
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        GeometryReader { geometry in
            let layout = identifierLayout(width: Double(geometry.size.width), height: Double(geometry.size.height))
            ZStack {
                if layout == .dialog {
                    Color.black.opacity(0.32).ignoresSafeArea()
                    screen(sideBySide: false)
                        .frame(maxWidth: 640, maxHeight: 720)
                        .background(colors.surface.swiftUI, in: RoundedRectangle(cornerRadius: 28))
                        .clipShape(RoundedRectangle(cornerRadius: 28))
                        .padding(24)
                } else {
                    colors.surface.swiftUI.ignoresSafeArea()
                    screen(sideBySide: layout == .sideBySide)
                }
            }
            .frame(width: geometry.size.width, height: geometry.size.height)
        }
        .task(id: state?.soundingToken ?? 0) {
            // What played last stays lit for sounding_seconds; a new play restarts the wait.
            guard live, let state, state.soundingToken != expired else { return }
            try? await Task.sleep(for: .seconds(state.soundingSeconds))
            if !Task.isCancelled { event(.identifierExpired(state.soundingToken)) }
        }
        .dynamicTypeSize(...DynamicTypeSize.accessibility1)
        .accessibilityIdentifier("identifier")
    }

    private var sounding: Set<Int> { shownSounding(state, expiredToken: expired) }

    private func screen(sideBySide: Bool) -> some View {
        VStack(spacing: 0) {
            topBar
            if sideBySide {
                HStack(alignment: .top, spacing: 24) {
                    scrolling { input }
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                    VStack(alignment: .leading, spacing: 4) {
                        notesRow
                        candidates
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                }
                .padding(.horizontal, 16)
            } else {
                VStack(alignment: .leading, spacing: 0) {
                    input
                    notesRow
                    candidates.padding(.top, 8)
                }
                .padding(.horizontal, 16)
                .frame(maxHeight: .infinity, alignment: .top)
            }
            colors.line.swiftUI.frame(height: 1)
            HStack(spacing: 12) {
                Text(status ?? "")
                    .font(.footnote)
                    .foregroundColor(colors.text.swiftUI)
                    .lineLimit(2)
                    .frame(maxWidth: .infinity, alignment: .leading)
                Button { event(.identifierInsert(nil)) } label: {
                    Text(IdentifierTexts.insert)
                        .font(.subheadline.weight(.medium))
                        .foregroundColor(colors.onPrimary.swiftUI)
                        .padding(.horizontal, 24)
                        .frame(minHeight: 40)
                        .background(colors.primary.swiftUI.opacity(model.picked == nil ? AppColors.disabledAlpha : 1),
                                    in: Capsule())
                }
                .buttonStyle(.plain)
                .disabled(model.picked == nil)
                .accessibilityIdentifier("identifier-insert")
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
        }
    }

    @ViewBuilder
    private func scrolling<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        if live {
            ScrollView { VStack(alignment: .leading, spacing: 0, content: content) }
        } else {
            VStack(alignment: .leading, spacing: 0, content: content)
        }
    }

    private var topBar: some View {
        HStack(spacing: 8) {
            Button { event(.dismiss) } label: {
                MdiIcon("mdi_arrow_left", tint: colors.text.swiftUI)
                    .frame(width: 48, height: 48)
                    .contentShape(Circle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(IdentifierTexts.close)
            .accessibilityIdentifier("identifier-close")
            Text(IdentifierTexts.title)
                .font(.title2)
                .foregroundColor(colors.text.swiftUI)
                .accessibilityAddTraits(.isHeader)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 4)
        .frame(height: 64)
    }

    /// The hint, the piano and the sounding notes it doesn't reach.
    private var input: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(IdentifierTexts.hint(notation: state?.notation))
                .font(.subheadline)
                .foregroundColor(colors.text.swiftUI)
                .fixedSize(horizontal: false, vertical: true)
            PianoView(selected: Set(state?.notes.map(\.midi) ?? []), sounding: sounding,
                      notation: state?.notation ?? "american", outline: colors.muted.swiftUI, live: live,
                      tap: { event(.identifierTap($0)) }, press: { event(.identifierPress($0)) })
                .frame(height: 132)
                .padding(.top, 12)
            HStack {
                Text(sounding.isEmpty ? "" : state?.soundingBelow ?? "")
                Spacer()
                Text(sounding.isEmpty ? "" : state?.soundingAbove ?? "")
            }
            .font(.caption2)
            .foregroundColor(colors.muted.swiftUI)
            .frame(minHeight: 16)
        }
    }

    /// The typed notes, Clear and Play.
    private var notesRow: some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: 8) {
                OutlinedField(label: IdentifierTexts.notes, text: model.typed, colors: colors, live: live,
                              error: state?.typedTextError != nil, autofocus: false, identifier: "identifier-notes",
                              change: { event(.identifierType($0)) })
                pill(IdentifierTexts.clear, enabled: true, outline: colors.line.swiftUI.opacity(0.6),
                     text: colors.muted.swiftUI, id: "identifier-clear") { event(.identifierClear) }
                let canPlay = !(state?.notes.isEmpty ?? true)
                // Not a Button: a long press plays the keys rolled instead of as they are.
                pillLabel(IdentifierTexts.play, enabled: canPlay, outline: colors.muted.swiftUI,
                          text: colors.primary.swiftUI)
                    .onTapGesture { if canPlay { event(.identifierPlay(rolled: false)) } }
                    .onLongPressGesture(minimumDuration: 0.5) { if canPlay { event(.identifierPlay(rolled: true)) } }
                    .accessibilityAddTraits(.isButton)
                    .accessibilityAction { if canPlay { event(.identifierPlay(rolled: false)) } }
                    .accessibilityAction(named: IdentifierTexts.playRolled) { event(.identifierPlay(rolled: true)) }
                    .accessibilityIdentifier("identifier-play")
            }
            if let error = state?.typedTextError {
                Text(error)
                    .font(.caption)
                    .foregroundColor(colors.error.swiftUI)
                    .padding(.leading, 16)
            }
        }
        .padding(.top, 4)
    }

    private func pill(_ label: String, enabled: Bool, outline: Color, text: Color, id: String,
                      action: @escaping () -> Void) -> some View {
        Button(action: action) {
            pillLabel(label, enabled: enabled, outline: outline, text: text)
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityIdentifier(id)
    }

    private func pillLabel(_ label: String, enabled: Bool, outline: Color, text: Color) -> some View {
        Text(label)
            .font(.subheadline.weight(.medium))
            .foregroundColor(enabled ? text : colors.text.swiftUI.opacity(AppColors.disabledAlpha))
            .padding(.horizontal, 22)
            .frame(minHeight: 44)
            .overlay(Capsule().stroke(enabled ? outline : colors.line.swiftUI.opacity(0.5), lineWidth: 1))
            .contentShape(Capsule())
            .padding(.top, 6)
    }

    /// The candidates (tap plays, long press plays rolled, double tap
    /// inserts), or the session's message when there are none.
    @ViewBuilder
    private var candidates: some View {
        Text(IdentifierTexts.candidates)
            .font(.subheadline.weight(.medium))
            .foregroundColor(colors.text.swiftUI)
            .padding(.top, 4)
        let list = shownCandidates(state)
        if list.isEmpty {
            Text(state?.typedTextError != nil ? "" : state?.message ?? "")
                .font(.subheadline)
                .foregroundColor(colors.muted.swiftUI)
                .padding(.vertical, 12)
                .frame(maxWidth: .infinity, alignment: .leading)
        } else {
            scrolling {
                ForEach(list, id: \.self) { chord in
                    candidate(chord)
                }
            }
        }
    }

    private func candidate(_ chord: String) -> some View {
        let selected = chord == model.picked
        return Text(chord)
            .font(.body)
            .foregroundColor(colors.text.swiftUI)
            .padding(.horizontal, 12)
            .frame(maxWidth: .infinity, minHeight: 48, alignment: .leading)
            .background(selected ? colors.primarySoft.swiftUI : .clear)
            .contentShape(Rectangle())
            .onTapGesture(count: 2) { event(.identifierInsert(chord)) }
            .onTapGesture { event(.identifierPick(chord, rolled: false)) }
            .onLongPressGesture(minimumDuration: 0.5) { event(.identifierPick(chord, rolled: true)) }
            .accessibilityAddTraits(selected ? [.isSelected, .isButton] : .isButton)
            .accessibilityAction(named: IdentifierTexts.playRolled) { event(.identifierPick(chord, rolled: true)) }
            .accessibilityAction(named: IdentifierTexts.insert) { event(.identifierInsert(chord)) }
            .accessibilityIdentifier("candidate-\(chord)")
    }
}

/// The two-octave piano: a tap toggles a key, a long press sounds it.
/// Selected keys are blue; what played last amber, or an amber dot on a
/// selected key. Keys are labelled in the song's notation.
struct PianoView: View {
    let selected: Set<Int>
    let sounding: Set<Int>
    let notation: String
    let outline: Color
    var live = true
    var tap: (PianoKey) -> Void = { _ in }
    var press: (PianoKey) -> Void = { _ in }

    private let piano = PianoKeyboard()
    @State private var touch: (start: CGPoint, key: PianoKey, pressed: Bool, task: Task<Void, Never>?)?

    var body: some View {
        GeometryReader { geometry in
            Canvas { context, size in
                draw(&context, size)
            }
            .contentShape(Rectangle())
            .gesture(live ? DragGesture(minimumDistance: 0).onChanged { drag in
                began(drag.location, in: geometry.size)
            }.onEnded { drag in
                ended(drag.location)
            } : nil)
        }
        .accessibilityElement()
        .accessibilityLabel(IdentifierTexts.keyboard)
        .accessibilityValue(selected.sorted().compactMap { midi in
            piano.keys.first { $0.midi == midi }.map { "\(PianoKeyboard.label($0, notation: notation))\($0.octave)" }
        }.joined(separator: ", "))
        .accessibilityIdentifier("identifier-piano")
    }

    private func began(_ point: CGPoint, in size: CGSize) {
        guard touch == nil,
              let key = piano.keyAt(x: Double(point.x), y: Double(point.y), width: Double(size.width),
                                    height: Double(size.height)) else { return }
        let task = Task { @MainActor in
            try? await Task.sleep(for: .milliseconds(500))
            guard !Task.isCancelled, let current = touch, current.key == key, !current.pressed else { return }
            touch?.pressed = true
            press(key)
        }
        touch = (point, key, false, task)
    }

    private func ended(_ point: CGPoint) {
        guard let current = touch else { return }
        current.task?.cancel()
        touch = nil
        let moved = hypot(point.x - current.start.x, point.y - current.start.y) > 12
        if !current.pressed && !moved { tap(current.key) }
    }

    private func draw(_ context: inout GraphicsContext, _ size: CGSize) {
        let unit = size.width / CGFloat(piano.whiteKeyCount)
        for key in piano.keys {
            let look = KeyLook.of(selected: selected.contains(key.midi), sounding: sounding.contains(key.midi))
            let height = key.isBlack ? size.height * CGFloat(PianoKeyboard.blackHeight) : size.height
            let rect = CGRect(x: CGFloat(key.left) * unit, y: 0, width: CGFloat(key.width) * unit, height: height)
            let shape = Path(roundedRect: rect, cornerRadius: 3)
            let fill: Color
            switch look {
            case .selected, .selectedAndSounding: fill = KeyColors.selected
            case .sounding: fill = KeyColors.sounding
            case .plain: fill = key.isBlack ? .black : .white
            }
            context.fill(shape, with: .color(fill))
            context.stroke(shape, with: .color(key.isBlack ? .black : outline), lineWidth: 1)
            let labelColor: Color
            switch look {
            case .sounding: labelColor = .black
            case .plain: labelColor = key.isBlack ? .white : .black
            default: labelColor = .white
            }
            let label = context.resolve(Text(PianoKeyboard.label(key, notation: notation))
                .font(.system(size: key.isBlack ? 8 : 10))
                .foregroundColor(labelColor))
            let labelSize = label.measure(in: rect.size)
            if labelSize.width <= rect.width {
                context.draw(label, at: CGPoint(x: rect.midX, y: rect.maxY - 4 - labelSize.height / 2))
            }
            if look == .selectedAndSounding {
                let r = min(rect.width * 0.22, 5)
                let center = CGPoint(x: rect.midX, y: rect.maxY - labelSize.height - 4 - r - 3)
                let dot = Path(ellipseIn: CGRect(x: center.x - r, y: center.y - r, width: 2 * r, height: 2 * r))
                context.fill(dot, with: .color(KeyColors.sounding))
                context.stroke(dot, with: .color(KeyColors.soundingOutline), lineWidth: 1)
            }
        }
    }
}
