import ChordNotepadKit
import SwiftUI
import UIKit

extension PlayheadMarker {
    /// The marker as one path: the bar with rounded ends and the triangle.
    var path: CGPath {
        let path = CGMutablePath()
        let rect = CGRect(x: bar.x, y: bar.y, width: bar.width, height: bar.height)
        path.addRoundedRect(in: rect, cornerWidth: bar.width / 2, cornerHeight: min(bar.width / 2, rect.height / 2))
        if let first = triangle.first {
            path.move(to: CGPoint(x: first.x, y: first.y))
            for point in triangle.dropFirst() { path.addLine(to: CGPoint(x: point.x, y: point.y)) }
            path.closeSubpath()
        }
        return path
    }
}

/// The song text laid out by TextKit 1 off screen, the way the live
/// ``EditorTextView`` lays it out (same storage attributes, container width,
/// line breaking and insets), so the catalog draws the same text and puts the
/// playhead marker where the live view does.
final class SongTextLayout {
    let storage = NSTextStorage()
    let layout = NSLayoutManager()
    let container: NSTextContainer
    private let breaks = ChordBreaks()

    init(model: EditorModel, font: UIFont, palette: EditorPalette, width: CGFloat, selection: Bool) {
        let wrap = model.wordWrap
        container = NSTextContainer(size: CGSize(
            width: wrap ? max(width - EditorTextView.horizontalInset * 2, 1) : EditorTextView.unwrappedWidth,
            height: CGFloat.greatestFiniteMagnitude))
        container.lineFragmentPadding = 0
        storage.addLayoutManager(layout)
        layout.addTextContainer(container)
        breaks.points = wrap ? model.joinPoints : []
        layout.delegate = breaks
        storage.replaceCharacters(in: NSRange(location: 0, length: 0), with: model.text)
        EditorAppearance.paint(model.styleRuns(palette), on: storage, font: font, palette: palette)
        // The find bar's current match shows in its own tint (the live text view, without the keys, draws no
        // selection while the find field has them).
        let findCurrent = model.findPaint?.current == model.selection
        if selection, !findCurrent, !model.selection.isEmpty, model.selection.end <= storage.length {
            storage.addAttribute(.backgroundColor,
                                 value: palette.primary.withAlpha(EditorPalette.selectionAlpha).uiColor,
                                 range: NSRange(location: model.selection.start, length: model.selection.length))
        }
        layout.ensureLayout(for: container)
    }

    /// Where the text starts in the view (the text view's insets).
    static let origin = CGPoint(x: EditorTextView.horizontalInset, y: EditorTextView.verticalInset)

    /// UTF-16 `range`'s box in the view (its first line), as the live view's `rect(of:)`.
    func rect(of range: UTF16Range) -> CGRect? {
        guard range.start < range.end, range.end <= storage.length else { return nil }
        let glyphs = layout.glyphRange(forCharacterRange: NSRange(location: range.start, length: range.length),
                                       actualCharacterRange: nil)
        return layout.boundingRect(forGlyphRange: glyphs, in: container)
            .offsetBy(dx: Self.origin.x, dy: Self.origin.y)
    }

    /// Draw the text (backgrounds, then glyphs and underlines) into the current UIKit context.
    func draw() {
        let glyphs = layout.glyphRange(for: container)
        layout.drawBackground(forGlyphRange: glyphs, at: Self.origin)
        layout.drawGlyphs(forGlyphRange: glyphs, at: Self.origin)
    }
}

/// The catalog's drawing of the song text: the editor's model laid out and
/// drawn by TextKit 1 as the live text view does (ImageRenderer can't draw
/// UIKit views, but it draws a `Canvas`), with the playhead marker in Play
/// mode. Unwrapped lines run past the right edge, as the live view shows them
/// before it is scrolled sideways.
struct EditorPreview: View {
    let model: EditorModel
    /// Play mode: the session's playhead (UTF-16); the marker sits before its chord.
    var playhead: Int?
    var play = false
    @Environment(\.colorScheme) private var colorScheme
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize

    var body: some View {
        let palette = EditorPalette.forScheme(dark: colorScheme == .dark)
        let font = EditorAppearance.font(kind: model.fontKind, points: model.fontPoints,
                                         category: EditorAppearance.category(dynamicTypeSize))
        palette.background.swiftUI
            .overlay(alignment: .topLeading) {
                if model.text.isEmpty {
                    Text(EditorPlaceholder.text)
                        .font(Font(font as CTFont))
                        .foregroundColor(palette.text.withAlpha(EditorPalette.placeholderAlpha).swiftUI)
                        .padding(.horizontal, EditorTextView.horizontalInset)
                        .padding(.vertical, EditorTextView.verticalInset)
                } else {
                    Canvas { context, size in
                        let text = SongTextLayout(model: model, font: font, palette: palette, width: size.width,
                                                  selection: !play)
                        context.withCGContext { cg in
                            UIGraphicsPushContext(cg)
                            text.draw()
                            UIGraphicsPopContext()
                        }
                        if play, let box = previewMarkerBox(text, model: model, playhead: playhead) {
                            context.fill(Path(PlayheadMarker(before: box).path), with: .color(palette.primary.swiftUI))
                        }
                    }
                }
            }
            .clipped()
    }
}

/// The marker's chord in the catalog's layout.
private func previewMarkerBox(_ text: SongTextLayout, model: EditorModel, playhead: Int?) -> ChordBox? {
    guard let chord = markerChord(playableChords(model.spans), playhead: playhead),
          let rect = text.rect(of: UTF16Range(chord.start, chord.end)) else { return nil }
    return ChordBox(chord.start, chord.end, left: Double(rect.minX), top: Double(rect.minY),
                    right: Double(rect.maxX), bottom: Double(rect.maxY))
}
