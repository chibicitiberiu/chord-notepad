import ChordNotepadKit
import UIKit

/// The undo manager the editor's text view hands UIKit: its undo, redo and
/// "can undo" are the kit's history (``EditorModel``), so the Edit menu,
/// shake to undo, the three-finger gestures and the iPad's shortcut bar all
/// reach the same steps as the ribbon. UIKit still registers its own typing
/// actions here; they are never run, and only one level is kept.
final class EditorUndoManager: UndoManager {
    var canUndoNow: () -> Bool = { false }
    var canRedoNow: () -> Bool = { false }
    var onUndo: () -> Void = {}
    var onRedo: () -> Void = {}

    override init() {
        super.init()
        levelsOfUndo = 1
    }

    override var canUndo: Bool { canUndoNow() }
    override var canRedo: Bool { canRedoNow() }
    override func undo() { onUndo() }
    override func undoNestedGroup() { onUndo() }
    override func redo() { onRedo() }
}

/// The song's text view: TextKit 1 (its layout manager's delegate keeps
/// chords whole when the text wraps), no autocorrection or smart
/// punctuation, the editor's key commands, and sideways scrolling when word
/// wrap is off. It holds no state of its own: ``EditorController`` puts the
/// model's text, selection and styles in it.
final class EditorTextView: UITextView {
    /// The text's padding (Android's 12 × 8 dp).
    static let horizontalInset: CGFloat = 12
    static let verticalInset: CGFloat = 8
    /// How wide the text container is when lines don't wrap.
    static let unwrappedWidth: CGFloat = 100_000
    /// Room kept beside the caret when the unwrapped text follows it sideways.
    static let cursorMargin: CGFloat = 24

    let editorUndo = EditorUndoManager()
    /// A key command ran.
    var onAction: ((EditorAction) -> Void)?
    /// The text size or the colour scheme changed.
    var onTraitsChanged: (() -> Void)?

    // TextKit 1, built by hand: UITextView keeps only a weak reference to its
    // text storage, so the view keeps the stack.
    private let storage: NSTextStorage
    private let layout: NSLayoutManager
    private let container: NSTextContainer
    private let breaks = ChordBreaks()

    /// Lines wrap at the view's width; else they run on and the view scrolls sideways.
    private(set) var wordWrap = true
    /// Where a wrapped line may not break (UTF-16 offsets inside chords).
    private(set) var joinPoints: [Int] = []

    init() {
        storage = NSTextStorage()
        layout = NSLayoutManager()
        container = NSTextContainer(size: CGSize(width: 0, height: CGFloat.greatestFiniteMagnitude))
        storage.addLayoutManager(layout)
        layout.addTextContainer(container)
        super.init(frame: .zero, textContainer: container)
        layout.delegate = breaks
        container.lineFragmentPadding = 0
        container.widthTracksTextView = true
        textContainerInset = UIEdgeInsets(top: Self.verticalInset, left: Self.horizontalInset,
                                          bottom: Self.verticalInset, right: Self.horizontalInset)
        autocorrectionType = .no
        autocapitalizationType = .none
        spellCheckingType = .no
        smartQuotesType = .no
        smartDashesType = .no
        smartInsertDeleteType = .no
        inlinePredictionType = .no
        dataDetectorTypes = []
        keyboardDismissMode = .interactive
        alwaysBounceVertical = true
        adjustsFontForContentSizeCategory = false
        accessibilityIdentifier = "song-editor"
        setWordWrap(false, joinPoints: [])
    }

    required init?(coder: NSCoder) {
        fatalError("EditorTextView is made in code")
    }

    override var undoManager: UndoManager? { editorUndo }

    // MARK: - Wrapping

