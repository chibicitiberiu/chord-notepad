import Foundation

// Find and Replace, from the Qt desktop's find bar (desktop/chordnotepad_desktop/
// find_bar.py and qml/app/FindBar.qml): Android has none. The matching is the
// core's `text_ops.find_all` and `next_match` (session/text_ops.py) done in
// Swift, character for character as Python's `re` does it (the tables in
// Generated/PythonText.swift), because the session's `replace_match` checks
// the span again with `find_all` and leaves a span it doesn't call a match.
// The replacements are the session's `replace_match` and `replace_all`: one
// undo step each, refused while a song plays, "Replaced 3 matches" in the status.

/// A match: code points `[start, end)` of the text.
public struct FindSpan: Sendable, Hashable, CustomStringConvertible {
    public var start: Int
    public var end: Int

    public init(_ start: Int, _ end: Int) {
        self.start = start
        self.end = end
    }

    public var description: String { "[\(start), \(end))" }
}

/// `text_ops.find_all` and `next_match` (Python's `re` with a literal
/// pattern), and the bar's texts.
public enum TextFind {
    public static let wrappedDown = "Continued from the top"
    public static let wrappedUp = "Continued from the bottom"
    public static let noMatches = "No matches"
    /// How long the wrap-around notice shows, in seconds (the desktop's 2000 ms).
    public static let noticeSeconds = 2.0

    /// What the bar says about the matches: "" for no query, "No matches",
    /// "3 of 7" when the selection is the third, else "7 matches".
    public static func countText(query: String, count: Int, current: Int) -> String {
        if query.isEmpty { return "" }
        if count == 0 { return noMatches }
        if current > 0 { return "\(current) of \(count)" }
        return "\(count) match" + (count == 1 ? "" : "es")
    }

    /// Every match of `query` in `text`, in order, not overlapping (code
    /// points). Ignores case unless `matchCase`; with `wholeWord` a match has
    /// no word character (`\w`) right before or after it. An empty query
    /// matches nothing.
    public static func findAll(_ text: String, query: String, matchCase: Bool, wholeWord: Bool) -> [FindSpan] {
        findAll(scalars: text.unicodeScalars.map(\.value), query: query, matchCase: matchCase, wholeWord: wholeWord)
    }

    static func findAll(scalars text: [UInt32], query: String, matchCase: Bool, wholeWord: Bool) -> [FindSpan] {
        let pattern = query.unicodeScalars.map { PatternChar($0.value, ignoreCase: !matchCase) }
        let n = pattern.count
        guard n > 0, n <= text.count else { return [] }
        var out: [FindSpan] = []
        var i = 0
        while i + n <= text.count {
            var hit = true
            for k in 0..<n where !pattern[k].matches(text[i + k]) {
                hit = false
                break
            }
            if hit && wholeWord {
                if i > 0 && isWord(text[i - 1]) { hit = false }
                if i + n < text.count && isWord(text[i + n]) { hit = false }
            }
            if hit {
                out.append(FindSpan(i, i + n))
                i += n
            } else {
                i += 1
            }
        }
        return out
    }

    /// The match to go to from `position`, and whether the search wrapped
    /// around the end (or the start, going back). Forward: the first match
    /// starting at or after `position`; backward: the last one ending at or
    /// before it. Nil without matches.
    public static func nextMatch(_ matches: [FindSpan], position: Int, backward: Bool = false)
        -> (index: Int, wrapped: Bool)? {
        guard !matches.isEmpty else { return nil }
        if backward {
            if let i = matches.lastIndex(where: { $0.end <= position }) { return (i, false) }
            return (matches.count - 1, true)
        }
        if let i = matches.firstIndex(where: { $0.start >= position }) { return (i, false) }
        return (0, true)
    }

    // MARK: - Python's `re`, character by character

    /// One character of the pattern as `sre_compile` makes it: an uncased
    /// character matches only itself; a cased one, ignoring case, matches a
    /// character whose lowercase is its lowercase or one of `_EXTRA_CASES`.
    struct PatternChar {
        let exact: UInt32
        let folded: [UInt32]?

