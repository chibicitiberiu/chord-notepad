import Foundation

/// The song editor's undo history, kept by the view as on every other front
/// end: the session has no undo command, its `TextEdited.undo` only says how
/// a session edit goes into the view's history (Android folds it into
/// `TextFieldState`'s history, the Qt desktop into `QTextDocument`'s).
///
/// - The user's typing is merged into one step per run: insertions that
///   continue where the last one ended, and deletions that continue a run of
///   Backspace or forward Delete. A new line, a move of the caret or any
///   other edit starts a new step.
/// - A session edit with `group` or `plain` is one step of its own, never
///   merged (Android: `plain` is "close enough" to `group`); `reset` clears
///   the history (a document was opened).
/// - Each step restores the selection it had before (undo) or after (redo).
public struct EditHistory: Sendable, Equatable {
    /// How many steps undo keeps.
    public static let limit = 500

    /// One replaced range: `old` at UTF-16 offset `start` became `new`.
    public struct Replacement: Sendable, Equatable {
        public var start: Int
        public var old: String
        public var new: String

        public init(start: Int, old: String, new: String) {
            self.start = start
            self.old = old
            self.new = new
        }

        var oldRange: UTF16Range { UTF16Range(start, start + old.utf16.count) }
        var newRange: UTF16Range { UTF16Range(start, start + new.utf16.count) }
    }

    /// One undo step: its replacements in the order they were made (each in
    /// the text the previous one left), and the selection around them.
    public struct Step: Sendable, Equatable {
        public var replacements: [Replacement]
        public var selectionBefore: UTF16Range
        public var selectionAfter: UTF16Range
        /// What later typing may merge into (nil: nothing).
        var run: Run?
    }

    enum Run: Sendable, Equatable {
        case inserting, deleting
    }

    public private(set) var undoSteps: [Step] = []
    public private(set) var redoSteps: [Step] = []

    public init() {}

    public var canUndo: Bool { !undoSteps.isEmpty }
    public var canRedo: Bool { !redoSteps.isEmpty }

    /// The user's edit: merged into the last step when it continues its run.
    public mutating func recordTyping(_ r: Replacement, before: UTF16Range, after: UTF16Range) {
        redoSteps.removeAll()
        let run = Self.run(of: r)
        if let run, var last = undoSteps.last, last.run == run, last.replacements.count == 1,
           let merged = Self.merge(last.replacements[0], r, run) {
            last.replacements[0] = merged
            last.selectionAfter = after
            undoSteps[undoSteps.count - 1] = last
            return
        }
        push(Step(replacements: [r], selectionBefore: before, selectionAfter: after, run: run))
    }

    /// An edit that is a step of its own (a session edit, a composed word).
    public mutating func recordStep(_ replacements: [Replacement], before: UTF16Range, after: UTF16Range) {
        guard !replacements.isEmpty else { return }
        redoSteps.removeAll()
        push(Step(replacements: replacements, selectionBefore: before, selectionAfter: after, run: nil))
    }

    /// Later typing starts a new step (the caret moved).
    public mutating func seal() {
        guard var last = undoSteps.last, last.run != nil else { return }
        last.run = nil
        undoSteps[undoSteps.count - 1] = last
    }

    /// Forget everything (a document was opened).
    public mutating func clear() {
        undoSteps.removeAll()
        redoSteps.removeAll()
    }

    /// The step to undo, moved to the redo list.
    public mutating func popUndo() -> Step? {
        guard var step = undoSteps.popLast() else { return nil }
        step.run = nil
        redoSteps.append(step)
        return step
    }

    /// The step to redo, moved back to the undo list.
    public mutating func popRedo() -> Step? {
        guard let step = redoSteps.popLast() else { return nil }
        undoSteps.append(step)
        return step
    }

    private mutating func push(_ step: Step) {
        // A new step ends the last one's run.
        if let index = undoSteps.indices.last { undoSteps[index].run = nil }
        undoSteps.append(step)
        if undoSteps.count > Self.limit { undoSteps.removeFirst(undoSteps.count - Self.limit) }
    }

    /// Typing that can continue a run: an insertion without a line break, or
    /// a deletion within a line.
    private static func run(of r: Replacement) -> Run? {
        if r.old.isEmpty && !r.new.isEmpty && !r.new.contains(where: \.isNewline) { return .inserting }
        if r.new.isEmpty && !r.old.isEmpty && !r.old.contains(where: \.isNewline) { return .deleting }
        return nil
    }

    /// `last` with `next` added when `next` continues it.
    private static func merge(_ last: Replacement, _ next: Replacement, _ run: Run) -> Replacement? {
        switch run {
        case .inserting:
            guard last.newRange.end == next.start else { return nil }
            return Replacement(start: last.start, old: "", new: last.new + next.new)
        case .deleting:
            if next.oldRange.end == last.start {  // Backspace
                return Replacement(start: next.start, old: next.old + last.old, new: "")
            }
            if next.start == last.start {  // forward Delete
                return Replacement(start: last.start, old: last.old + next.old, new: "")
            }
            return nil
        }
    }
}