    /// Wrap at the view's width (keeping chords whole at `joinPoints`) or not at all.
    func setWordWrap(_ wrap: Bool, joinPoints points: [Int]) {
        let pointsChanged = points != joinPoints
        joinPoints = points
        breaks.points = wrap ? points : []
        if wrap != wordWrap {
            wordWrap = wrap
            container.widthTracksTextView = wrap
            if !wrap {
                container.size = CGSize(width: Self.unwrappedWidth, height: CGFloat.greatestFiniteMagnitude)
                showsHorizontalScrollIndicator = true
            } else {
                container.size = CGSize(width: max(bounds.width - Self.horizontalInset * 2, 1),
                                        height: CGFloat.greatestFiniteMagnitude)
                setContentOffset(CGPoint(x: -adjustedContentInset.left, y: contentOffset.y), animated: false)
            }
            invalidateTextLayout()
        } else if wrap && pointsChanged {
            invalidateTextLayout()
        }
    }

    private func invalidateTextLayout() {
        layout.invalidateLayout(forCharacterRange: NSRange(location: 0, length: storage.length),
                                actualCharacterRange: nil)
        textChanged()
    }

    /// The text or its attributes changed: unwrapped, the content's width is
    /// worked out again at the next layout.
    func textChanged() {
        contentWidthStale = true
        setNeedsLayout()
    }

    private var contentWidthStale = true
    private var measuredWidth: CGFloat = 0

    /// Unwrapped, the content is as wide as the longest line (UIKit keeps it
    /// at the view's width: it doesn't always go through the setter below,
    /// so the width is also put right after every layout).
    override var contentSize: CGSize {
        get { super.contentSize }
        set {
            var size = newValue
            if !wordWrap { size.width = unwrappedContentWidth() }
            super.contentSize = size
        }
    }

    private func unwrappedContentWidth() -> CGFloat {
        let used = layout.usedRect(for: container)
        return max(bounds.width - adjustedContentInset.left - adjustedContentInset.right,
                   ceil(used.maxX + textContainerInset.left + textContainerInset.right))
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        guard !wordWrap else { return }
        if container.widthTracksTextView || container.size.width < Self.unwrappedWidth {
            // UIKit sized the container to the view (it may on a frame change): unwrap again.
            container.widthTracksTextView = false
            container.size = CGSize(width: Self.unwrappedWidth, height: CGFloat.greatestFiniteMagnitude)
            contentWidthStale = true
        }
        if contentWidthStale || measuredWidth != bounds.width {
            // The whole text, so the longest line is measured even when it is
            // off screen (TextKit lays out lazily).
            layout.ensureLayout(for: container)
            contentWidthStale = false
            measuredWidth = bounds.width
        }
        let width = unwrappedContentWidth()
        if abs(super.contentSize.width - width) > 0.5 {
            super.contentSize = CGSize(width: width, height: super.contentSize.height)
        }
    }

    // MARK: - Following the caret and the sounding chord

    /// The rectangle of UTF-16 `range` in the content's coordinates (its first line).
    func rect(of range: UTF16Range) -> CGRect? {
        let length = storage.length
        guard range.start < range.end, range.end <= length else { return nil }
        let glyphs = layout.glyphRange(forCharacterRange: NSRange(location: range.start, length: range.length),
                                       actualCharacterRange: nil)
        var rect = layout.boundingRect(forGlyphRange: glyphs, in: container)
        rect.origin.x += textContainerInset.left
        rect.origin.y += textContainerInset.top
        return rect
    }

    /// Keep the sounding chord in view on both axes (the desktop's `see`).
    func follow(_ range: UTF16Range) {
        guard let rect = rect(of: range) else { return }
        let inset = adjustedContentInset
        var offset = contentOffset
        let visibleHeight = bounds.height - inset.top - inset.bottom
        if let y = TextScroll.followChord(start: Double(rect.minY), end: Double(rect.maxY),
                                          value: Double(offset.y + inset.top), viewport: Double(visibleHeight),
                                          max: Double(contentSize.height - visibleHeight)) {
            offset.y = CGFloat(y) - inset.top
        }
        if !wordWrap {
            let visibleWidth = bounds.width - inset.left - inset.right
            if let x = TextScroll.followChord(start: Double(rect.minX), end: Double(rect.maxX),
                                              value: Double(offset.x + inset.left), viewport: Double(visibleWidth),
                                              max: Double(contentSize.width - visibleWidth)) {
                offset.x = CGFloat(x) - inset.left
            }
        }
        if offset != contentOffset { setContentOffset(offset, animated: true) }
    }

