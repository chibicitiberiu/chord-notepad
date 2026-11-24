import ChordNotepadKit
import SwiftUI

// The player's sheets and the ribbon's Insert sheet, ported from Android's
// ui/sheets/ (PickerSheet.kt, PlayerSheets.kt, SongDefaultsSheet.kt). They are
// panels the screen draws over itself rather than system sheets, as Android's
// bottom sheets are part of its screen: a dialog (Manual…, the tempo) stacks
// over its sheet, and the preview catalog draws them as they are. Every tap
// goes to the kit's reducer as a ``SheetEvent``.

/// Android's `PickerSheet`: a panel from the bottom over a dimmed screen,
/// with a drag handle, a title row (`leading` before the title, `trailing`
/// after it), an optional subtitle, the body (scrolling live) and the actions
/// row under a divider. A tap on the dimmed screen or a swipe down dismisses.
struct BottomSheet<Content: View, Actions: View>: View {
    let title: String
    let colors: AppColors
    var subtitle: String?
    /// False in the catalog: no ScrollView and no gestures (ImageRenderer).
    var live = true
    var leading: AnyView?
    var trailing: AnyView?
    var dismiss: () -> Void = {}
    @ViewBuilder let content: () -> Content
    @ViewBuilder let actions: () -> Actions

    @State private var contentHeight: CGFloat = 0
    @State private var drag: CGFloat = 0

    /// What the catalog leaves the body: the window less the handle, the
    /// title, the subtitle, the actions and the margins.
    private var chrome: CGFloat { subtitle == nil ? 150 : 176 }

    var body: some View {
        GeometryReader { geometry in
            let room = max(geometry.size.height - 16, 160)
            ZStack(alignment: .bottom) {
                Color.black.opacity(0.32)
                    .ignoresSafeArea()
                    .onTapGesture { dismiss() }
                    .accessibilityLabel("Close")
                    .accessibilityAddTraits(.isButton)
                panel(room: room)
                    .offset(y: max(drag, 0))
            }
            .frame(width: geometry.size.width, height: geometry.size.height, alignment: .bottom)
        }
    }

    private func panel(room: CGFloat) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 0) {
                Capsule()
                    .fill(colors.grip.swiftUI)
                    .frame(width: 32, height: 4)
                    .frame(maxWidth: .infinity)
                    .padding(.top, 10)
                    .padding(.bottom, 8)
                HStack(spacing: 8) {
                    leading
                    Text(title)
                        .font(.callout.weight(.medium))
                        .foregroundColor(colors.text.swiftUI)
                        .accessibilityAddTraits(.isHeader)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    trailing
                }
                .padding(.top, 2)
                .padding(.bottom, 6)
                .frame(minHeight: 36)
                if let subtitle {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundColor(colors.muted.swiftUI)
                        .padding(.bottom, 6)
                }
            }
            .contentShape(Rectangle())
            .gesture(live ? swipeDown : nil)
            bodyArea(room: room)
            colors.line.swiftUI.frame(height: 1).padding(.top, 10)
            HStack(spacing: 8) { actions() }
                .padding(.top, 10)
        }
        .padding(.horizontal, 18)
        .padding(.bottom, 12)
        .frame(maxWidth: 640)
        .frame(maxHeight: room)
        .background(alignment: .top) {
            UnevenRoundedRectangle(topLeadingRadius: 18, topTrailingRadius: 18)
                .fill(colors.surfaceLow.swiftUI)
                .ignoresSafeArea(edges: .bottom)
        }
        // The rows follow the text size up to a point: the sheet keeps room for its rows.
        .dynamicTypeSize(...DynamicTypeSize.accessibility2)
    }

    @ViewBuilder
    private func bodyArea(room: CGFloat) -> some View {
        let rows = VStack(alignment: .leading, spacing: 0, content: content)
            .frame(maxWidth: .infinity, alignment: .leading)
        if live {
            ScrollView {
                rows.onGeometryChange(for: CGFloat.self, of: { $0.size.height }) { contentHeight = $0 }
            }
            .scrollBounceBehavior(.basedOnSize)
            .frame(maxHeight: contentHeight > 0 ? contentHeight : nil)
        } else {
            rows.fixedSize(horizontal: false, vertical: true)
                .frame(maxHeight: max(room - chrome, 60), alignment: .top)
                .clipped()
        }
    }

    private var swipeDown: some Gesture {
        DragGesture(minimumDistance: 8)
            .onChanged { drag = $0.translation.height }
            .onEnded { value in
                if value.translation.height > 80 { dismiss() }
                drag = 0
            }
    }
}

