import ChordNotepadKit
import SwiftUI

/// The Edit ribbon under the header (Android's `ui/main/EditRibbon.kt`, one
/// 48 pt row): Undo, Redo | AB/Do, Convert. Android's Insert, Transpose, Capo
/// and Identify open sheets the iOS app doesn't have yet; they join the row
/// with them.
///
/// It sits at the top rather than above the keyboard (an
/// `inputAccessoryView`), as on Android: it stays put with a hardware
/// keyboard or none, and the preview catalog can draw it. The same view is
/// live and in the catalog (`perform` nil: inert).
struct EditRibbon: View {
    let canUndo: Bool
    let canRedo: Bool
    /// `american` or `european`; nil before the session says.
    let notation: String?
    var readOnly = false
    var perform: ((EditorAction) -> Void)?

    @Environment(\.colorScheme) private var colorScheme

    /// The ribbon's height (Android's `BAR_HEIGHT_DP`).
    static let height: CGFloat = 48

    var body: some View {
        let palette = EditorPalette.forScheme(dark: colorScheme == .dark)
        HStack(spacing: 1) {
            button("Undo", enabled: canUndo, action: .undo) {
                Image(systemName: "arrow.uturn.backward").foregroundStyle(RibbonTints.undo)
            }
            button("Redo", enabled: canRedo, action: .redo) {
                Image(systemName: "arrow.uturn.forward").foregroundStyle(RibbonTints.undo)
            }
            separator(palette)
            notationSegments(palette)
            button("Convert", enabled: !readOnly, action: .convertNotation) {
                ConvertIcon()
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 4)
        .frame(height: Self.height)
        .frame(maxWidth: .infinity)
        .background(palette.ribbon.swiftUI)
        // The captions follow the text size up to a point: the row is a fixed 48 pt.
        .dynamicTypeSize(...DynamicTypeSize.xLarge)
    }

    private func button<Icon: View>(_ label: String, enabled: Bool, action: EditorAction,
                                    @ViewBuilder icon: () -> Icon) -> some View {
        let palette = EditorPalette.forScheme(dark: colorScheme == .dark)
        return Button {
            perform?(action)
        } label: {
            VStack(spacing: 1) {
                icon()
                    .font(.system(size: 19, weight: .medium))
                    .frame(height: 24)
                Text(label)
                    .font(.caption2.weight(.medium))
                    .foregroundStyle(palette.ribbonText.swiftUI)
                    .lineLimit(1)
            }
            .padding(.horizontal, 6)
            .frame(minWidth: 44, minHeight: 44)
            .contentShape(RoundedRectangle(cornerRadius: 10))
        }
        .buttonStyle(.plain)
        .opacity(enabled ? 1 : 0.38)
        .disabled(!enabled || perform == nil)
        .accessibilityLabel(label)
    }

    private func separator(_ palette: EditorPalette) -> some View {
        palette.line.swiftUI
            .frame(width: 1, height: 28)
            .padding(.horizontal, 4)
    }

    /// AB | Do: the notation the text is read in.
    private func notationSegments(_ palette: EditorPalette) -> some View {
        HStack(spacing: 0) {
            ForEach(["american", "european"], id: \.self) { value in
                let on = notation == value
                let label = value == "american" ? "AB" : "Do"
                Button {
                    if !on { perform?(.setNotation(value)) }
                } label: {
                    Text(label)
                        .font(.footnote.weight(.medium))
                        .foregroundStyle((on ? palette.primary : palette.muted).swiftUI)
                        .padding(.horizontal, 9)
                        .frame(maxHeight: .infinity)
                        .background((on ? palette.primarySoft : palette.surfaceLow).swiftUI)
                }
                .buttonStyle(.plain)
                .disabled(perform == nil)
                .accessibilityLabel(value == "american" ? "American notation" : "European notation")
                .accessibilityAddTraits(on ? .isSelected : [])
            }
        }
        .frame(height: 30)
        .clipShape(Capsule())
        .overlay(Capsule().stroke(palette.line.swiftUI, lineWidth: 1))
        .padding(.horizontal, 2)
    }
}

/// Android's per-function icon tints (`IconTints`).
enum RibbonTints {
    static let undo = Color(.sRGB, red: 0x5C / 255, green: 0x6B / 255, blue: 0xC0 / 255)
    static let convertBlue = Color(.sRGB, red: 0x1E / 255, green: 0x88 / 255, blue: 0xE5 / 255)
    static let convertOrange = Color(.sRGB, red: 0xFB / 255, green: 0x8C / 255, blue: 0x00 / 255)
}

/// Convert's icon: a blue C with ↘ at the top left, an orange ↖ Do at the
/// bottom right (Android's `ConvertIcon`).
private struct ConvertIcon: View {
    var body: some View {
        ZStack(alignment: .topLeading) {
            Text("C")
                .font(.system(size: 13, weight: .bold))
                .foregroundStyle(RibbonTints.convertBlue)
                .offset(x: 2, y: -2)
            Image(systemName: "arrow.down.right")
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(RibbonTints.convertBlue)
                .offset(x: 13, y: 1)
            Image(systemName: "arrow.up.left")
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(RibbonTints.convertOrange)
                .offset(x: 2, y: 13)
            Text("Do")
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(RibbonTints.convertOrange)
                .offset(x: 12, y: 10)
        }
        .frame(width: 28, height: 24, alignment: .topLeading)
        .accessibilityHidden(true)
    }
}