        init(_ c: UInt32, ignoreCase: Bool) {
            exact = c
            if ignoreCase && TextFind.isCased(c) {
                let lo = TextFind.lower(c)
                folded = [lo] + (pythonExtraCases[lo] ?? [])
            } else {
                folded = nil
            }
        }

        func matches(_ t: UInt32) -> Bool {
            guard let folded else { return t == exact }
            let lo = TextFind.lower(t)
            return folded.contains(lo)
        }
    }

    /// `_sre.unicode_tolower`: the simple lowercase.
    static func lower(_ c: UInt32) -> UInt32 {
        var lo = 0
        var hi = pythonLowerPairs.count / 2
        while lo < hi {
            let mid = (lo + hi) >> 1
            let key = pythonLowerPairs[mid * 2]
            if key == c { return pythonLowerPairs[mid * 2 + 1] }
            if key < c { lo = mid + 1 } else { hi = mid }
        }
        return c
    }

    /// `_sre.unicode_iscased`.
    static func isCased(_ c: UInt32) -> Bool { inRanges(pythonCasedRanges, c) }

    /// `\w` in a str pattern: `str.isalnum()` or `_`.
    static func isWord(_ c: UInt32) -> Bool { inRanges(pythonWordRanges, c) }

    private static func inRanges(_ ranges: [UInt32], _ c: UInt32) -> Bool {
        var lo = 0
        var hi = ranges.count / 2
        while lo < hi {
            let mid = (lo + hi) >> 1
            if ranges[mid * 2 + 1] < c {
                lo = mid + 1
            } else if ranges[mid * 2] > c {
                hi = mid
            } else {
                return true
            }
        }
        return false
    }
}

/// What the find bar's controls do (the desktop's `FindModel` slots).
public enum FindAction: Sendable, Hashable {
    /// Command-F (`replace` false) or Option-Command-F, the ribbon's Find:
    /// the bar opens (again), the search starts from the selection, a
    /// one-line selection becomes the query.
    case open(replace: Bool)
    /// The ✕, Escape: no tints; the query stays for Command-G.
    case close
    case query(String)
    case replacement(String)
    /// Return, ▼; Shift-Return, ▲.
    case next, previous
    /// Command-G, Shift-Command-G: the last query again, the bar open or not
    /// (with no query yet the bar opens).
    case again(backward: Bool)
    case matchCase(Bool), wholeWord(Bool)
    /// The ▸ / ▾ at the bar's start: the Replace row.
    case showReplace(Bool)
    case replace, replaceAll
    /// The wrap-around notice's time is up.
    case clearNotice
}

/// The find bar's state (the desktop's `FindModel`), part of ``EditorModel``
/// so its matches are painted with the text. Matches are code points of the
/// editor's text.
public struct FindBar: Sendable, Equatable {
    public internal(set) var open = false
    /// The Replace row is shown.
    public internal(set) var replacing = false
    /// Replace is offered (Edit mode, a writable song); Play finds only.
    public internal(set) var canReplace = true
    public internal(set) var query = ""
    public internal(set) var replacement = ""
    public internal(set) var matchCase = false
    public internal(set) var wholeWord = false
    public internal(set) var matches: [FindSpan] = []
    /// Which match the selection is (1-based), or 0.
    public internal(set) var current = 0
    /// "Continued from the top" for a moment after a search wrapped around.
    public internal(set) var notice: String?
    /// Where the typed search starts (code points).
    var origin = 0
    /// A Replace was sent: the next match is selected once the session's
    /// edit (or its refusal) is in.
    var advancing = false

    public init() {}

    /// "3 of 7", "7 matches", "No matches" or "".
    public var countText: String { TextFind.countText(query: query, count: matches.count, current: current) }
    /// A query that matches nothing (the bar says so in red).
    public var noMatch: Bool { !query.isEmpty && matches.isEmpty }
    /// Next, previous, Replace and Replace all work.
    public var hasMatches: Bool { !matches.isEmpty }

