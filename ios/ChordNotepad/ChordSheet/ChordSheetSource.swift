import ChordNotepadKit
import Foundation
import UIKit
import os

/// Where the chord sheet's buffers come from: the live session (the kit's
/// ``ChordSheetLoader``, which fetches on the bridge thread and decodes off
/// the main thread), or the buffers a fixture recorded (the preview catalog,
/// no Python). Also keeps each sheet's themed palettes.
@MainActor
final class ChordSheetSource: ObservableObject {
    /// The live buffer state; the recorded source answers ``sheetLoad(for:)`` instead.
    @Published private(set) var load = ChordSheetLoad()

    private let loader: ChordSheetLoader?
    private let recorded: Fixture?
    private var decoded: [Int: PreparedSheet?] = [:]
    private var palettes: [PaletteKey: ChordSheetPalette] = [:]
    private var reportedFirstSheet = false

    private struct PaletteKey: Hashable {
        let sheet: Int
        let dark: Bool
    }

    /// The live session's buffers.
    init(session: Session) {
        recorded = nil
        let loader = ChordSheetLoader { height in
            await session.chordSheetBuffer(height: height)
        }
        self.loader = loader
        loader.onChange = { [weak self] load in
            self?.apply(load)
        }
    }

    /// A fixture's recorded buffers.
    init(recorded fixture: Fixture?) {
        recorded = fixture
        loader = nil
    }

    /// Follow the newest request (live only; a recorded source has every height already).
    func follow(_ request: SheetRequest?) {
        loader?.follow(request)
    }

    /// What the strip shows for `request`: the live state, or the recorded
    /// buffer for its height (decoded once).
    func sheetLoad(for request: SheetRequest?) -> ChordSheetLoad {
        guard let recorded else { return load }
        guard let request else { return ChordSheetLoad() }
        if decoded[request.height] == nil {
            let outcome = SheetOutcome.decode(recorded.chordSheetBuffer(forHeight: request.height))
            if case .sheet(let sheet) = outcome {
                decoded[request.height] = sheet
            } else {
                decoded[request.height] = .some(nil)
            }
        }
        return ChordSheetLoad(sheet: decoded[request.height] ?? nil, request: request)
    }

    /// `sheet`'s colours in a theme, worked out once per sheet and theme.
    func palette(for sheet: PreparedSheet, colors: ChordSheetColors) -> ChordSheetPalette {
        let key = PaletteKey(sheet: sheet.id, dark: colors.dark)
        if let found = palettes[key] { return found }
        if palettes.count > 8 { palettes.removeAll() }
        let made = ChordSheetPalette(strings: sheet.buffer.strings, colors: colors)
        palettes[key] = made
        return made
    }

    private func apply(_ load: ChordSheetLoad) {
        self.load = load
        guard let sheet = load.sheet else {
            if let failure = load.failure { Log.ui.error("Chord sheet: \(failure, privacy: .public)") }
            return
        }
        let buffer = sheet.buffer
        Log.ui.info("Chord sheet \(buffer.viewId, privacy: .public) z=\(Double(buffer.zoom)) h=\(Double(buffer.height)): \(buffer.content.count)+\(buffer.lane.count) ops, \(buffer.slots.count) slots")
        if !reportedFirstSheet {
            // CI's live screenshot waits for this file (ios/tools/ci_screenshots.sh).
            reportedFirstSheet = true
            Diagnostics.shared.writeJSON(FirstSheetReport(buffer: buffer, fetches: loader?.fetchCount ?? 0),
                                         name: "chordsheet.json")
        }
    }
}

/// `Diagnostics/chordsheet.json`: the first buffer the live strip drew.
struct FirstSheetReport: Codable {
    var view: String
    var zoom: Double
    var height: Double
    var contentWidth: Double
    var contentOps: Int
    var laneOps: Int
    var gutterVariants: Int
    var slots: Int
    var fetches: Int

    init(buffer: SheetBuffer, fetches: Int) {
        view = buffer.viewId
        zoom = Double(buffer.zoom)
        height = Double(buffer.height)
        contentWidth = Double(buffer.contentWidth)
        contentOps = buffer.content.count
        laneOps = buffer.lane.count
        gutterVariants = buffer.gutterVariants.count
        slots = buffer.slots.count
        self.fetches = fetches
    }
}
