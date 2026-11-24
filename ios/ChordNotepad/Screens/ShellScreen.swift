import ChordNotepadKit
import SwiftUI

/// What the shell's buttons do; nil in the preview catalog (inert buttons).
struct ShellActions {
    var playChord: () -> Void
    var selfTest: () -> Void
    var exportDiagnostics: () -> Void
}

/// The phase 1 shell (docs/IOS.md): the song's title, its text with the
/// chords highlighted, and the status line, all from a ``SessionSnapshot``.
/// The live app and the preview catalog draw the same view; the catalog
/// passes `scrolls: false`, since ImageRenderer can't draw a ScrollView.
struct ShellScreen: View {
    let snapshot: SessionSnapshot
    var phaseText: String? = nil
    var build: String = BuildInfo.current.line
    var scrolls = true
    var actions: ShellActions? = nil

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            editor
            Divider()
            statusLine
        }
        .background(Color(uiColor: .systemBackground))
    }

    private var title: String {
        snapshot.document?.displayName ?? "Chord Notepad"
    }

    private var header: some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                    .lineLimit(1)
                Text(snapshot.document.map { $0.isModified ? "Edited" : ($0.location ?? "") } ?? " ")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            Spacer(minLength: 8)
            button("Play chord", systemImage: "speaker.wave.2") { actions?.playChord() }
            button("Self-test", systemImage: "stethoscope") { actions?.selfTest() }
            button("Export diagnostics", systemImage: "square.and.arrow.up") { actions?.exportDiagnostics() }
        }
        .padding(.horizontal)
        .padding(.vertical, 10)
        .background(Color(uiColor: .secondarySystemBackground))
    }

    private func button(_ label: String, systemImage: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: systemImage)
                .imageScale(.large)
                .frame(minWidth: 44, minHeight: 44)
        }
        .accessibilityLabel(label)
        .disabled(actions == nil && scrolls)
    }

    @ViewBuilder
    private var editor: some View {
        let text = Text(highlighted)
            .font(.system(.body, design: .monospaced))
            .frame(maxWidth: .infinity, alignment: .topLeading)
            .padding()
        if scrolls {
            ScrollView { text.textSelection(.enabled) }
        } else {
            // The space left, with the text cut at its bottom: an oversized
            // child would otherwise push the header and status line out.
            Color.clear
                .overlay(alignment: .topLeading) {
                    text.fixedSize(horizontal: false, vertical: true)
                }
                .clipped()
        }
    }

    /// The text with the chord spans of the current highlight in the accent
    /// colour (spans are code points: ``OffsetMapper`` turns them into UTF-16).
    private var highlighted: AttributedString {
        guard !snapshot.text.isEmpty else {
            var placeholder = AttributedString("No song open")
            placeholder.foregroundColor = .secondary
            return placeholder
        }
        var attributed = AttributedString(snapshot.text)
        guard let highlight = snapshot.highlight, highlight.textRevision == snapshot.textRevision else {
            return attributed
        }
        let mapper = OffsetMapper(snapshot.text)
        for span in highlight.spans {
            let color: Color
            switch span.kind {
            case .chord: color = .accentColor
            case .chordInvalid, .directiveInvalid: color = .red
            case .directive, .directiveRedundant: color = .purple
            case .comment: color = .secondary
            }
            let start = mapper.toUTF16(span.start)
            let range = NSRange(location: start, length: max(0, mapper.toUTF16(span.end) - start))
            if let attributedRange = Range(range, in: attributed) {
                attributed[attributedRange].foregroundColor = color
            }
        }
        return attributed
    }

    private var statusLine: some View {
        VStack(alignment: .leading, spacing: 4) {
            if let message = snapshot.messages.last {
                Text(message)
                    .font(.footnote)
                    .foregroundStyle(.red)
                    .lineLimit(3)
            }
            HStack {
                Text(snapshot.status?.text ?? phaseText ?? "")
                    .font(.footnote)
                    .lineLimit(1)
                Spacer(minLength: 8)
                Text(build)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(Color(uiColor: .secondarySystemBackground))
    }
}

#Preview("Quick start") {
    ShellScreen(snapshot: PreviewCatalog.snapshot("quick_start_edit"), build: "preview")
}

#Preview("Errors, dark") {
    ShellScreen(snapshot: PreviewCatalog.snapshot("errors"), build: "preview")
        .preferredColorScheme(.dark)
}
