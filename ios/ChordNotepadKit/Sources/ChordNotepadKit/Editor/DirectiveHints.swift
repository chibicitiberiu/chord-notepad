import Foundation

// Play mode's directive explanation (Android's ui/editor/DirectiveHints.kt),
// as plain state for the Play slice: a long-press on a red or faded directive
// asks for it (`request_directive_hint`), and the reply shows in a small card
// by the directive until the next touch. There is no Edit-mode hint (Tibi
// found Android's strip distracting), so the editor itself doesn't use this.

/// What a directive hint shows: the `reason` (invalid, or has no effect; ""
/// for a valid directive), in the error colour when `error`, then the
/// `syntax`, one line per directive a half-typed keyword could become. Each
/// example in `syntax` is kept whole when the text wraps (its spaces are
/// non-breaking), with " · " between them.
public struct HintCard: Sendable, Equatable {
    public var reason: String
    public var error: Bool
    public var syntax: String

    public init(reason: String, error: Bool, syntax: String) {
        self.reason = reason
        self.error = error
        self.syntax = syntax
    }

    /// The card for `hint`; nil when there is no directive there.
    public static func of(_ hint: DirectiveHint) -> HintCard? {
        if hint.syntax.isEmpty { return nil }
        return HintCard(reason: hint.message, error: !hint.message.isEmpty && !hint.redundant,
                        syntax: wrapFriendly(hint.syntax))
    }

    /// `syntax` with every example's own spaces non-breaking.
    public static func wrapFriendly(_ syntax: String) -> String {
        syntax.split(separator: "\n", omittingEmptySubsequences: true)
            .map { line in
                line.components(separatedBy: separator)
                    .map { $0.replacingOccurrences(of: " ", with: "\u{00A0}") }
                    .joined(separator: separator)
            }
            .joined(separator: "\n")
    }

    private static let separator = " · "
}

/// A long-pressed directive's explanation: `card` for the directive at code
/// points `[start, end)`.
public struct ExplainedDirective: Sendable, Equatable {
    public var card: HintCard
    public var start: Int
    public var end: Int
}

/// The long-press explanation's state. Replies for an offset nobody is
/// waiting for any more are dropped; the last reply is kept and reused when
/// the same directive is explained again (the session doesn't repeat an
/// equal one).
public struct DirectiveHintState: Sendable, Equatable {
    /// The explanation shown, or nil.
    public private(set) var explained: ExplainedDirective?
    private var explaining: Int?
    private var last: DirectiveHint?

    public init() {}

    /// Explain the directive starting at code point `offset`; returns the
    /// command to send.
    public mutating func explain(_ offset: Int) -> BridgeCommand {
        explaining = offset
        if let last, last.offset == offset { show(last) }
        return .requestDirectiveHint(offset: offset)
    }

    /// Hide the explanation.
    public mutating func dismiss() {
        explaining = nil
        explained = nil
    }

    /// The session's reply to `request_directive_hint`.
    public mutating func receive(_ hint: DirectiveHint) {
        last = hint
        if hint.offset == explaining { show(hint) }
    }

    private mutating func show(_ hint: DirectiveHint) {
        guard let card = HintCard.of(hint), !card.reason.isEmpty else {
            explained = nil
            return
        }
        explained = ExplainedDirective(card: card, start: hint.start, end: hint.end)
    }

    /// Where the card's top goes, in the text's points: under the directive
    /// (`[anchorTop, anchorBottom]`) with a `gap`, or above it when it would
    /// run past the visible part's bottom and fits under its top.
    public static func cardTop(anchorTop: Double, anchorBottom: Double, cardHeight: Double, viewTop: Double,
                               viewBottom: Double, gap: Double) -> Double {
        let below = anchorBottom + gap
        let above = anchorTop - gap - cardHeight
        return below + cardHeight > viewBottom && above >= viewTop ? above : below
    }
}
