import Foundation

// What the player's sheets and the Edit ribbon's tools do with a tap, as one
// reducer over the screen's own state (Android's SongScreen `Sheets`,
// MainScreen's CapoDialog and SessionRequests' Insert dialogs): the route,
// the dialogs' fields, and the commands to send. The views draw
// ``MainUiState`` and the snapshot, and hand every tap here.

/// The ribbon's tool buttons.
public enum RibbonTool: Sendable, Equatable {
    case insert, transpose, capo, identify
}

/// A tap in a sheet or a tool's dialog.
public enum SheetEvent: Sendable, Equatable {
    /// A player button opened a sheet.
    case open(MainRoute)
    case ribbon(RibbonTool)
    /// The dimmed screen, a swipe down, Done or Cancel: back one level, or closed.
    case dismiss
    /// Done: closed, whatever level.
    case done
    /// A sheet's ← (the instrument's families), the speed dialog's Cancel.
    case back

    case chooseVoicing(String)
    /// Edit voicings… (Settings › Voicings, which the iOS app hasn't got yet).
    case editVoicings
    case openFamily(Int)
    case chooseInstrument(Int)

    /// The speed slider moved to a value (unsnapped).
    case speedDragged(Double)
    case speedReset
    case speedManual
    case speedTyped(String)
    case speedOK

    /// Playback settings' tempo value: its dialog.
    case tempoOpen
    case tempoTyped(String)
    case tempoOK
    case tempoCancel
    /// A time signature or key picked in its dropdown.
    case chooseDefault(SongDefaultRow, String)
    /// "Edit" under a value a directive sets: Edit mode, the cursor at it (code points).
    case editDirective(Int)
    case writeIntoSong
    /// A tap on a value or Write into song while a song plays.
    case locked

    case insert(DirectiveKind)

    case transposeUp, transposeDown, transposeOK

    /// The Insert dialog for the pending request appeared.
    case directiveShown
    case directiveChanged(DirectiveForm)
    case directiveInsert
    case directiveCancel
    /// Insert Capo's Suggest: the request dropped, Suggest Capo opened.
    case directiveSuggest

    case capoPick(Int)
    case capoVoicing(String)
    case capoApply
    case capoCancel

    case identifierTap(PianoKey)
    case identifierPress(PianoKey)
    case identifierType(String)
    case identifierClear
    case identifierPick(String, rolled: Bool)
    case identifierPlay(rolled: Bool)
    /// Insert (nil: the picked candidate) or a candidate's double tap.
    case identifierInsert(String?)
    /// The sounding keys' time ran out for this token.
    case identifierExpired(Int)
}

/// What the app does after a ``SheetEvent``.
public struct SheetEffects: Sendable {
    /// Commands for the session, in order (the editor's text first when a tool reads it).
    public var commands: [BridgeCommand] = []
    /// The request these commands answer (the snapshot drops it).
    public var answered: Int?
    /// A short note for a greyed control.
    public var notice: String?
    /// Switch to Edit with the cursor at this code point.
    public var editAt: Int?

    public init() {}
}

/// The fields of the open dialogs: the screen's own, not the session's.
public struct ToolsUiState: Sendable, Equatable {
    public var transpose = TransposeForm()
    public var speedSlider = SpeedSlider()
    /// The speed's Manual… field while its dialog is open.
    public var speedEntry: SpeedEntry?
    /// Playback settings' tempo field while its dialog is open.
    public var tempoEntry: String?
    /// The Insert dialog's fields, for the request they were made for.
    public var directive: DirectiveFormState?
    /// The Suggest Capo row picked, for the voicing and rows it was picked among.
    public var capoPick: CapoPick?
    public var identifier = IdentifierModel()
    /// The sounding token whose time ran out.
    public var identifierExpired = 0

    public init() {}
}

/// An Insert dialog's fields and the ones it opened with.
public struct DirectiveFormState: Sendable, Equatable {
    public var requestId: Int
    public var form: DirectiveForm
    public var initial: DirectiveForm

    public init(requestId: Int, form: DirectiveForm, initial: DirectiveForm) {
        self.requestId = requestId
        self.form = form
        self.initial = initial
    }

    /// Errors show once the user changed something.
    public var changed: Bool { form != initial }
}

/// A Suggest Capo pick. A new voicing or new rows start again from the
/// recommended row, as Android's `rememberSaveable(state.voicing, state.rows)`.
public struct CapoPick: Sendable, Equatable {
    public var voicing: String
    public var rows: [CapoRow]
    public var capo: Int
}

extension MainUiState {
    /// The Suggest Capo row chosen now.
    public func capoChosen(_ state: CapoAdviceState) -> Int? {
        let pick = tools.capoPick.flatMap { $0.voicing == state.voicing && $0.rows == state.rows ? $0.capo : nil }
        return capoChoice(state, picked: pick)
    }

    /// Whether Apply can go now.
    public func capoCanApplyNow(_ state: CapoAdviceState) -> Bool {
        let pick = tools.capoPick.flatMap { $0.voicing == state.voicing && $0.rows == state.rows ? $0.capo : nil }
        return capoCanApply(state, picked: pick)
    }

