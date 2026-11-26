import ChordNotepadKit
import SwiftUI

// The player's sheets and the ribbon's Insert sheet, ported from Android's
// ui/sheets/ (PickerSheet.kt, PlayerSheets.kt, SongDefaultsSheet.kt) and
// drawn as iOS sheets: a navigation bar with the title, Cancel or Done, an
// inset grouped list. The main screen presents them (`MainScreen`'s
// `.sheet(item:)`); the preview catalog draws the same views in a sheet's
// frame (`CatalogSheetFrame`), since it can't present. Every tap goes to the
// kit's reducer as a ``SheetEvent``.

/// A button in a sheet's navigation bar.
struct BarButton {
    let title: String
    var enabled = true
    var identifier: String?
    let action: () -> Void
}

/// A sheet's navigation stack: the title inline, Cancel (`cancel`) on the
/// leading side and the confirming button (Done, OK, Insert) bold on the
/// trailing side.
struct SheetScaffold<Content: View>: View {
    let title: String
    var cancel: BarButton?
    var confirm: BarButton?
    @ViewBuilder let content: () -> Content

    var body: some View {
        NavigationStack {
            content()
                .sheetBar(title: title, cancel: cancel, confirm: confirm)
        }
    }
}

extension View {
    /// The sheet's title and bar buttons on a view in a navigation stack.
    func sheetBar(title: String, cancel: BarButton?, confirm: BarButton?) -> some View {
        navigationTitle(title)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if let cancel {
                    ToolbarItem(placement: .cancellationAction) {
                        Button(cancel.title, action: cancel.action)
                            .disabled(!cancel.enabled)
                            .modifier(AlertIdentifier(id: cancel.identifier))
                    }
                }
                if let confirm {
                    ToolbarItem(placement: .confirmationAction) {
                        Button(confirm.title, action: confirm.action)
                            .fontWeight(.semibold)
                            .disabled(!confirm.enabled)
                            .modifier(AlertIdentifier(id: confirm.identifier))
                    }
                }
            }
    }
}

/// How tall a sheet opens.
enum SheetHeight {
    /// Half the window, draggable to full (the system's medium and large).
    case medium
    /// Nearly the whole window.
    case large

    var detents: Set<PresentationDetent> {
        switch self {
        case .medium: return [.medium, .large]
        case .large: return [.large]
        }
    }
}

/// The catalog's picture of a presented sheet: the screen dimmed, the sheet
/// from the bottom at its height with rounded top corners (a centred card
/// in a regular-width window, as an iPad presents a form sheet).
struct CatalogSheetFrame<Content: View>: View {
    var height = SheetHeight.medium
    @ViewBuilder let content: () -> Content

    @Environment(\.horizontalSizeClass) private var sizeClass

    var body: some View {
        GeometryReader { window in
            let size = window.size
            ZStack(alignment: sizeClass == .regular ? .center : .bottom) {
                Color.black.opacity(0.25)
                if sizeClass == .regular {
                    content()
                        .frame(width: min(540, size.width - 40), height: min(620, size.height - 80))
                        .background(Color(uiColor: .systemGroupedBackground))
                        .clipShape(RoundedRectangle(cornerRadius: glassAlerts ? 30 : 12, style: .continuous))
                } else {
                    content()
                        .frame(width: glassAlerts ? size.width - 16 : size.width,
                               height: height == .medium ? size.height * 0.52 : size.height - 44)
                        .background(Color(uiColor: .systemGroupedBackground))
                        .clipShape(UnevenRoundedRectangle(topLeadingRadius: glassAlerts ? 30 : 12,
                                                          bottomLeadingRadius: glassAlerts ? 30 : 0,
                                                          bottomTrailingRadius: glassAlerts ? 30 : 0,
                                                          topTrailingRadius: glassAlerts ? 30 : 12,
                                                          style: .continuous))
                        .padding(.bottom, glassAlerts ? 8 : 0)
                }
            }
            .frame(width: size.width, height: size.height)
        }
    }
}

