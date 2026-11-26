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

    /// An iOS sheet (the main screen presents it; on an iPad a form sheet,
    /// Android's dialog): Close and Insert in its navigation bar, the piano
    /// and the typed notes beside the candidates when the sheet is wider than
    /// tall (a phone on its side), else above them.
    var body: some View {
        NavigationStack {
            GeometryReader { geometry in
                let layout = identifierLayout(width: Double(geometry.size.width), height: Double(geometry.size.height))
                screen(sideBySide: layout == .sideBySide)
                    .frame(width: geometry.size.width, height: geometry.size.height)
            }
            .background(colors.groupedBackground.ignoresSafeArea())
            .navigationTitle(IdentifierTexts.title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(IdentifierTexts.close) { event(.dismiss) }
                        .accessibilityIdentifier("identifier-close")
                }
                ToolbarItem(placement: .confirmationAction) {
                    // Inserts the picked chord and closes the identifier (SheetController).
                    Button(IdentifierTexts.insert) { event(.identifierInsert(nil)) }
                        .fontWeight(.semibold)
                        .disabled(model.picked == nil)
                        .accessibilityIdentifier("identifier-insert")
                }
            }
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
            // The session's status line, so "Inserted chord: C" is seen while the editor is covered.
            colors.separator.frame(height: 0.5)
            Text(status ?? "")
                .font(.footnote)
                .foregroundColor(colors.secondaryLabel)
                .lineLimit(2)
                .frame(maxWidth: .infinity, minHeight: 20, alignment: .leading)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(colors.bar)
                .accessibilityIdentifier("identifier-status")
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

    /// The hint, the piano and the sounding notes it doesn't reach.
    private var input: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(IdentifierTexts.hint(notation: state?.notation))
                .font(.subheadline)
                .foregroundColor(colors.secondaryLabel)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 8)
            PianoView(selected: Set(state?.notes.map(\.midi) ?? []), sounding: sounding,
                      notation: state?.notation ?? "american", outline: colors.secondaryLabel, live: live,
                      tap: { event(.identifierTap($0)) }, press: { event(.identifierPress($0)) })
                .frame(height: 132)
                .padding(.top, 12)
            HStack {
                Text(sounding.isEmpty ? "" : state?.soundingBelow ?? "")
                Spacer()
                Text(sounding.isEmpty ? "" : state?.soundingAbove ?? "")
            }
            .font(.caption2)
            .foregroundColor(colors.secondaryLabel)
            .frame(minHeight: 16)
        }
    }

    /// The typed notes (a plain rounded field, its name as the placeholder),
    /// Clear and Play.
    private var notesRow: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(spacing: 8) {
                TextField(IdentifierTexts.notes, text: Binding(get: { model.typed },
                                                              set: { event(.identifierType($0)) }))
                    .textFieldStyle(.roundedBorder)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.done)
                    .foregroundColor(state?.typedTextError != nil ? colors.red : nil)
                    .accessibilityLabel(IdentifierTexts.notes)
                    .accessibilityIdentifier("identifier-notes")
                Button(IdentifierTexts.clear) { event(.identifierClear) }
                    .buttonStyle(.bordered)
                    .accessibilityIdentifier("identifier-clear")
                let canPlay = !(state?.notes.isEmpty ?? true)
                // Not a Button: a long press plays the keys rolled instead of as they are.
                // Drawn as the system's bordered button.
                Text(IdentifierTexts.play)
                    .foregroundStyle(canPlay ? AnyShapeStyle(TintShapeStyle())
                                     : AnyShapeStyle(HierarchicalShapeStyle.tertiary))
                    .padding(.horizontal, 12)
                    .padding(.vertical, 7)
                    .background(canPlay ? AnyShapeStyle(Color.accentColor.opacity(0.15))
                                : AnyShapeStyle(Color(uiColor: .tertiarySystemFill)),
                                in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                    .contentShape(Rectangle())
                    .onTapGesture { if canPlay { event(.identifierPlay(rolled: false)) } }
                    .onLongPressGesture(minimumDuration: 0.5) { if canPlay { event(.identifierPlay(rolled: true)) } }
                    .accessibilityAddTraits(.isButton)
                    .accessibilityAction { if canPlay { event(.identifierPlay(rolled: false)) } }
                    .accessibilityAction(named: IdentifierTexts.playRolled) { event(.identifierPlay(rolled: true)) }
                    .accessibilityIdentifier("identifier-play")
            }
            if let error = state?.typedTextError {
                Text(error)
                    .font(.footnote)
                    .foregroundColor(colors.red)
            }
        }
        .padding(.top, 8)
    }

    /// The candidates (a tap picks and plays, a long press plays rolled;
    /// Insert inserts the picked one), or the session's message when there are none.
    @ViewBuilder
    private var candidates: some View {
        Text(IdentifierTexts.candidates.uppercased())
            .font(.footnote)
            .foregroundColor(colors.secondaryLabel)
            .padding(.top, 12)
            .padding(.bottom, 4)
            .accessibilityAddTraits(.isHeader)
        let list = shownCandidates(state)
        if list.isEmpty {
            Text(state?.typedTextError != nil ? "" : state?.message ?? "")
                .font(.subheadline)
                .foregroundColor(colors.secondaryLabel)
                .padding(.vertical, 12)
                .frame(maxWidth: .infinity, alignment: .leading)
        } else {
            scrolling {
                VStack(spacing: 0) {
                    ForEach(Array(list.enumerated()), id: \.element) { index, chord in
                        if index > 0 { colors.separator.frame(height: 0.5).padding(.leading, 16) }
                        candidate(chord)
                    }
                }
                .background(colors.cell, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            }
        }
    }

    private func candidate(_ chord: String) -> some View {
        let selected = chord == model.picked
        return HStack {
            Text(chord)
                .font(.body)
                .foregroundColor(colors.label)
                .frame(maxWidth: .infinity, alignment: .leading)
            Image(systemName: AppSymbols.checkmark)
                .font(.body.weight(.semibold))
                .foregroundStyle(.tint)
                .opacity(selected ? 1 : 0)
                .accessibilityHidden(true)
        }
            .padding(.horizontal, 16)
            .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
            .contentShape(Rectangle())
            .accessibilityElement(children: .combine)
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