    /// The Insert dialog's fields for `request`: kept while the request is the
    /// same, fresh (the desktop's defaults) for a new one.
    public func directiveForm(for request: InsertDirectiveRequest, snapshot: SessionSnapshot) -> DirectiveFormState? {
        guard let kind = DirectiveKind.of(request.kind) else { return nil }
        if let state = tools.directive, state.requestId == request.requestId { return state }
        let initial = DirectiveForm.initial(kind, keys: insertKeys(request, snapshot))
        return DirectiveFormState(requestId: request.requestId, form: initial, initial: initial)
    }

    /// What the Insert dialog shows about its fields.
    public func directiveVerdict(for request: InsertDirectiveRequest, snapshot: SessionSnapshot) -> DirectiveVerdict {
        guard let state = directiveForm(for: request, snapshot: snapshot) else {
            return DirectiveVerdict(canInsert: false, messages: [])
        }
        return DirectiveVerdict.of(kind: request.kind, requestId: request.requestId, answer: state.form.answer(),
                                   check: snapshot.directiveCheck, showErrors: state.changed)
    }

    /// Handle `event`; `editor` is the editor's model (a tool reads its text,
    /// selection and cursor, and sends the text first).
    public mutating func handle(_ event: SheetEvent, snapshot: SessionSnapshot,
                                editor: inout EditorModel) -> SheetEffects {
        var effects = SheetEffects()
        switch event {
        case .open(let target):
            if case .speed = target {
                tools.speedSlider = SpeedSlider()
                tools.speedEntry = nil
            }
            if target == .songDefaults { tools.tempoEntry = nil }
            route = target
        case .ribbon(let tool):
            switch tool {
            case .insert:
                route = .insert
            case .transpose:
                tools.transpose = TransposeForm()
                route = .transpose(selection: editor.toolSelection != nil)
            case .capo:
                route = .none
                effects.commands = editor.suggestCapoCommands()
            case .identify:
                tools.identifier = IdentifierModel()
                tools.identifierExpired = 0
                effects.commands = tools.identifier.open()
                route = .identify
            }
        case .dismiss:
            if route == .identify { tools.identifier = IdentifierModel() }
            if case .speed(true) = route { tools.speedEntry = nil }
            route = route.afterSheetDismissed().route
        case .done:
            route = .none
            tools.speedEntry = nil
            tools.tempoEntry = nil
        case .back:
            if case .speed(true) = route { tools.speedEntry = nil }
            route = route.back()

        case .chooseVoicing(let value):
            if snapshot.voicingMenu?.selected != value { effects.commands = [.setVoicing(voicing: value)] }
        case .editVoicings:
            effects.notice = SheetNotices.editVoicings
        case .openFamily(let index):
            route = route.openingFamily(index)
        case .chooseInstrument(let program):
            if snapshot.instrumentMenu?.current != program { effects.commands = [.setInstrument(program: program)] }

        case .speedDragged(let value):
            if let command = tools.speedSlider.moved(to: value) { effects.commands = [command] }
        case .speedReset:
            tools.speedSlider = SpeedSlider()
            effects.commands = [.resetMultiplier()]
        case .speedManual:
            tools.speedEntry = SpeedEntry(pct: snapshot.toolbar?.multiplierPct ?? 100)
            route = .speed(manual: true)
        case .speedTyped(let text):
            tools.speedEntry?.type(text)
        case .speedOK:
            if let command = tools.speedEntry?.submit() {
                tools.speedSlider = SpeedSlider()
                tools.speedEntry = nil
                effects.commands = [command]
                route = .speed(manual: false)
            }

        case .tempoOpen:
            if let locked = snapshot.songDefaults?.lockedReason {
                effects.notice = locked
            } else {
                tools.tempoEntry = snapshot.songDefaults?.tempo.value ?? ""
            }
        case .tempoTyped(let text):
            if tools.tempoEntry != nil { tools.tempoEntry = text }
        case .tempoOK:
            if let text = tools.tempoEntry, let command = tempoCommand(text) {
                effects.commands = [command]
                tools.tempoEntry = nil
            }
        case .tempoCancel:
            tools.tempoEntry = nil
        case .chooseDefault(let row, let choice):
            if let locked = snapshot.songDefaults?.lockedReason {
                effects.notice = locked
            } else if let command = songDefaultChoice(row, choice) {
                effects.commands = [command]
            }
        case .editDirective(let offset):
            route = .none
            effects.editAt = offset
        case .writeIntoSong:
            if let locked = snapshot.songDefaults?.lockedReason {
                effects.notice = locked
            } else if snapshot.songDefaults?.anythingToWrite == true {
                effects.commands = editor.syncCommands() + [.writeSongDefaults()]
                route = .none
            }
        case .locked:
            effects.notice = snapshot.songDefaults?.lockedReason

        case .insert(let kind):
            route = .none
            effects.commands = editor.insertDirectiveCommands(kind)

        case .transposeUp:
            tools.transpose = tools.transpose.up()
        case .transposeDown:
            tools.transpose = tools.transpose.down()
        case .transposeOK:
            route = .none
            effects.commands = editor.transposeCommands(tools.transpose.semitones, selection: editor.toolSelection)

        case .directiveShown:
            guard case .insertDirective(let request)? = snapshot.request else { break }
            guard let state = directiveForm(for: request, snapshot: snapshot) else {
                // A kind this app doesn't know: cancelled, as Android does.
                effects.commands = [.respondToInsertDirectiveRequest(requestId: request.requestId, value: nil)]
                effects.answered = request.requestId
                break
            }
            let fresh = tools.directive?.requestId != request.requestId
            tools.directive = state
            if fresh { effects.commands = [checkCommand(request, state.form)] }
        case .directiveChanged(let form):
            guard case .insertDirective(let request)? = snapshot.request,
                  var state = directiveForm(for: request, snapshot: snapshot) else { break }
            let changed = form.answer() != state.form.answer()
            state.form = form
            tools.directive = state
            if changed { effects.commands = [checkCommand(request, form)] }
        case .directiveInsert:
            guard case .insertDirective(let request)? = snapshot.request,
                  let state = directiveForm(for: request, snapshot: snapshot),
                  directiveVerdict(for: request, snapshot: snapshot).canInsert else { break }
            effects.commands = [.respondToInsertDirectiveRequest(requestId: request.requestId,
                                                                 value: state.form.answer())]
            effects.answered = request.requestId
            tools.directive = nil
        case .directiveCancel, .directiveSuggest:
            guard case .insertDirective(let request)? = snapshot.request else { break }
            effects.commands = [.respondToInsertDirectiveRequest(requestId: request.requestId, value: nil)]
            effects.answered = request.requestId
            tools.directive = nil
            if event == .directiveSuggest { effects.commands += editor.suggestCapoCommands() }

        case .capoPick(let capo):
            if let state = snapshot.capoAdvice {
                tools.capoPick = CapoPick(voicing: state.voicing, rows: state.rows, capo: capo)
            }
        case .capoVoicing(let value):
            if snapshot.capoAdvice?.voicing != value { effects.commands = [.capoAdviceVoicing(voicing: value)] }
        case .capoApply:
            if let state = snapshot.capoAdvice, capoCanApplyNow(state), let capo = capoChosen(state) {
                effects.commands = [.capoAdviceApply(capo: capo)]
                tools.capoPick = nil
            }
        case .capoCancel:
            effects.commands = [.capoAdviceClose()]
            tools.capoPick = nil

        case .identifierTap(let key):
            effects.commands = tools.identifier.tapKey(key)
        case .identifierPress(let key):
            effects.commands = tools.identifier.pressKey(key)
        case .identifierType(let text):
            effects.commands = tools.identifier.type(text)
        case .identifierClear:
            effects.commands = tools.identifier.clear()
        case .identifierPick(let chord, let rolled):
            effects.commands = tools.identifier.pick(chord, rolled: rolled)
        case .identifierPlay(let rolled):
            effects.commands = tools.identifier.play(rolled: rolled)
        case .identifierInsert(let chord):
            if let chord = tools.identifier.insert(chord) { effects.commands = editor.insertChordCommands(chord) }
        case .identifierExpired(let token):
            tools.identifierExpired = token
        }
        return effects
    }

