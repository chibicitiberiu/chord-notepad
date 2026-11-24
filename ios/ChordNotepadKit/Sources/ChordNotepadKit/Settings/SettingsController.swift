import Foundation

// The Settings screen's state holder, ported from Android's
// ui/settings/SettingsController.kt: the settings edit's life (begin,
// autosave, leaving), the General/Playback draft, navigation and the voicing
// commands, with the commands Android sends. A value: each call queues its
// commands in ``SettingsController/outbox``, which the app sends
// (``SettingsController/takeCommands()``) and the tests read.

/// Where the Settings screen is in its life.
public enum SettingsPhase: Sendable, Equatable {
    /// Not started: ``SettingsController/start(needSchema:)`` sends `begin_settings_edit`.
    case new
    /// `begin_settings_edit` sent, waiting for an active `VoicingEditorState`.
    case opening
    /// Editing; every change is saved as it is made (`commit_settings`).
    case editing
    /// Left: the edit ended and the screen goes away.
    case closed
}

/// How long a number setting's text rests before it is saved (``SettingsController/saveDraft()``),
/// in seconds; the voicing form's errors banner waits as long.
public let draftSaveDelay = 0.4

/// From this width (points) the pages list stays on the left (iPads, a phone on its side is narrower).
public let settingsTwoPaneWidth = 600.0

/// The voicings list and form need this much width beside the pages list to sit side by side.
public let voicingsSplitContentWidth = 720.0

/// The pages list's width in two panes, and the voicings list's in a split.
public let settingsPagesPaneWidth = 240.0
public let voicingsListWidth = 280.0

/// Whether Settings shows its pages list beside the page in a window `width` wide.
public func settingsTwoPane(width: Double) -> Bool { width >= settingsTwoPaneWidth }

/// Whether the Voicings page shows its list and form side by side in a window
/// `width` wide: with room for both after the pages list (Android's L14: a
/// phone on its side, 914 dp, got three columns and a 300 dp form).
public func splitsVoicings(width: Double) -> Bool {
    let pages = settingsTwoPane(width: width) ? settingsPagesPaneWidth : 0
    return width - pages >= voicingsSplitContentWidth
}

/// Which page is open. On phones `page` nil is the list of pages; with two
/// panes the list is always there and nil shows General. `voicingDetail` is
/// the voicing form on phones (list → form).
public struct SettingsNav: Sendable, Equatable {
    public var page: SettingsPage?
    public var voicingDetail: Bool

    public init(_ page: SettingsPage? = nil, voicingDetail: Bool = false) {
        self.page = page
        self.voicingDetail = voicingDetail
    }

    /// The page the content pane shows.
    public func shown(twoPane: Bool) -> SettingsPage? { page ?? (twoPane ? .general : nil) }

    /// The same, with the page two panes show made the open one, so a
    /// rotation to one pane stays on it (Android's L8: it dropped to the pages list).
    public func settled(twoPane: Bool) -> SettingsNav {
        twoPane && page == nil ? SettingsNav(.general, voicingDetail: voicingDetail) : self
    }

    /// Back: from the voicing form to the list (unless both show, `split`),
    /// from a page to the list of pages (phones), else nil: leave the screen.
    public func back(twoPane: Bool, split: Bool) -> SettingsNav? {
        if page == .voicings && voicingDetail && !split { return SettingsNav(page, voicingDetail: false) }
        if page != nil && !twoPane { return SettingsNav() }
        return nil
    }
}

/// A dialog the Settings screen shows over itself.
public enum SettingsDialog: Sendable, Equatable {
    /// Leaving with wrong values: Edit (go to the first) or Discard (drop them and leave).
    case problems
    /// Remove voicing `name`? (`remove_confirm`)
    case removeVoicing(String)
    /// Rename voicing `name`.
    case rename(String)
    /// Switch to `model`, dropping the edits? (`model_confirm`)
    case changeModel(String)
}