    /// Unwrapped: keep the caret in view sideways while typing or moving it
    /// (UIKit follows it up and down).
    func followCaretSideways() {
        guard !wordWrap, let end = selectedTextRange?.end else { return }
        let caret = caretRect(for: end)
        guard caret.width.isFinite, caret.minX.isFinite else { return }
        let inset = adjustedContentInset
        let visibleWidth = bounds.width - inset.left - inset.right
        if let x = TextScroll.followCursor(start: Double(caret.minX), end: Double(caret.maxX),
                                           value: Double(contentOffset.x + inset.left),
                                           viewport: Double(visibleWidth),
                                           max: Double(contentSize.width - visibleWidth),
                                           margin: Double(Self.cursorMargin)) {
            setContentOffset(CGPoint(x: CGFloat(x) - inset.left, y: contentOffset.y), animated: false)
        }
    }

    /// The text layout's state, for a failed check's message.
    var layoutDescription: String {
        "container \(container.size.width) pt (tracks \(container.widthTracksTextView)), used "
            + "\(layout.usedRect(for: container).width) pt, content \(contentSize.width) pt, "
            + "view \(bounds.width) pt, wrap \(wordWrap), TextKit 2 \(textLayoutManager != nil)"
    }

    /// Back to the top left (a document was opened).
    func scrollToStart() {
        setContentOffset(CGPoint(x: -adjustedContentInset.left, y: -adjustedContentInset.top), animated: false)
    }

    // MARK: - Keys and traits

    override var keyCommands: [UIKeyCommand]? {
        let own = EditorKeyBinding.all.enumerated().map { index, binding -> UIKeyCommand in
            var flags: UIKeyModifierFlags = .command
            if binding.shift { flags.insert(.shift) }
            if binding.option { flags.insert(.alternate) }
            let input: String
            switch binding.input {
            case EditorKeyBinding.upArrow: input = UIKeyCommand.inputUpArrow
            case EditorKeyBinding.downArrow: input = UIKeyCommand.inputDownArrow
            default: input = binding.input
            }
            let command = UIKeyCommand(title: binding.title, action: #selector(runKeyCommand(_:)), input: input,
                                       modifierFlags: flags, propertyList: index)
            command.wantsPriorityOverSystemBehavior = true
            return command
        }
        return (super.keyCommands ?? []) + own
    }

    @objc private func runKeyCommand(_ command: UIKeyCommand) {
        guard let index = command.propertyList as? Int, EditorKeyBinding.all.indices.contains(index) else { return }
        onAction?(EditorKeyBinding.all[index].action)
    }

    override func traitCollectionDidChange(_ previous: UITraitCollection?) {
        super.traitCollectionDidChange(previous)
        if previous?.preferredContentSizeCategory != traitCollection.preferredContentSizeCategory
            || previous?.userInterfaceStyle != traitCollection.userInterfaceStyle {
            onTraitsChanged?()
        }
    }
}

/// The layout manager's delegate: no soft line break inside a chord
/// (`D/F#` stays whole), so the song never holds a word joiner.
private final class ChordBreaks: NSObject, NSLayoutManagerDelegate {
    var points: [Int] = []

    func layoutManager(_ layoutManager: NSLayoutManager,
                       shouldBreakLineByWordBeforeCharacterAt charIndex: Int) -> Bool {
        mayBreak(before: charIndex, points: points)
    }
}