    /// A session output arrived: the identifier's field and pick follow it,
    /// and the speed slider lets go once the session has its value.
    public mutating func received(_ output: SessionOutput) {
        switch output {
        case .identifierState(let state): tools.identifier.onState(state)
        case .toolbarState(let state): tools.speedSlider.sessionChanged(state.multiplierPct)
        default: break
        }
    }

    private func insertKeys(_ request: InsertDirectiveRequest, _ snapshot: SessionSnapshot) -> [String] {
        keyChoices(request, american: snapshot.settings?.americanKeys, european: snapshot.settings?.europeanKeys,
                   toolbar: snapshot.toolbar?.keyOptions)
    }

    private func checkCommand(_ request: InsertDirectiveRequest, _ form: DirectiveForm) -> BridgeCommand {
        .checkDirective(fields: .object(form.answer().mapValues { .string($0) }), kind: request.kind,
                        requestId: request.requestId)
    }
}

extension SessionSnapshot {
    /// The keys and the beat units the Insert dialog for `request` offers.
    public func insertChoices(_ request: InsertDirectiveRequest) -> (keys: [String], units: [Int]) {
        let keys = keyChoices(request, american: settings?.americanKeys, european: settings?.europeanKeys,
                              toolbar: toolbar?.keyOptions)
        let units = settings?.timeSignatureUnits.isEmpty == false ? settings!.timeSignatureUnits : defaultTimeUnits
        return (keys, units)
    }
}

/// The notes a greyed sheet control gives.
public enum SheetNotices {
    /// Edit voicings… opens Settings › Voicings on Android.
    public static let editVoicings = "Editing voicings comes with Settings, in a later version."
}