/// A row in a sheet (Android's `SheetRow`): `leading` icon, the label, `sub`
/// on the right, `trailing`.
struct SheetRow<Leading: View, Trailing: View>: View {
    let label: String
    let colors: AppColors
    var sub: String?
    var subMonospace = false
    /// A radio row says whether it's the chosen one.
    var selected: Bool?
    var identifier: String?
    let action: () -> Void
    @ViewBuilder var leading: () -> Leading
    @ViewBuilder var trailing: () -> Trailing

    var body: some View {
        Button(action: action) {
            HStack(spacing: 14) {
                leading()
                Text(label)
                    .font(.subheadline)
                    .foregroundColor(colors.text.swiftUI)
                    .frame(maxWidth: .infinity, alignment: .leading)
                if let sub {
                    Text(sub)
                        .font(subMonospace ? .caption.monospaced() : .caption)
                        .foregroundColor(colors.muted.swiftUI)
                }
                trailing()
            }
            .padding(.horizontal, 6)
            .frame(minHeight: 46)
            .contentShape(RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected == true ? [.isSelected, .isButton] : .isButton)
        .accessibilityIdentifier(identifier ?? "row-\(label)")
    }
}

extension SheetRow where Trailing == EmptyView {
    init(label: String, colors: AppColors, sub: String? = nil, subMonospace: Bool = false, selected: Bool? = nil,
         identifier: String? = nil, action: @escaping () -> Void, @ViewBuilder leading: @escaping () -> Leading) {
        self.init(label: label, colors: colors, sub: sub, subMonospace: subMonospace, selected: selected,
                  identifier: identifier, action: action, leading: leading, trailing: { EmptyView() })
    }
}

/// A small uppercase section heading (Android's `SheetSection`).
struct SheetSection: View {
    let text: String
    let colors: AppColors

    var body: some View {
        Text(text.uppercased())
            .font(.caption2.weight(.medium))
            .tracking(0.66)
            .foregroundColor(colors.muted.swiftUI)
            .padding(.top, 12)
            .padding(.bottom, 2)
            .padding(.leading, 6)
    }
}

/// A text button in the primary colour. Locked (`lockedReason`), it looks
/// disabled but still takes the tap, so the action can say why.
struct SheetTextButton<Leading: View>: View {
    let label: String
    let colors: AppColors
    var enabled = true
    var locked = false
    var identifier: String?
    let action: () -> Void
    @ViewBuilder var leading: () -> Leading

    var body: some View {
        let dim = !enabled || locked
        Button(action: action) {
            HStack(spacing: 6) {
                leading()
                Text(label)
                    .font(.subheadline.weight(.medium))
            }
            .foregroundColor(dim ? colors.text.swiftUI.opacity(AppColors.disabledAlpha) : colors.primary.swiftUI)
            .padding(.horizontal, 12)
            .frame(minHeight: 40)
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityIdentifier(identifier ?? "sheet-\(label)")
    }
}

extension SheetTextButton where Leading == EmptyView {
    init(label: String, colors: AppColors, enabled: Bool = true, locked: Bool = false, identifier: String? = nil,
         action: @escaping () -> Void) {
        self.init(label: label, colors: colors, enabled: enabled, locked: locked, identifier: identifier,
                  action: action, leading: { EmptyView() })
    }
}

/// The filled primary button that closes a sheet (Done).
struct SheetDoneButton: View {
    let colors: AppColors
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(sheetDone)
                .font(.subheadline.weight(.medium))
                .foregroundColor(colors.onPrimary.swiftUI)
                .padding(.horizontal, 24)
                .frame(minHeight: 40)
                .background(colors.primary.swiftUI, in: Capsule())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("sheet-done")
    }
}

/// A radio mark: filled in the primary colour when on, else a grey ring.
struct RadioMark: View {
    let on: Bool
    let colors: AppColors

    var body: some View {
        MdiIcon(on ? "mdi_radiobox_marked" : "mdi_radiobox_blank",
                tint: on ? colors.primary.swiftUI : IconTints.off.swiftUI)
            .accessibilityHidden(true)
    }
}

/// A dropdown's button: the value and ▾ in an outlined chip. Live, a menu of
/// the choices; in the catalog, the chip alone.
struct DropdownChip: View {
    let text: String
    let choices: [String]
    let colors: AppColors
    var live = true
    var locked = false
    var identifier: String?
    var choose: (String) -> Void = { _ in }
    /// A tap while locked.
    var lockedTap: () -> Void = {}