/// What the Settings screen shows, apart from the voicings editor state.
///
/// `saved` is the General/Playback values Python has: what the screen opened
/// with, then the last ones sent with `commit_settings`. `numberTexts` are
/// number fields whose text isn't a whole number in range, with that text
/// (not saved; the draft keeps the saved value), `sentNumbers` the ones
/// Python has (`invalid_numbers`, kept for next time). `adoptStaged`: this
/// screen began the edit, so it takes the number texts Python kept from last
/// time when it opens.
public struct SettingsUi: Sendable, Equatable {
    public var phase = SettingsPhase.new
    public var nav = SettingsNav()
    public var draft: SettingsDraft?
    public var saved: SettingsDraft?
    public var numberTexts: [NumberSetting: String] = [:]
    public var sentNumbers: [NumberSetting: String] = [:]
    public var adoptStaged = false
    public var dialog: SettingsDialog?
    /// A number field to put the cursor in, once (Edit in the problems dialog or banner: P8).
    public var focus: NumberSetting?

    public init(nav: SettingsNav = SettingsNav()) {
        self.nav = nav
    }

    /// The draft has changes not sent yet (a number being typed: ``SettingsController/saveDraft()``).
    public var draftPending: Bool { draft != nil && draft != saved }

    /// The wrong number texts changed since they were last sent.
    public var numbersPending: Bool { numberTexts != sentNumbers }
}

/// The voicings editor as the form draws it: the state plus local edits not echoed yet.
public struct EditorView: Sendable, Equatable {
    public var state: VoicingEditorState
    public var values: JSONValue

    public init(state: VoicingEditorState, values: JSONValue) {
        self.state = state
        self.values = values
    }
}

/// The Settings screen's state holder. Every change is saved as it is made: a
/// voicing command is followed by `commit_settings` (Python writes each
/// voicing's valid fields), and a General/Playback change goes out at once,
/// or after ``draftSaveDelay`` for a number being typed (the screen calls
/// ``saveDraft()``). Wrong values aren't saved; Python keeps them for next
/// time, and leaving asks what to do with them (``SettingsDialog/problems``).
/// Fed by the session's states (``onSettings(_:)``, ``onEditor(_:)``).
public struct SettingsController: Sendable {
    public private(set) var ui: SettingsUi
    /// The voicings editor (nil until an active state arrives).
    public private(set) var editor: EditorView?
    /// The limits and choices of the newest `SettingsState`.
    public private(set) var limits: SettingsState?
    /// The commands queued since the last ``takeCommands()``, in order.
    public private(set) var outbox: [BridgeCommand] = []
    private var pending = PendingEdits()

    /// A screen that opens at `initialPage` (Voicings, from the Voicing sheet's Edit voicings…).
    public init(initialPage: SettingsPage? = nil) {
        ui = SettingsUi(nav: SettingsNav(initialPage))
    }

    /// A screen already editing what `snapshot` holds (its settings and an
    /// active voicings editor), at `nav`, with nothing to send: the preview
    /// catalog draws Settings from a recorded scene this way.
    public static func showing(_ snapshot: SessionSnapshot, nav: SettingsNav = SettingsNav()) -> SettingsController {
        var controller = SettingsController()
        controller.start(needSchema: false)
        if let settings = snapshot.settings { controller.onSettings(settings) }
        if let editor = snapshot.voicingEditor { controller.onEditor(editor) }
        controller.outbox = []
        controller.ui.nav = nav
        return controller
    }

    /// The queued commands, emptying the outbox.
    public mutating func takeCommands() -> [BridgeCommand] {
        defer { outbox = [] }
        return outbox
    }

    private mutating func send(_ command: BridgeCommand) {
        outbox.append(command)
    }

    /// Open the edit (once). `needSchema`: also ask for the form schema.
    public mutating func start(needSchema: Bool) {
        if needSchema { send(.requestVoicingEditorSchema()) }
        guard ui.phase == .new else { return }
        send(.beginSettingsEdit())
        ui.phase = .opening
        ui.adoptStaged = true
    }

    /// A `SettingsState` arrived: the draft starts from the first one.
    public mutating func onSettings(_ state: SettingsState) {
        limits = state
        if ui.draft == nil {
            let draft = SettingsDraft.of(state)
            ui.draft = draft
            ui.saved = draft
        }
    }

