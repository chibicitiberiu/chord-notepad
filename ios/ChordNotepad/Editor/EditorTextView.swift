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

    /// The sideways scroll around the text view (``EditorHost``), if any.
    weak var host: EditorHost?

    /// Wrap at the view's width (keeping chords whole at `joinPoints`) or not
    /// at all: then the text view is as wide as the longest line, and its
    /// ``EditorHost`` scrolls it sideways.
    func setWordWrap(_ wrap: Bool, joinPoints points: [Int]) {
        let pointsChanged = points != joinPoints
        joinPoints = points
        breaks.points = wrap ? points : []
        if wrap != wordWrap {
            wordWrap = wrap
            container.widthTracksTextView = wrap
            if !wrap {
                container.size = CGSize(width: Self.unwrappedWidth, height: CGFloat.greatestFiniteMagnitude)
            } else {
                container.size = CGSize(width: max(bounds.width - Self.horizontalInset * 2, 1),
                                        height: CGFloat.greatestFiniteMagnitude)
            }
            host?.wrapChanged()
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

    /// The text or its attributes changed: the host measures the lines again.
    func textChanged() {
        host?.setNeedsLayout()
    }

    /// Unwrapped, the container is wide whatever UIKit did: it sizes the
    /// container to the view's frame even with `widthTracksTextView` off
    /// (563 pt in a 587 pt view in run 45366786133), and the text then wraps.
    func keepContainerUnwrapped() {
        guard !wordWrap else { return }
        if container.widthTracksTextView { container.widthTracksTextView = false }
        if container.size.width != Self.unwrappedWidth {
            container.size = CGSize(width: Self.unwrappedWidth, height: CGFloat.greatestFiniteMagnitude)
        }
    }

    override func layoutSubviews() {
        keepContainerUnwrapped()
        super.layoutSubviews()
    }

    /// The width the unwrapped text needs: its longest line and the insets.
    func unwrappedTextWidth() -> CGFloat {
        keepContainerUnwrapped()
        // The whole text, so a long line off screen counts too (TextKit lays out lazily).
        layout.ensureLayout(for: container)
        return ceil(layout.usedRect(for: container).maxX + textContainerInset.left + textContainerInset.right)
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

    /// Keep the sounding chord in view on both axes (the desktop's `see`):
    /// up and down in the text view, sideways in the host.
    func follow(_ range: UTF16Range) {
        host?.layoutIfNeeded()
        guard let rect = rect(of: range) else { return }
        let inset = adjustedContentInset
        var offset = contentOffset
        let visibleHeight = bounds.height - inset.top - inset.bottom
        if let y = TextScroll.followChord(start: Double(rect.minY), end: Double(rect.maxY),
                                          value: Double(offset.y + inset.top), viewport: Double(visibleHeight),
                                          max: Double(contentSize.height - visibleHeight)) {
            offset.y = CGFloat(y) - inset.top
        }
        if offset != contentOffset { setContentOffset(offset, animated: true) }
        if !wordWrap, let host {
            if let x = TextScroll.followChord(start: Double(rect.minX), end: Double(rect.maxX),
                                              value: Double(host.contentOffset.x), viewport: Double(host.bounds.width),
                                              max: Double(host.contentSize.width - host.bounds.width)) {
                host.setContentOffset(CGPoint(x: CGFloat(x), y: 0), animated: true)
            }
        }
    }

    /// Unwrapped: keep the caret in view sideways while typing or moving it
    /// (the text view follows it up and down itself).
    func followCaretSideways() {
        guard !wordWrap, let host else { return }
        // The text view must have its new width first, or a caret past the
        // old edge has nowhere to scroll to.
        host.layoutIfNeeded()
        guard let end = selectedTextRange?.end else { return }
        let caret = caretRect(for: end)
        guard caret.width.isFinite, caret.minX.isFinite else { return }
        if let x = TextScroll.followCursor(start: Double(caret.minX), end: Double(caret.maxX),
                                           value: Double(host.contentOffset.x), viewport: Double(host.bounds.width),
                                           max: Double(host.contentSize.width - host.bounds.width),
                                           margin: Double(Self.cursorMargin)) {
            host.setContentOffset(CGPoint(x: CGFloat(x), y: 0), animated: false)
        }
    }

    /// Whether the caret is inside the part of the text on screen (CI's check).
    var caretOnScreen: Bool {
        guard let end = selectedTextRange?.end else { return false }
        let caret = caretRect(for: end)
        let left = host?.contentOffset.x ?? 0
        let width = host?.bounds.width ?? bounds.width
        return caret.minX >= left && caret.maxX <= left + width
    }

    /// The text layout's state, for a failed check's message.
    var layoutDescription: String {
        "container \(container.size.width) pt (tracks \(container.widthTracksTextView)), used "
            + "\(layout.usedRect(for: container).width) pt, text view \(bounds.width) pt, "
            + "host \(host?.bounds.width ?? 0) pt showing x \(host?.contentOffset.x ?? 0) of "
            + "\(host?.contentSize.width ?? 0) pt, wrap \(wordWrap), TextKit 2 \(textLayoutManager != nil)"
    }

    /// Back to the top left (a document was opened).
    func scrollToStart() {
        setContentOffset(CGPoint(x: -adjustedContentInset.left, y: -adjustedContentInset.top), animated: false)
        host?.setContentOffset(.zero, animated: false)
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

/// What SwiftUI places: the editor's text view, either as wide as the host
/// (word wrap on) or as wide as its longest line inside this sideways scroll
/// (word wrap off, the default), as Android puts its field in a
/// `horizontalScroll`. The text view scrolls up and down itself and never
/// sees content wider than itself, so UIKit's own caret scrolling can't
/// undo the sideways offset (it kept resetting a wide text view's content
/// width to the view's, which put the offset back to 0).
final class EditorHost: UIScrollView {
    let textView = EditorTextView()

    init() {
        super.init(frame: .zero)
        contentInsetAdjustmentBehavior = .never
        isDirectionalLockEnabled = true
        alwaysBounceHorizontal = false
        alwaysBounceVertical = false
        showsVerticalScrollIndicator = false
        textView.host = self
        addSubview(textView)
        wrapChanged()
    }

    required init?(coder: NSCoder) {
        fatalError("EditorHost is made in code")
    }

    /// Word wrap was switched: only the unwrapped text scrolls sideways.
    func wrapChanged() {
        isScrollEnabled = !textView.wordWrap
        if textView.wordWrap { contentOffset = .zero }
        setNeedsLayout()
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        let width = textView.wordWrap ? bounds.width : max(bounds.width, textView.unwrappedTextWidth())
        let frame = CGRect(x: 0, y: 0, width: width, height: bounds.height)
        if textView.frame != frame {
            textView.frame = frame
            textView.keepContainerUnwrapped()
        }
        let size = CGSize(width: width, height: bounds.height)
        if contentSize != size { contentSize = size }
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
