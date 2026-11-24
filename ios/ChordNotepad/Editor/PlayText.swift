import ChordNotepadKit
import UIKit
import UIKit.UIGestureRecognizerSubclass

// Play mode on the song editor's text view (Android's PlayText in
// ChordEditor.kt): the same view, frozen (not editable, not selectable, so
// nothing opens the keyboard), with the playhead marker before the
// playhead's chord. A tap on a chord moves the playhead there and plays it, a
// tap elsewhere moves it to the nearest chord (not while a song plays), a
// drag that starts on the marker scrubs it chord by chord, and a long-press
// on a red or faded directive explains it. The rules are the kit's
// (PlayheadGestures.swift); this file only measures and draws.

/// The marker's scrub: a pan that fails at once unless it starts on the
/// marker, so the text's own scrolling (which waits for it to fail) starts
/// without delay everywhere else, in Edit mode too.
final class MarkerScrub: UIPanGestureRecognizer {
    /// Whether a touch at this point (the text view's content) grabs the marker.
    var grabs: (CGPoint) -> Bool = { _ in false }
    /// Every touch that starts on the text (Play mode puts an explanation away).
    var touchDown: () -> Void = {}

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent) {
        super.touchesBegan(touches, with: event)
        touchDown()
        guard touches.count == 1, let view, let touch = touches.first, grabs(touch.location(in: view)) else {
            state = .failed
            return
        }
    }
}

/// Play mode's explanation of a long-pressed directive (Android's
/// `DirectiveHintCard`): the reason, in the error colour when it is one, then
/// the syntax in the monospaced font.
final class HintCardView: UIView {
    private let reason = UILabel()
    private let syntax = UILabel()
    private let stack = UIStackView()

    init() {
        super.init(frame: .zero)
        layer.cornerRadius = 12
        layer.shadowOpacity = 0.2
        layer.shadowRadius = 4
        layer.shadowOffset = CGSize(width: 0, height: 2)
        reason.numberOfLines = 2
        reason.font = UIFont.preferredFont(forTextStyle: .caption1)
        syntax.numberOfLines = 4
        syntax.font = UIFont.monospacedSystemFont(
            ofSize: UIFont.preferredFont(forTextStyle: .caption1).pointSize, weight: .regular)
        stack.axis = .vertical
        stack.spacing = 2
        stack.addArrangedSubview(reason)
        stack.addArrangedSubview(syntax)
        stack.isLayoutMarginsRelativeArrangement = true
        stack.directionalLayoutMargins = NSDirectionalEdgeInsets(top: 8, leading: 12, bottom: 8, trailing: 12)
        addSubview(stack)
        isAccessibilityElement = true
        accessibilityIdentifier = "hint-card"
    }

    required init?(coder: NSCoder) {
        fatalError("HintCardView is made in code")
    }

    func show(_ card: HintCard, colors: AppColors) {
        backgroundColor = colors.surfaceHigh.uiColor
        reason.text = card.reason
        reason.isHidden = card.reason.isEmpty
        reason.textColor = (card.error ? colors.error : colors.muted).uiColor
        syntax.text = card.syntax
        syntax.textColor = colors.muted.uiColor
        accessibilityLabel = [card.reason, card.syntax].filter { !$0.isEmpty }.joined(separator: ". ")
        UIAccessibility.post(notification: .announcement, argument: accessibilityLabel)
    }

    /// Its size for at most `width` points.
    func fit(width: CGFloat) -> CGSize {
        let size = stack.systemLayoutSizeFitting(CGSize(width: width, height: UIView.layoutFittingCompressedSize.height),
                                                 withHorizontalFittingPriority: .fittingSizeLevel,
                                                 verticalFittingPriority: .fittingSizeLevel)
        return CGSize(width: min(ceil(size.width), width), height: ceil(size.height))
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        stack.frame = bounds
    }
}

/// The handlers Play mode calls (the app model's commands); offsets UTF-16.
struct PlayHandlers {
    /// A tap's result: play the chord, or move the playhead to the nearest.
    var tap: (PlayTap) -> Void
    /// A scrub ended on the chord at this offset.
    var scrub: (Int) -> Void
    /// A long-press on the explainable directive starting at this offset.
    var explain: (Int) -> Void
    /// Any touch: put an explanation away.
    var touched: () -> Void
}

extension EditorTextView {
    /// Make the text frozen or editable again; `editable` is the session's
    /// read-only flag's opposite.
    func setPlayMode(_ on: Bool, editable: Bool) {
        playTap.isEnabled = on
        playHold.isEnabled = on
        markerLayer.isHidden = !on
        if on {
            if isFirstResponder { _ = resignFirstResponder() }
            isEditable = false
            isSelectable = false
        } else {
            isSelectable = true
            isEditable = editable
            hideHint()
        }
    }

    /// Draw the marker before `box` (nil: none).
    func showMarker(_ box: ChordBox?, color: UIColor) {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        markerLayer.fillColor = color.cgColor
        markerLayer.path = box.map { PlayheadMarker(before: $0).path }
        CATransaction.commit()
    }

    /// Show `card` by the directive in `rect` (content coordinates): under
    /// it, or above it near the bottom of what's in view.
    func showHint(_ card: HintCard, at rect: CGRect, colors: AppColors) {
        let view = hintCard ?? HintCardView()
        if hintCard == nil {
            hintCard = view
            addSubview(view)
        }
        view.show(card, colors: colors)
        let visibleLeft = host?.contentOffset.x ?? 0
        let visibleWidth = host?.bounds.width ?? bounds.width
        let margin: CGFloat = 8
        let size = view.fit(width: min(340, visibleWidth - 2 * margin))
        let top = DirectiveHintState.cardTop(anchorTop: Double(rect.minY), anchorBottom: Double(rect.maxY),
                                             cardHeight: Double(size.height), viewTop: Double(contentOffset.y),
                                             viewBottom: Double(contentOffset.y + bounds.height), gap: 6)
        let left = min(max(rect.minX, visibleLeft + margin), visibleLeft + visibleWidth - size.width - margin)
        view.frame = CGRect(x: left, y: CGFloat(top), width: size.width, height: size.height)
        view.isHidden = false
    }

    func hideHint() {
        hintCard?.isHidden = true
    }

    /// The boxes of `spans` (UTF-16) in the content's coordinates.
    func boxes(of spans: [PaintedSpan]) -> [ChordBox] {
        spans.compactMap { span in
            rect(of: UTF16Range(span.start, span.end)).map {
                ChordBox(span.start, span.end, left: Double($0.minX), top: Double($0.minY), right: Double($0.maxX),
                         bottom: Double($0.maxY))
            }
        }
    }
}