    /// A `VoicingEditorState` arrived.
    public mutating func onEditor(_ state: VoicingEditorState) {
        if state.active { pending.onState(state.values) }
        var next = ui
        switch ui.phase {
        case .opening:
            if state.active {
                // Python's number texts: kept from last time (adopted when
                // this screen began the edit) or after a restart.
                let staged = NumberSetting.fromKeys(state.stagedNumbers)
                next.phase = .editing
                next.sentNumbers = staged
                if ui.adoptStaged && ui.numberTexts.isEmpty { next.numberTexts = staged }
                next.adoptStaged = false
            }
        case .editing:
            // The edit is gone though nobody ended it: open a new one.
            if !state.active {
                pending.clear()
                send(.beginSettingsEdit())
                next.phase = .opening
            }
        case .new, .closed:
            break
        }
        if state.active && state.selected == nil && next.nav.voicingDetail {
            next.nav.voicingDetail = false
        }
        ui = next
        editor = state.active ? EditorView(state: state, values: pending.applyTo(state.values)) : nil
    }

    // MARK: - Saving and leaving

    /// Whether commands can go to the edit now.
    private var live: Bool { ui.phase == .editing && editor != nil }

    /// Whether ``saveDraft()`` has something to send once the typing rests.
    public var needsSave: Bool { ui.draftPending || ui.numbersPending }

    /// Send the draft's General/Playback values and the wrong number texts if
    /// they changed since the last save.
    public mutating func saveDraft() {
        if live && needsSave { commit() }
    }

    /// `commit_settings`, with the draft's values when they changed (null keeps
    /// the config's) and the wrong number texts when they changed.
    private mutating func commit() {
        let values = ui.draftPending ? ui.draft?.toValues() : nil
        let numbers = ui.numbersPending ? ui.numberTexts : nil
        if values != nil { ui.saved = ui.draft }
        ui.sentNumbers = ui.numberTexts
        let invalid: JSONValue? = numbers.map { texts in
            .object(Dictionary(uniqueKeysWithValues: texts.map { ($0.key.key, JSONValue.string($0.value)) }))
        }
        send(.commitSettings(invalidNumbers: invalid, values: values))
    }

    /// Whether something wrong isn't saved: a number field's text or a voicing value.
    public var hasProblems: Bool {
        !ui.numberTexts.isEmpty || !(editor?.state.problems.isEmpty ?? true)
    }

    /// Back out of the screen: asks first (``SettingsDialog/problems``) while
    /// something wrong isn't saved.
    public mutating func requestClose() {
        if ui.phase == .closed { return }
        if hasProblems {
            ui.dialog = .problems
        } else {
            close()
        }
    }

    /// Leave: save what the draft still holds, then end the edit (Python drops the wrong values).
    public mutating func close() {
        if ui.phase == .closed { return }
        saveDraft()
        send(.cancelSettingsEdit())
        pending.clear()
        ui.phase = .closed
        ui.dialog = nil
        ui.numberTexts = [:]
    }

    /// Edit (the leave dialog, or the banner of values kept from last time): go to the first problem.
    public mutating func editProblems() {
        ui.dialog = nil
        if let number = NumberSetting.allCases.first(where: { ui.numberTexts[$0] != nil }) {
            ui.nav = SettingsNav(number.page)
            ui.focus = number
            return
        }
        guard let state = editor?.state, let name = state.problems.first?.voicing else { return }
        if name == state.selected {
            ui.nav = SettingsNav(.voicings, voicingDetail: true)
        } else {
            selectVoicing(name)
        }
    }

    /// Drop the wrong values and stay (the banner of values kept from last time).
    public mutating func discardProblems() {
        send(.discardSettingsProblems())
        ui.numberTexts = [:]
        ui.sentNumbers = [:]
    }

    /// Back (the bar's ←): up one page, or ``requestClose()``.
    public mutating func back(twoPane: Bool, split: Bool) {
        if let up = ui.nav.back(twoPane: twoPane, split: split) {
            ui.nav = up
        } else {
            requestClose()
        }
    }

    // MARK: - Navigation and the draft

    /// The field asked for with ``SettingsUi/focus`` has the focus.
    public mutating func focusShown() {
        ui.focus = nil
    }

    /// Show `page`.
    public mutating func openPage(_ page: SettingsPage) {
        ui.nav = SettingsNav(page)
    }