    var body: some View {
        if live && !locked {
            Menu {
                ForEach(choices, id: \.self) { choice in
                    Button(choice) { choose(choice) }
                }
            } label: { chip }
            .accessibilityIdentifier(identifier ?? "dropdown")
        } else {
            Button(action: lockedTap) { chip }
                .buttonStyle(.plain)
                .accessibilityIdentifier(identifier ?? "dropdown")
        }
    }

    private var chip: some View {
        Text("\(text) ▾")
            .font(.subheadline.weight(.medium))
            .foregroundColor(locked ? colors.muted.swiftUI.opacity(0.6) : colors.text.swiftUI)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(colors.line.swiftUI, lineWidth: 1))
            .contentShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - Voicing and Instrument

/// Voicing: Piano, Fretted, Ensembles and Your voicings with radio rows.
/// Choosing one applies it at once (the sheet stays, Done closes it). Edit
/// voicings… would open Settings › Voicings, which the iOS app hasn't got yet.
struct VoicingPickerSheet: View {
    let state: VoicingMenuState?
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        BottomSheet(title: VoicingSheetTexts.title, colors: colors, subtitle: VoicingSheetTexts.subtitle, live: live,
                    dismiss: { event(.dismiss) }) {
            if let state {
                ForEach(voicingGroups(state), id: \.kind) { group in
                    SheetSection(text: group.kind.title, colors: colors)
                    ForEach(group.choices, id: \.value) { choice in
                        SheetRow(label: choice.label, colors: colors, selected: choice.selected,
                                 identifier: "voicing-\(choice.value)",
                                 action: { event(.chooseVoicing(choice.value)) }) {
                            RadioMark(on: choice.selected, colors: colors)
                        }
                    }
                }
            }
        } actions: {
            SheetTextButton(label: VoicingSheetTexts.edit, colors: colors,
                            action: { event(.editVoicings) }) {
                MdiIcon("mdi_pencil", tint: colors.primary.swiftUI, size: 18)
            }
            Spacer(minLength: 0)
            SheetDoneButton(colors: colors) { event(.done) }
        }
        .accessibilityIdentifier("voicing-sheet")
    }
}

/// Instrument, two levels: the 16 General MIDI families (a dot on the
/// current one, its instrument on the right), then a family's 8 programs
/// with their numbers; ← goes back to the families, Done closes.
struct InstrumentPickerSheet: View {
    let state: InstrumentMenuState?
    /// The open family's index, or nil for the families.
    let family: Int?
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        let families = state.map(instrumentFamilies) ?? []
        let open = family.flatMap { families.indices.contains($0) ? families[$0] : nil }
        BottomSheet(title: open?.name ?? InstrumentSheetTexts.title, colors: colors, live: live,
                    leading: open == nil ? nil : AnyView(backButton), dismiss: { event(.dismiss) }) {
            if let open {
                ForEach(open.programs, id: \.program) { program in
                    let parts = programParts(program)
                    SheetRow(label: parts.name, colors: colors, sub: parts.number, selected: program.selected,
                             identifier: "program-\(program.program)",
                             action: { event(.chooseInstrument(program.program)) }) {
                        RadioMark(on: program.selected, colors: colors)
                    }
                }
            } else {
                ForEach(Array(families.enumerated()), id: \.offset) { pair in
                    let f = pair.element
                    SheetRow(label: f.name, colors: colors,
                             sub: f.isCurrent ? f.programs.first(where: \.selected).map { programParts($0).name } : nil,
                             identifier: "family-\(pair.offset)",
                             action: { event(.openFamily(pair.offset)) }) {
                        MdiIcon(f.isCurrent ? "mdi_circle" : "mdi_circle_outline",
                                tint: (f.isCurrent ? colors.primary : colors.grip).swiftUI, size: 12)
                            .frame(width: 24, height: 24)
                    } trailing: {
                        MdiIcon("mdi_chevron_right", tint: IconTints.off.swiftUI, size: 20)
                    }
                }
            }
        } actions: {
            Spacer(minLength: 0)
            SheetDoneButton(colors: colors) { event(.done) }
        }
        .accessibilityIdentifier("instrument-sheet")
    }

