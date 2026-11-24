import ChordNotepadKit
import SwiftUI

/// What the shell's buttons do; nil in the preview catalog (inert buttons).
struct ShellActions {
    var playChord: () -> Void
    var selfTest: () -> Void
    var exportDiagnostics: () -> Void
    /// Play chord `index`, as a tap on it does.
    var audition: (Int) -> Void
    var submit: (BridgeCommand) -> Void
}

/// The phase 1 shell (docs/IOS.md): the song's title, the Edit ribbon, the
/// song editor, the chord sheet under it while it is shown, and the status
/// line, from a ``SessionSnapshot`` and the editor's ``EditorModel``. The
/// live app and the preview catalog draw the same view; the catalog passes
/// `scrolls: false`, since ImageRenderer can't draw UIKit views (the editor's
/// UITextView, the strip's UIScrollView): it gets ``EditorPreview``, the same
/// text and style runs in SwiftUI.
struct ShellScreen: View {
    let snapshot: SessionSnapshot
    /// The editor's text, selection and highlighting.
    var editorModel = EditorModel()
    /// The live editor (nil in the catalog).
    var editor: EditorController? = nil
    var phaseText: String? = nil
    var build: String = BuildInfo.current.line
    var scrolls = true
    var actions: ShellActions? = nil
    /// The chord sheet's buffers (the session's, or a fixture's); nil: no sheet.
    var chordSheet: ChordSheetSource? = nil

    var body: some View {
        GeometryReader { window in
            VStack(spacing: 0) {
                header
                Divider()
                EditRibbon(canUndo: editorModel.canUndo, canRedo: editorModel.canRedo,
                           notation: editorModel.notation, readOnly: editorModel.readOnly,
                           perform: ribbonAction)
                Divider()
                // The text, the chord sheet and the status line share what's left.
                GeometryReader { area in
                    VStack(spacing: 0) {
                        editorView
                        if let state = snapshot.chordSheet, state.visible, let chordSheet {
                            ChordSheetSplitView(state: state, source: chordSheet, available: area.size.height,
                                                window: window.size, interactive: scrolls,
                                                actions: chordSheetActions)
                        }
                        Divider()
                        statusLine
                    }
                }
            }
        }
        .background(Color(uiColor: .systemBackground))
    }

    private var chordSheetActions: ChordSheetActions? {
        guard let actions else { return nil }
        return ChordSheetActions(
            selectView: { actions.submit(.setChordSheetView(viewId: $0)) },
            zoom: { actions.submit(.chordSheetZoom(step: $0)) },
            audition: actions.audition,
            setHeight: { actions.submit(.setChordSheetHeight(px: $0)) })
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
            button(snapshot.chordSheet?.visible == true ? "Hide the chord sheet" : "Show the chord sheet",
                   systemImage: "rectangle.bottomhalf.inset.filled") {
                if let sheet = snapshot.chordSheet { actions?.submit(.setChordSheetVisible(visible: !sheet.visible)) }
            }
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

    /// The ribbon's buttons and the editor's key commands, through the live editor.
    private var ribbonAction: ((EditorAction) -> Void)? {
        guard let editor else { return nil }
        return { editor.perform($0) }
    }

    @ViewBuilder
    private var editorView: some View {
        if scrolls, let editor {
            SongEditor(controller: editor)
                .overlay(alignment: .topLeading) {
                    if editorModel.text.isEmpty { placeholder }
                }
        } else {
            EditorPreview(model: editorModel)
        }
    }

    /// The empty editor's "Type or paste a song here", never part of the text.
    private var placeholder: some View {
        Text(EditorPlaceholder.text)
            .font(.system(.body, design: .monospaced))
            .foregroundStyle(.secondary)
            .padding(.horizontal, EditorTextView.horizontalInset)
            .padding(.vertical, EditorTextView.verticalInset)
            .allowsHitTesting(false)
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

#Preview("Chord sheet") {
    ShellScreen(snapshot: PreviewCatalog.snapshot("play_with_chord_sheet"),
                editorModel: PreviewCatalog.editor("play_with_chord_sheet"), build: "preview", scrolls: false,
                chordSheet: PreviewCatalog.chordSheet("play_with_chord_sheet"))
}

#Preview("Quick start") {
    ShellScreen(snapshot: PreviewCatalog.snapshot("quick_start_edit"),
                editorModel: PreviewCatalog.editor("quick_start_edit"), build: "preview", scrolls: false)
}

#Preview("Editor mid-edit, dark") {
    ShellScreen(snapshot: PreviewCatalog.snapshot("editor_mid_edit"),
                editorModel: PreviewCatalog.editor("editor_mid_edit"), build: "preview", scrolls: false)
        .preferredColorScheme(.dark)
}