/// A row that chooses: the label, a value on the right, a checkmark when chosen.
struct ChoiceRow: View {
    let label: String
    var detail: String?
    var detailMonospaced = false
    let selected: Bool
    var identifier: String?
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Text(label)
                    .foregroundColor(Color(uiColor: .label))
                    .frame(maxWidth: .infinity, alignment: .leading)
                if let detail {
                    Text(detail)
                        .font(detailMonospaced ? .body.monospacedDigit() : .body)
                        .foregroundColor(Color(uiColor: .secondaryLabel))
                }
                Image(systemName: AppSymbols.checkmark)
                    .font(.body.weight(.semibold))
                    .foregroundStyle(.tint)
                    .opacity(selected ? 1 : 0)
                    .accessibilityHidden(true)
            }
            .contentShape(Rectangle())
        }
        .accessibilityAddTraits(selected ? [.isSelected, .isButton] : .isButton)
        .modifier(AlertIdentifier(id: identifier ?? "row-\(label)"))
    }
}

/// The Done button that closes a sheet.
func doneButton(_ action: @escaping () -> Void) -> BarButton {
    BarButton(title: sheetDone, identifier: "sheet-done", action: action)
}

// MARK: - Voicing and Instrument

/// Voicing: Piano, Fretted, Ensembles and Your voicings, the current one
/// checked. Choosing one applies it at once (the sheet stays, Done closes
/// it); Edit voicings… opens Settings › Voicings.
struct VoicingPickerSheet: View {
    let state: VoicingMenuState?
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        SheetScaffold(title: VoicingSheetTexts.title, confirm: doneButton { event(.done) }) {
            List {
                Section {
                } footer: {
                    Text(VoicingSheetTexts.subtitle)
                }
                if let state {
                    ForEach(voicingGroups(state), id: \.kind) { group in
                        Section(group.kind.title) {
                            ForEach(group.choices, id: \.value) { choice in
                                ChoiceRow(label: choice.label, selected: choice.selected,
                                          identifier: "voicing-\(choice.value)") {
                                    event(.chooseVoicing(choice.value))
                                }
                            }
                        }
                    }
                }
                Section {
                    Button { event(.editVoicings) } label: {
                        Label(VoicingSheetTexts.edit, systemImage: AppSymbols.edit)
                    }
                    .accessibilityIdentifier("sheet-\(VoicingSheetTexts.edit)")
                }
            }
            .listStyle(.insetGrouped)
        }
        .accessibilityIdentifier("voicing-sheet")
    }
}

/// Instrument, two levels in a navigation stack: the 16 General MIDI
/// families (the current one shows its instrument), then a family's 8
/// programs with their numbers, the current one checked; Back goes to the
/// families, Done closes.
struct InstrumentPickerSheet: View {
    let state: InstrumentMenuState?
    /// The open family's index, or nil for the families.
    let family: Int?
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        let families = state.map(instrumentFamilies) ?? []
        NavigationStack(path: Binding(get: { family.map { [$0] } ?? [] }, set: { path in
            if let last = path.last {
                if last != family { event(.openFamily(last)) }
            } else if family != nil {
                event(.back)
            }
        })) {
            List {
                ForEach(Array(families.enumerated()), id: \.offset) { pair in
                    let f = pair.element
                    NavigationLink(value: pair.offset) {
                        HStack {
                            Text(f.name)
                                .frame(maxWidth: .infinity, alignment: .leading)
                            if f.isCurrent, let current = f.programs.first(where: \.selected) {
                                Text(programParts(current).name)
                                    .foregroundColor(Color(uiColor: .secondaryLabel))
                                    .lineLimit(1)
                            }
                        }
                    }
                    .accessibilityAddTraits(f.isCurrent ? .isSelected : [])
                    .accessibilityIdentifier("family-\(pair.offset)")
                }
            }
            .listStyle(.insetGrouped)
            .sheetBar(title: InstrumentSheetTexts.title, cancel: nil, confirm: doneButton { event(.done) })
            .navigationDestination(for: Int.self) { index in
                programs(families.indices.contains(index) ? families[index] : nil)
            }
        }
        .accessibilityIdentifier("instrument-sheet")
    }

    private func programs(_ open: FamilyRow?) -> some View {
        List {
            ForEach(open?.programs ?? [], id: \.program) { program in
                let parts = programParts(program)
                ChoiceRow(label: parts.name, detail: parts.number, detailMonospaced: true, selected: program.selected,
                          identifier: "program-\(program.program)") {
                    event(.chooseInstrument(program.program))
                }
            }
        }
        .listStyle(.insetGrouped)
        .sheetBar(title: open?.name ?? InstrumentSheetTexts.title, cancel: nil, confirm: doneButton { event(.done) })
    }
}