    /// The catalog's bar: open with `query` (and `replacement` when replacing)
    /// over `editor`'s text, the selection on match `current` (1-based; 0 none).
    public static func showing(_ editor: EditorModel, query: String, replacement: String? = nil,
                               current: Int = 1, canReplace: Bool = true, matchCase: Bool = false,
                               wholeWord: Bool = false) -> FindBar {
        var bar = FindBar()
        bar.open = true
        bar.canReplace = canReplace
        bar.replacing = replacement != nil && canReplace
        bar.replacement = replacement ?? ""
        bar.query = query
        bar.matchCase = matchCase
        bar.wholeWord = wholeWord
        bar.matches = TextFind.findAll(editor.text, query: query, matchCase: matchCase, wholeWord: wholeWord)
        bar.current = min(max(current, 0), bar.matches.count)
        return bar
    }
}

/// The matches as the editor paints them: UTF-16 ranges, and the current one.
public struct FindPaint: Sendable, Equatable {
    public var matches: [UTF16Range]
    public var current: UTF16Range?

    public init(matches: [UTF16Range], current: UTF16Range?) {
        self.matches = matches
        self.current = current
    }
}

extension EditorModel {
    /// The matches to tint while the bar is open (nil when it is closed).
    public var findPaint: FindPaint? {
        guard find.open, !find.matches.isEmpty else { return nil }
        let mapper = OffsetMapper(text)
        let ranges = find.matches.map { UTF16Range(mapper.toUTF16($0.start), mapper.toUTF16($0.end)) }
        let current = find.current > 0 && find.current <= ranges.count ? ranges[find.current - 1] : nil
        return FindPaint(matches: ranges, current: current)
    }

    /// Run one of the find bar's actions. `canReplace`: Replace is offered
    /// (Edit mode); read when the bar opens.
    public mutating func find(_ action: FindAction, canReplace: Bool = true) -> EditorEffects {
        var effects = EditorEffects()
        switch action {
        case .open(let replace):
            let mapper = OffsetMapper(text)
            find.origin = mapper.toCodePoint(selection.start)
            find.open = true
            find.canReplace = canReplace && !readOnly
            find.replacing = replace && find.canReplace
            find.notice = nil
            find.advancing = false
            let selected = UTF16Text.substring(text, selection)
            searchFind()
            updateFindCurrent()
            if !selected.isEmpty && !selected.contains("\n") {
                effects.merge(setFindQuery(selected))
            }
        case .close:
            if find.open {
                find.open = false
                find.notice = nil
                find.advancing = false
            }
        case .query(let query):
            effects.merge(setFindQuery(query))
        case .replacement(let text):
            find.replacement = text
        case .next:
            effects.merge(findStep(backward: false))
        case .previous:
            effects.merge(findStep(backward: true))
        case .again(let backward):
            if find.query.isEmpty {
                return self.find(.open(replace: false), canReplace: canReplace)
            }
            searchFind()
            effects.merge(findStep(backward: backward))
        case .matchCase(let on):
            if on != find.matchCase {
                find.matchCase = on
                effects.merge(findOptionsChanged())
            }
        case .wholeWord(let on):
            if on != find.wholeWord {
                find.wholeWord = on
                effects.merge(findOptionsChanged())
            }
        case .showReplace(let on):
            find.replacing = on && find.canReplace
        case .replace:
            guard find.canReplace, !readOnly else { break }
            searchFind()
            updateFindCurrent()
            if find.current == 0 {
                effects.merge(findStep(backward: false))
            } else {
                let span = find.matches[find.current - 1]
                find.advancing = true
                effects.commands = syncCommands() + [
                    .replaceMatch(matchCase: find.matchCase, query: find.query, replacement: find.replacement,
                                  span: Selection(start: span.start, end: span.end), wholeWord: find.wholeWord),
                ]
            }
        case .replaceAll:
            guard find.canReplace, !readOnly, !find.query.isEmpty else { break }
            effects.commands = syncCommands() + [
                .replaceAll(cursor: cursorCodePoint, matchCase: find.matchCase, query: find.query,
                            replacement: find.replacement, wholeWord: find.wholeWord),
            ]
        case .clearNotice:
            find.notice = nil
        }
        effects.restyle = true
        return effects
    }