    /// The layout is `twoPane` now: see ``SettingsNav/settled(twoPane:)``.
    public mutating func settleNav(twoPane: Bool) {
        ui.nav = ui.nav.settled(twoPane: twoPane)
    }

    /// Change the draft and save it at once.
    public mutating func updateDraft(_ change: (inout SettingsDraft) -> Void) {
        if var draft = ui.draft {
            change(&draft)
            ui.draft = draft
        }
        saveDraft()
    }

    /// Switch the draft's notation (the key stays; it shows in the new spelling).
    public mutating func setNotation(_ notation: String) {
        updateDraft { $0 = $0.withNotation(notation) }
    }

    /// A number field's text: a whole number in range goes into the draft
    /// (saved once the typing rests, ``saveDraft()``); anything else is marked
    /// invalid and not saved.
    public mutating func setNumber(_ setting: NumberSetting, _ text: String) {
        guard let limits, let draft = ui.draft else { return }
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let value = Int(trimmed).flatMap { setting.range(limits).contains($0) ? $0 : nil }
        if let value {
            ui.draft = setting.set(draft, value)
            ui.numberTexts[setting] = nil
        } else {
            // Back to the saved value: a number typed on the way (the 9 of
            // 999) must not be saved when the typing rests.
            ui.draft = ui.saved.map { setting.set(draft, setting.get($0)) } ?? draft
            ui.numberTexts[setting] = text
        }
    }

    /// − or + beside a number field: the value moved by `delta` within its range.
    public mutating func stepNumber(_ setting: NumberSetting, _ delta: Int) {
        guard let limits, let draft = ui.draft else { return }
        let range = setting.range(limits)
        let value = Swift.min(Swift.max(setting.get(draft) + delta, range.lowerBound), range.upperBound)
        setNumber(setting, String(value))
    }

    // MARK: - Dialogs

    /// Close the dialog without doing anything.
    public mutating func dismissDialog() {
        ui.dialog = nil
    }

    /// Do what the open dialog asks (`newName` for Rename).
    public mutating func confirmDialog(newName: String = "") {
        guard let dialog = ui.dialog else { return }
        ui.dialog = nil
        switch dialog {
        case .problems:
            ui.numberTexts = [:]
            close()
        case .removeVoicing(let name):
            touch(.removeVoicing(name: name))
        case .rename(let name):
            if newName != name { touch(.renameVoicing(new: newName, old: name)) }
        case .changeModel(let model):
            setModel(model)
        }
    }

    // MARK: - The voicings editor

    /// Show voicing `name` in the form (on phones, open the form).
    public mutating func selectVoicing(_ name: String) {
        pending.clear()
        send(.selectVoicing(name: name))
        ui.nav = SettingsNav(.voicings, voicingDetail: true)
    }

    /// Add a voicing that starts as `preset` (an ``VoicingEditorState/addPresets()``
    /// entry, or the built-in shown: its model and label); Python names and
    /// selects it. On phones the form opens.
    public mutating func addVoicingFrom(_ preset: VoicingPreset) {
        pending.clear()
        touch(.addVoicingFrom(group: preset.group, label: preset.label))
        ui.nav = SettingsNav(.voicings, voicingDetail: true)
    }

    /// Show built-in `label` of `model` in the form, read-only (on phones,
    /// open the form). Viewing one changes nothing, so nothing is saved.
    public mutating func selectBuiltin(model: String, label: String) {
        pending.clear()
        send(.selectBuiltin(group: model, label: label))
        ui.nav = SettingsNav(.voicings, voicingDetail: true)
    }

    /// Ask before removing `name` (not a built-in: it can't be removed).
    public mutating func askRemove(_ name: String) {
        if !showsBuiltin { ui.dialog = .removeVoicing(name) }
    }

    /// Open the rename dialog for `name` (not a built-in's).
    public mutating func askRename(_ name: String) {
        if !showsBuiltin { ui.dialog = .rename(name) }
    }

    /// Switch the selected voicing to `model`, asking first when it has edits (`dirty`).
    public mutating func askModel(_ model: String) {
        guard let state = editor?.state, model != state.model, !state.readOnly else { return }
        if state.dirty {
            ui.dialog = .changeModel(model)
        } else {
            setModel(model)
        }
    }