// MARK: - Speed

/// Playback speed: the value in large type, the system's slider over
/// 12.5–400 % (5 % stops; the session gets each new one), then Reset and
/// Manual…; Done closes. Manual… is a small sheet of its own over this one.
struct SpeedSheet: View {
    /// The session's speed.
    let pct: Double
    let slider: SpeedSlider
    let colors: AppColors
    /// Manual…'s field while it is open.
    var entry: SpeedEntry?
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        let shown = slider.shown(pct)
        SheetScaffold(title: SpeedTexts.title, confirm: doneButton { event(.done) }) {
            List {
                Section {
                    VStack(spacing: 8) {
                        Text("\(speedPctText(shown))%")
                            .font(.largeTitle.weight(.semibold).monospacedDigit())
                            .foregroundStyle(.tint)
                            .frame(maxWidth: .infinity)
                            .accessibilityIdentifier("speed-value")
                        Slider(value: Binding(get: { speedFraction(shown) },
                                              set: { event(.speedDragged(speedAt(fraction: $0))) }),
                               in: 0...1) {
                            Text(SpeedTexts.title)
                        } minimumValueLabel: {
                            Text("\(speedPctText(speedMinPct))%").font(.caption)
                        } maximumValueLabel: {
                            Text("\(speedPctText(speedMaxPct))%").font(.caption)
                        }
                        .accessibilityValue("\(speedPctText(shown))%")
                        .accessibilityAdjustableAction { direction in
                            switch direction {
                            case .increment: event(.speedDragged(shown + speedStepPct))
                            case .decrement: event(.speedDragged(shown - speedStepPct))
                            @unknown default: break
                            }
                        }
                        .accessibilityIdentifier("speed-slider")
                    }
                    .padding(.vertical, 6)
                }
                Section {
                    Button(SpeedTexts.reset) { event(.speedReset) }
                        .accessibilityIdentifier("sheet-\(SpeedTexts.reset)")
                    Button(SpeedTexts.manual) { event(.speedManual) }
                        .accessibilityIdentifier("sheet-\(SpeedTexts.manual)")
                }
            }
            .listStyle(.insetGrouped)
        }
        .sheet(isPresented: Binding(get: { live && entry != nil }, set: { shown in
            if !shown && entry != nil { event(.back) }
        })) {
            if let entry {
                SpeedEntrySheet(entry: entry, live: live, event: event)
                    .presentationDetents([.medium])
            }
        }
        .accessibilityIdentifier("speed-sheet")
    }
}

/// Manual…: the speed typed, 12.5–400, checked by OK (a wrong one stays,
/// with the range in red).
struct SpeedEntrySheet: View {
    let entry: SpeedEntry
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        SheetScaffold(title: SpeedTexts.title,
                      cancel: BarButton(title: "Cancel") { event(.back) },
                      confirm: BarButton(title: "OK", identifier: "speed-ok") { event(.speedOK) }) {
            Form {
                Section {
                    NumberEntryRow(text: entry.text, suffix: "%", keyboard: .decimalPad, live: live,
                                   identifier: "speed-field", change: { event(.speedTyped($0)) },
                                   submit: { event(.speedOK) })
                } footer: {
                    Text(entry.supportingText)
                        .foregroundColor(entry.showError ? .red : nil)
                }
            }
        }
        .accessibilityIdentifier("speed-dialog")
    }
}

/// A typed number in a form row: the field, its unit after it; it takes
/// the keyboard when the sheet opens (live).
struct NumberEntryRow: View {
    let text: String
    var suffix: String?
    var keyboard: UIKeyboardType = .numberPad
    var live = true
    var identifier: String?
    var change: (String) -> Void = { _ in }
    var submit: () -> Void = {}

    @FocusState private var focused: Bool

    var body: some View {
        HStack {
            TextField("", text: Binding(get: { text }, set: { change($0) }))
                .keyboardType(keyboard)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .submitLabel(.done)
                .focused($focused)
                .onSubmit(submit)
                .modifier(AlertIdentifier(id: identifier))
            if let suffix {
                Text(suffix).foregroundColor(Color(uiColor: .secondaryLabel))
            }
        }
        .task {
            guard live else { return }
            focused = true
        }
    }
}

// MARK: - Playback settings