    private var backButton: some View {
        Button { event(.back) } label: {
            MdiIcon("mdi_arrow_left", tint: colors.text.swiftUI, size: 22)
                .frame(width: 36, height: 36)
                .contentShape(Circle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(InstrumentSheetTexts.back)
    }
}

// MARK: - Speed

/// Playback speed: the value in large type, a 12.5–400 % slider (5 % steps;
/// the session gets each new value), then Reset, Manual… and Done.
struct SpeedSheet: View {
    /// The session's speed.
    let pct: Double
    let slider: SpeedSlider
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        let shown = slider.shown(pct)
        BottomSheet(title: SpeedTexts.title, colors: colors, live: live,
                    trailing: AnyView(Text("\(speedPctText(shown))%")
                        .font(.title3.weight(.medium))
                        .foregroundColor(colors.primary.swiftUI)
                        .accessibilityIdentifier("speed-value")),
                    dismiss: { event(.dismiss) }) {
            SpeedTrack(fraction: speedFraction(shown), colors: colors, live: live,
                       value: "\(speedPctText(shown))%",
                       moved: { event(.speedDragged(speedAt(fraction: $0))) },
                       step: { up in event(.speedDragged(shown + (up ? speedStepPct : -speedStepPct))) })
                .padding(.top, 10)
            HStack {
                Text("\(speedPctText(speedMinPct))%")
                Spacer()
                Text("\(speedPctText(speedMaxPct))%")
            }
            .font(.caption2)
            .foregroundColor(colors.muted.swiftUI)
        } actions: {
            SheetTextButton(label: SpeedTexts.reset, colors: colors) { event(.speedReset) }
            SheetTextButton(label: SpeedTexts.manual, colors: colors) { event(.speedManual) }
            Spacer(minLength: 0)
            SheetDoneButton(colors: colors) { event(.done) }
        }
        .accessibilityIdentifier("speed-sheet")
    }
}

/// The speed slider, drawn as Android's Material slider (a thick track, the
/// active part up to a bar-shaped thumb, a stop dot at the end), so the
/// catalog draws it too; VoiceOver adjusts it in 5 % steps.
struct SpeedTrack: View {
    /// Where the thumb is, 0…1.
    let fraction: Double
    let colors: AppColors
    var live = true
    let value: String
    var moved: (Double) -> Void = { _ in }
    var step: (Bool) -> Void = { _ in }

    var body: some View {
        GeometryReader { geometry in
            let width = geometry.size.width
            let x = CGFloat(fraction) * width
            ZStack(alignment: .leading) {
                Capsule()
                    .fill(colors.primary.swiftUI)
                    .frame(width: max(x - 6, 0), height: 16)
                Capsule()
                    .fill(colors.primarySoft.swiftUI)
                    .frame(width: max(width - x - 6, 0), height: 16)
                    .offset(x: min(x + 6, width))
                Circle()
                    .fill(colors.primary.swiftUI)
                    .frame(width: 4, height: 4)
                    .offset(x: width - 10)
                    .opacity(fraction < 0.99 ? 1 : 0)
                Capsule()
                    .fill(colors.primary.swiftUI)
                    .frame(width: 4, height: 44)
                    .offset(x: x - 2)
            }
            .frame(height: 44)
            .contentShape(Rectangle())
            .gesture(live ? DragGesture(minimumDistance: 0).onChanged { drag in
                moved(Double(min(max(drag.location.x / max(width, 1), 0), 1)))
            } : nil)
        }
        .frame(height: 44)
        .accessibilityElement()
        .accessibilityLabel(SpeedTexts.title)
        .accessibilityValue(value)
        .accessibilityAdjustableAction { direction in
            switch direction {
            case .increment: step(true)
            case .decrement: step(false)
            @unknown default: break
            }
        }
        .accessibilityIdentifier("speed-slider")
    }
}

// MARK: - Playback settings

/// Playback settings (the player's song pill): Tempo, Time signature and
/// Key, each with a line saying what it does. A value set by a directive is
/// read only with "Set by `{bpm: 90}` in the song · Edit"; the others are
/// this song's values (not saved with the file, as the note at the bottom
/// says). Write into song inserts the missing directives at the top. While a
/// song plays the values and Write into song are greyed, and a tap says why.
struct SongDefaultsSheet: View {
    let state: SongDefaultsState
    let keys: [String]
    let colors: AppColors
    let directive: Color
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        let locked = state.lockedReason != nil
        BottomSheet(title: SongDefaultsTexts.title, colors: colors, live: live, dismiss: { event(.dismiss) }) {
            ForEach(songDefaultRows(state, keys: keys), id: \.kind) { row in
                defaultRow(row, locked: locked)
            }
            if state.anythingToWrite {
                Text(SongDefaultsTexts.unsaved)
                    .font(.caption)
                    .foregroundColor(colors.muted.swiftUI)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 10)
            }
        } actions: {
            SheetTextButton(label: SongDefaultsTexts.write, colors: colors, enabled: state.anythingToWrite,
                            locked: locked, identifier: "song-defaults-write") { event(.writeIntoSong) }
            Spacer(minLength: 0)
            SheetDoneButton(colors: colors) { event(.done) }
        }
        .accessibilityIdentifier("song-defaults-sheet")
    }

    @ViewBuilder
    private func defaultRow(_ row: SongDefaultRow, locked: Bool) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 12) {
                MdiIcon(row.icon, tint: IconTints.of(row.kind).swiftUI)
                VStack(alignment: .leading, spacing: 1) {
                    Text(row.label)
                        .font(.subheadline)
                        .foregroundColor(colors.text.swiftUI)
                    Text(row.about)
                        .font(.caption2)
                        .foregroundColor(colors.muted.swiftUI)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                if row.fromDirective {
                    Text(row.display)
                        .font(.subheadline.weight(.medium))
                        .foregroundColor(colors.muted.swiftUI)
                } else if row.kind == .tempo {
                    DropdownChip(text: row.display, choices: [], colors: colors, live: false, locked: locked,
                                 identifier: "song-defaults-tempo", lockedTap: { event(.tempoOpen) })
                } else {
                    DropdownChip(text: row.display, choices: row.choices, colors: colors, live: live, locked: locked,
                                 identifier: "song-defaults-\(row.kind.rawValue)",
                                 choose: { event(.chooseDefault(row, $0)) }, lockedTap: { event(.locked) })
                }
            }
            .padding(.vertical, 6)
            .frame(minHeight: 52)
            if row.fromDirective { setBy(row) }
            colors.line.swiftUI.frame(height: 1)
        }
    }

    /// "Set by `{bpm: 90}` in the song · Edit", under a row a directive sets.
    private func setBy(_ row: SongDefaultRow) -> some View {
        var text = AttributedString("\(SongDefaultsTexts.setBy) ")
        var code = AttributedString(row.code)
        code.foregroundColor = directive
        code.font = .caption2.monospaced()
        text += code
        text += AttributedString(" \(SongDefaultsTexts.inSong)")
        if let offset = row.directiveOffset {
            text += AttributedString(" · ")
            var edit = AttributedString(SongDefaultsTexts.edit)
            edit.foregroundColor = colors.primary.swiftUI
            edit.font = .caption2.weight(.medium)
            edit.link = URL(string: "chordnotepad-edit:\(offset)")
            text += edit
        }
        return Text(text)
            .font(.caption2)
            .foregroundColor(colors.muted.swiftUI)
            .tint(colors.primary.swiftUI)
            .padding(.leading, 36)
            .padding(.bottom, 8)
            .environment(\.openURL, OpenURLAction { url in
                if let offset = Int(url.absoluteString.replacingOccurrences(of: "chordnotepad-edit:", with: "")) {
                    event(.editDirective(offset))
                }
                return .handled
            })
            .accessibilityIdentifier("song-defaults-set-by-\(row.kind.rawValue)")
    }
}