    /// A form edit (`set_voicing_values` with `payload`, e.g. from ``VoicingEdits``).
    public mutating func edit(_ payload: JSONValue) {
        if readOnly { return }
        pending.record(payload)
        touch(.setVoicingValues(values: payload))
        if let view = editor { editor = EditorView(state: view.state, values: pending.applyTo(view.state.values)) }
    }

    /// A records cell changed: the whole list goes out, built on the rows shown
    /// now (with edits not echoed yet), so quick edits of two cells both stay.
    public mutating func editCell(_ fieldId: String, index: Int, column: String, value: JSONValue) {
        guard let view = editor else { return }
        let rows = records(pending.applyTo(view.state.values)[fieldId])
        edit(VoicingEdits.cell(fieldId, rows: rows, index: index, column: column, value: value))
    }

    /// Add a row to records field `fieldId`.
    public mutating func addRecord(_ fieldId: String) {
        if readOnly { return }
        pending.clear(fieldId)
        touch(.addVoicingRecord(fieldId: fieldId))
    }

    /// Remove row `index` of records field `fieldId`.
    public mutating func removeRecord(_ index: Int, _ fieldId: String) {
        if readOnly { return }
        pending.clear(fieldId)
        touch(.removeVoicingRecord(fieldId: fieldId, index: index))
    }

    /// Move row `index` of records field `fieldId` by `offset` rows (-1 up, +1 down).
    public mutating func moveRecord(_ index: Int, _ offset: Int, _ fieldId: String) {
        if readOnly { return }
        pending.clear(fieldId)
        touch(.moveVoicingRecord(fieldId: fieldId, index: index, offset: offset))
    }

    /// Copy row `index` of records field `fieldId` right below it.
    public mutating func duplicateRecord(_ index: Int, _ fieldId: String) {
        if readOnly { return }
        pending.clear(fieldId)
        touch(.duplicateVoicingRecord(fieldId: fieldId, index: index))
    }

    private mutating func setModel(_ model: String) {
        if readOnly { return }
        pending.clear()
        touch(.setVoicingModel(model: model))
    }

    /// The form shows a built-in or a newer release's voicing: Python refuses
    /// the edit commands then (a `RuntimeError`), so none is sent.
    private var readOnly: Bool { editor?.state.readOnly == true }

    /// The form shows a built-in (``VoicingEditorState/showsBuiltin``).
    private var showsBuiltin: Bool { editor?.state.showsBuiltin == true }

    /// Send a voicing command, then save (Python writes it once every voicing is valid).
    private mutating func touch(_ command: BridgeCommand) {
        send(command)
        commit()
    }
}

/// What the Settings bar's title says: Settings with two panes or on the
/// pages list, the voicing's name on a phone's voicing form, else the page.
public func settingsTitle(_ ui: SettingsUi, editor: EditorView?, twoPane: Bool, split: Bool) -> String {
    let shown = ui.nav.shown(twoPane: twoPane)
    guard !twoPane, let shown else { return SettingsTexts.title }
    if shown == .voicings && ui.nav.voicingDetail && !split, let name = editor?.state.selected { return name }
    return shown.title
}

/// The restored-values banner shows: Python brought back wrong values typed
/// last time, and some are still there.
public func settingsShowsRestoredBanner(_ ui: SettingsUi, editor: EditorView?) -> Bool {
    let problems = !ui.numberTexts.isEmpty || !(editor?.state.problems.isEmpty ?? true)
    return editor?.state.restored == true && problems
}

/// The leave dialog's lines: each wrong number worded here (in page order),
/// then each voicing value as Python words it.
public func settingsProblemLines(_ ui: SettingsUi, editor: EditorView?, limits: SettingsState?) -> [String] {
    var lines: [String] = []
    for setting in ui.numberTexts.keys.sorted() {
        let text = ui.numberTexts[setting]!.trimmingCharacters(in: .whitespacesAndNewlines)
        lines.append(SettingsTexts.problemNumber(page: setting.page.title, label: setting.label,
                                                 text: text.isEmpty ? SettingsTexts.problemEmpty : text,
                                                 range: limits.map(setting.rangeText) ?? ""))
    }
    lines += editor?.state.problems.map(\.text) ?? []
    return lines
}