/// Playback settings (the player's song pill): Tempo, Time signature and
/// Key, each with a line saying what it does. A value set by a directive is
/// read only with "Set by `{bpm: 90}` in the song · Edit"; the others are
/// this song's values (not saved with the file, as the note at the bottom
/// says): the time and key as pop-up menus, the tempo typed in a small sheet.
/// Write into song inserts the missing directives at the top. While a song
/// plays the values and Write into song are greyed, and a tap says why.
struct SongDefaultsSheet: View {
    let state: SongDefaultsState
    let keys: [String]
    let colors: AppColors
    let directive: Color
    /// The tempo's field while its sheet is open.
    var tempo: String?
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    init(state: SongDefaultsState, keys: [String], colors: AppColors, directive: Color, tempo: String? = nil,
         live: Bool = true, event: @escaping (SheetEvent) -> Void = { _ in }) {
        self.state = state
        self.keys = keys
        self.colors = colors
        self.directive = directive
        self.tempo = tempo
        self.live = live
        self.event = event
    }

    var body: some View {
        let locked = state.lockedReason != nil
        SheetScaffold(title: SongDefaultsTexts.title, confirm: doneButton { event(.done) }) {
            List {
                Section {
                    ForEach(songDefaultRows(state, keys: keys), id: \.kind) { row in
                        defaultRow(row, locked: locked)
                    }
                }
                Section {
                    Button { event(.writeIntoSong) } label: {
                        Text(SongDefaultsTexts.write)
                            .foregroundStyle(locked || !state.anythingToWrite ? AnyShapeStyle(HierarchicalShapeStyle.tertiary)
                                             : AnyShapeStyle(TintShapeStyle()))
                    }
                    .disabled(!state.anythingToWrite)
                    .accessibilityIdentifier("song-defaults-write")
                } footer: {
                    if state.anythingToWrite {
                        Text(SongDefaultsTexts.unsaved)
                    }
                }
            }
            .listStyle(.insetGrouped)
        }
        .sheet(isPresented: Binding(get: { live && tempo != nil }, set: { shown in
            if !shown && tempo != nil { event(.tempoCancel) }
        })) {
            if let tempo {
                TempoSheet(text: tempo, live: live, event: event)
                    .presentationDetents([.medium])
            }
        }
        .accessibilityIdentifier("song-defaults-sheet")
    }

    @ViewBuilder
    private func defaultRow(_ row: SongDefaultRow, locked: Bool) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .center, spacing: 12) {
                AppIcon(row.icon, size: 18)
                    .frame(width: 28)
                VStack(alignment: .leading, spacing: 2) {
                    Text(row.label)
                    Text(row.about)
                        .font(.footnote)
                        .foregroundColor(Color(uiColor: .secondaryLabel))
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                value(row, locked: locked)
            }
            if row.fromDirective { setBy(row) }
        }
        .padding(.vertical, 2)
    }

    /// The value: grey when a directive sets it; a pop-up menu (the tempo:
    /// a button that opens its sheet) otherwise; greyed while a song plays,
    /// when a tap says why.
    @ViewBuilder
    private func value(_ row: SongDefaultRow, locked: Bool) -> some View {
        if row.fromDirective {
            Text(row.display)
                .foregroundColor(Color(uiColor: .secondaryLabel))
        } else if locked || row.kind == .tempo || !live {
            Button { event(row.kind == .tempo ? .tempoOpen : .locked) } label: { menuLabel(row.display, locked: locked) }
                .buttonStyle(.borderless)
                .accessibilityIdentifier(row.kind == .tempo ? "song-defaults-tempo" : "song-defaults-\(row.kind.rawValue)")
        } else {
            Menu {
                ForEach(row.choices, id: \.self) { choice in
                    Button(choice) { event(.chooseDefault(row, choice)) }
                }
            } label: {
                menuLabel(row.display, locked: false)
            }
            .buttonStyle(.borderless)
            .accessibilityIdentifier("song-defaults-\(row.kind.rawValue)")
        }
    }

    private func menuLabel(_ text: String, locked: Bool) -> some View {
        HStack(spacing: 4) {
            Text(text)
            Image(systemName: "chevron.up.chevron.down")
                .font(.caption.weight(.semibold))
        }
        .foregroundStyle(locked ? AnyShapeStyle(HierarchicalShapeStyle.tertiary) : AnyShapeStyle(TintShapeStyle()))
    }

    /// "Set by `{bpm: 90}` in the song · Edit", under a row a directive sets.
    /// Edit is a button of its own, at least 44 pt each way: a link inside the
    /// text was a target a few points high that a real tap missed (S0 issue 13).
    private func setBy(_ row: SongDefaultRow) -> some View {
        var text = AttributedString("\(SongDefaultsTexts.setBy) ")
        var code = AttributedString(row.code)
        code.foregroundColor = directive
        code.font = .footnote.monospaced()
        text += code
        text += AttributedString(" \(SongDefaultsTexts.inSong)")
        if row.directiveOffset != nil { text += AttributedString(" ·") }
        return HStack(alignment: .center, spacing: 0) {
            Text(text)
                .font(.footnote)
                .foregroundColor(Color(uiColor: .secondaryLabel))
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityIdentifier("song-defaults-set-by-\(row.kind.rawValue)")
            if let offset = row.directiveOffset {
                Button { event(.editDirective(offset)) } label: {
                    Text(SongDefaultsTexts.edit)
                        .font(.footnote.weight(.semibold))
                        .padding(.leading, 4)
                        .padding(.trailing, 12)
                        .frame(minWidth: 44, minHeight: 44, alignment: .leading)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.borderless)
                .accessibilityIdentifier("song-defaults-edit-\(row.kind.rawValue)")
            }
            Spacer(minLength: 0)
        }
        .padding(.leading, 40)
    }
}