    private mutating func setFindQuery(_ query: String) -> EditorEffects {
        var effects = EditorEffects()
        guard query != find.query else { return effects }
        find.query = query
        searchFind()
        if !query.isEmpty {
            if let found = TextFind.nextMatch(find.matches, position: find.origin) {
                effects.merge(goToMatch(found, backward: false))
            } else {
                let caret = OffsetMapper(text).toUTF16(find.origin)
                effects.merge(select(UTF16Range(caret: caret)))
            }
        }
        updateFindCurrent()
        return effects
    }

    private mutating func findStep(backward: Bool) -> EditorEffects {
        var effects = EditorEffects()
        guard !find.matches.isEmpty else { return effects }
        let mapper = OffsetMapper(text)
        let position = mapper.toCodePoint(backward ? selection.start : selection.end)
        if let found = TextFind.nextMatch(find.matches, position: position, backward: backward) {
            effects.merge(goToMatch(found, backward: backward))
            find.origin = find.matches[found.index].start
        }
        updateFindCurrent()
        return effects
    }

    private mutating func findOptionsChanged() -> EditorEffects {
        var effects = EditorEffects()
        searchFind()
        if !find.query.isEmpty, !find.matches.isEmpty,
           let found = TextFind.nextMatch(find.matches, position: OffsetMapper(text).toCodePoint(selection.start)) {
            effects.merge(goToMatch(found, backward: false))
        }
        updateFindCurrent()
        return effects
    }

    private mutating func goToMatch(_ found: (index: Int, wrapped: Bool), backward: Bool) -> EditorEffects {
        let span = find.matches[found.index]
        let mapper = OffsetMapper(text)
        var effects = select(UTF16Range(mapper.toUTF16(span.start), mapper.toUTF16(span.end)))
        effects.findMoved = true
        if found.wrapped {
            find.notice = backward ? TextFind.wrappedUp : TextFind.wrappedDown
            effects.findNotice = true
        }
        return effects
    }

    mutating func searchFind() {
        find.matches = TextFind.findAll(text, query: find.query, matchCase: find.matchCase, wholeWord: find.wholeWord)
        if find.current > find.matches.count { find.current = 0 }
    }

    mutating func updateFindCurrent() {
        guard selection.start < selection.end else {
            find.current = 0
            return
        }
        let mapper = OffsetMapper(text)
        let span = FindSpan(mapper.toCodePoint(selection.start), mapper.toCodePoint(selection.end))
        find.current = (find.matches.firstIndex(of: span) ?? -1) + 1
    }

    /// The text changed (typing, the session's edits, undo): search again
    /// while there's something to show.
    mutating func findTextChanged() {
        guard !find.query.isEmpty, find.open || !find.matches.isEmpty else { return }
        searchFind()
        updateFindCurrent()
    }

    /// The selection moved: which match it is now.
    mutating func findSelectionMoved() {
        if !find.query.isEmpty { updateFindCurrent() }
    }

    /// A Replace's edit is in (or was refused): on to the next match after
    /// the caret, as the desktop's `_after_replace`.
    mutating func findAdvanceAfterReplace() -> EditorEffects {
        guard find.advancing else { return EditorEffects() }
        find.advancing = false
        var effects = EditorEffects()
        searchFind()
        if !find.matches.isEmpty,
           let found = TextFind.nextMatch(find.matches, position: OffsetMapper(text).toCodePoint(selection.end)) {
            effects.merge(goToMatch(found, backward: false))
        }
        updateFindCurrent()
        effects.restyle = true
        return effects
    }
}