// MARK: - Insert

/// ＋ Insert: Tempo, Time signature, Key, Capo, Label and Loop, each showing its directive.
struct InsertSheet: View {
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        BottomSheet(title: InsertTexts.title, colors: colors, live: live, dismiss: { event(.dismiss) }) {
            ForEach(insertEntries, id: \.self) { entry in
                SheetRow(label: entry.label, colors: colors, sub: entry.code, subMonospace: true,
                         identifier: "insert-\(entry.kind.wire)", action: { event(.insert(entry.kind)) }) {
                    MdiIcon(entry.icon, tint: IconTints.of(entry.kind).swiftUI)
                }
            }
        } actions: {
            Spacer(minLength: 0)
            SheetTextButton(label: InsertTexts.cancel, colors: colors) { event(.dismiss) }
        }
        .accessibilityIdentifier("insert-sheet")
    }
}

/// The old sheet frame, for Examples (a system sheet with Done in its header).
struct PlayerSheet<Content: View>: View {
    let title: String
    let colors: AppColors
    /// False in the catalog (no ScrollView).
    var scrolls = true
    var done: () -> Void = {}
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(title)
                    .font(.headline)
                    .foregroundColor(colors.text.swiftUI)
                Spacer(minLength: 8)
                DialogButton(label: "Done", colors: colors, action: done)
            }
            .padding(.leading, 20)
            .padding(.trailing, 8)
            .padding(.vertical, 8)
            colors.line.swiftUI.frame(height: 1)
            if scrolls {
                ScrollView { rows }
            } else {
                rows.frame(maxHeight: .infinity, alignment: .top).clipped()
            }
        }
        .background(colors.surfaceLow.swiftUI)
    }

    private var rows: some View {
        VStack(alignment: .leading, spacing: 0, content: content)
            .padding(.vertical, 8)
            .frame(maxWidth: .infinity, alignment: .leading)
    }
}