/// The tempo for this song, typed (the session parses and clamps it).
struct TempoSheet: View {
    let text: String
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        SheetScaffold(title: "Tempo",
                      cancel: BarButton(title: "Cancel") { event(.tempoCancel) },
                      confirm: BarButton(title: "OK", enabled: !text.trimmingCharacters(in: .whitespaces).isEmpty,
                                         identifier: "tempo-ok") { event(.tempoOK) }) {
            Form {
                Section {
                    NumberEntryRow(text: text, suffix: "bpm", keyboard: .numberPad, live: live,
                                   identifier: "tempo-field", change: { event(.tempoTyped($0)) },
                                   submit: { event(.tempoOK) })
                } footer: {
                    Text(SongDefaultsTexts.tempoAbout)
                }
            }
        }
        .accessibilityIdentifier("tempo-dialog")
    }
}

// MARK: - Insert

/// ＋ Insert: Tempo, Time signature, Key, Capo, Label and Loop, each showing its directive.
struct InsertSheet: View {
    let colors: AppColors
    var live = true
    var event: (SheetEvent) -> Void = { _ in }

    var body: some View {
        SheetScaffold(title: InsertTexts.title,
                      cancel: BarButton(title: InsertTexts.cancel, identifier: "sheet-\(InsertTexts.cancel)") {
                          event(.dismiss)
                      }) {
            List {
                ForEach(insertEntries, id: \.self) { entry in
                    Button { event(.insert(entry.kind)) } label: {
                        HStack(spacing: 12) {
                            AppIcon(entry.icon, size: 18)
                                .frame(width: 28)
                            Text(entry.label)
                                .foregroundColor(Color(uiColor: .label))
                                .frame(maxWidth: .infinity, alignment: .leading)
                            Text(entry.code)
                                .font(.callout.monospaced())
                                .foregroundColor(Color(uiColor: .secondaryLabel))
                        }
                        .contentShape(Rectangle())
                    }
                    .accessibilityIdentifier("insert-\(entry.kind.wire)")
                }
            }
            .listStyle(.insetGrouped)
        }
        .accessibilityIdentifier("insert-sheet")
    }
}

/// Examples (Android's `ExamplesSheet`): the songs the app ships, by file
/// name; a tap opens a copy of one.
struct ExamplesSheet: View {
    let names: [String]
    let colors: AppColors
    var scrolls = true
    var choose: (String) -> Void = { _ in }
    var done: () -> Void = {}

    var body: some View {
        SheetScaffold(title: "Examples", confirm: doneButton(done)) {
            List {
                ForEach(names, id: \.self) { name in
                    Button { choose(name) } label: {
                        Label {
                            Text(name)
                                .foregroundColor(Color(uiColor: .label))
                                .lineLimit(1)
                        } icon: {
                            Image(systemName: AppSymbols.recent)
                        }
                    }
                    .accessibilityIdentifier("example-\(name)")
                }
            }
            .listStyle(.insetGrouped)
        }
    }
}
