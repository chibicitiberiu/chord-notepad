import SwiftUI
import UIKit

/// The live shell: ``ShellScreen`` over the app's session, with the
/// self-test sheet and the diagnostics export.
struct ShellView: View {
    @ObservedObject var model: AppModel
    /// The model's editor, observed for the ribbon (undo, redo, notation).
    @ObservedObject var editor: EditorController
    @State private var shareItem: ShareItem?
    @State private var exportError: String?

    var body: some View {
        ShellScreen(snapshot: model.snapshot, editorModel: editor.model, editor: editor, phaseText: model.phaseText,
                    actions: ShellActions(playChord: { model.audition(index: 0) },
                                          selfTest: { model.showSelfTest = true },
                                          exportDiagnostics: export,
                                          audition: { model.audition(index: $0) },
                                          submit: { model.session?.submit($0) }),
                    chordSheet: model.chordSheet)
            .sheet(isPresented: $model.showSelfTest) {
                SelfTestView(model: model)
            }
            .sheet(item: $shareItem) { item in
                ShareSheet(items: [item.url])
            }
            .alert("Export failed", isPresented: Binding(get: { exportError != nil },
                                                          set: { if !$0 { exportError = nil } })) {
                Button("OK", role: .cancel) {}
            } message: {
                Text(exportError ?? "")
            }
    }

    private func export() {
        do {
            shareItem = ShareItem(url: try Diagnostics.shared.exportArchive())
        } catch {
            Log.ui.error("Export failed: \(error.localizedDescription, privacy: .public)")
            exportError = error.localizedDescription
        }
    }
}

struct ShareItem: Identifiable {
    let id = UUID()
    let url: URL
}

/// The system share sheet for files.
struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}

/// The self-test (docs/IOS.md, "Diagnostics"): runs when it opens, shows
/// every result and saves them in the Diagnostics folder.
struct SelfTestView: View {
    @ObservedObject var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var report: SelfTestReport?
    @State private var running = false

    var body: some View {
        NavigationStack {
            SelfTestContent(report: report, timings: model.timings, running: running)
                .navigationTitle("Self-test")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Done") { dismiss() }
                    }
                    ToolbarItem(placement: .primaryAction) {
                        Button("Run again") { Task { await run() } }
                            .disabled(running || model.phase != .running)
                    }
                }
        }
        .task {
            // Opened at launch (CI): wait for the session first.
            _ = await model.waitFor(timeout: .seconds(180)) { _ in model.phase != .starting && model.phase != .idle }
            if report == nil, model.phase == .running {
                _ = await model.waitFor(timeout: .seconds(60)) { !$0.text.isEmpty }
                await run()
            }
        }
    }

    private func run() async {
        running = true
        report = await SelfTest.run(model: model)
        running = false
    }
}

/// The self-test's results as rows (no List: the catalog can draw it too).
struct SelfTestContent: View {
    let report: SelfTestReport?
    let timings: LaunchTimings
    let running: Bool
    /// False for ImageRenderer (the catalog), which can't draw a ScrollView.
    var scrolls = true

    var body: some View {
        Group {
            if scrolls {
                ScrollView { rows }
            } else {
                Color.clear
                    .overlay(alignment: .top) { rows.fixedSize(horizontal: false, vertical: true) }
                    .clipped()
            }
        }
        .background(Color(uiColor: .systemGroupedBackground))
    }

    private var rows: some View {
            VStack(alignment: .leading, spacing: 14) {
                section("Result") {
                    if running {
                        row("Status", "Running…")
                    } else if let report {
                        row("Status", report.passed ? "Passed" : "Problems", ok: report.passed)
                        ForEach(report.problems, id: \.self) { Text($0).font(.footnote).foregroundStyle(.red) }
                    } else {
                        row("Status", "Waiting for the session")
                    }
                }
                section("Start-up") {
                    row("Python boot", seconds(timings.pythonBoot))
                    row("Session start", seconds(timings.sessionStart))
                    row("First song text", seconds(timings.firstText))
                    if let error = timings.error { row("Error", error, ok: false) }
                }
                if let report {
                    section("Synth (offline render)") {
                        if let render = report.offlineRender {
                            row("Render", render.ok ? "Sound" : (render.error ?? "Silent"), ok: render.ok)
                            row("Peak", "\(render.peak) of 32767")
                            row("Frames", "\(render.frames) in \(String(format: "%.3f", render.seconds)) s")
                        } else {
                            row("Render", "Not run", ok: false)
                        }
                    }
                    section("Live audio") {
                        row("Player", report.liveAudio?.initialized == true ? "Started" : (report.liveAudio?.error ?? "Unknown"),
                            ok: report.liveAudio?.initialized == true)
                        row("Category", report.audioCategory.replacingOccurrences(of: "AVAudioSessionCategory", with: ""))
                        row("Route", report.audioRoute.isEmpty ? "None" : report.audioRoute.joined(separator: ", "))
                        row("Sample rate", "\(Int(report.sampleRate)) Hz, buffer \(String(format: "%.1f", report.ioBufferDuration * 1000)) ms")
                        ForEach(report.auditionMessages, id: \.self) { Text($0).font(.footnote).foregroundStyle(.orange) }
                    }
                    section("Build") {
                        row("Version", report.build.line)
                        row("Built", report.build.date.isEmpty ? "?" : report.build.date)
                        row("Device", report.device)
                    }
                }
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func seconds(_ value: Double?) -> String {
        value.map { String(format: "%.2f s", $0) } ?? "–"
    }

    private func section<Content: View>(_ title: String, @ViewBuilder _ content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased())
                .font(.caption)
                .foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 6, content: content)
                .padding(12)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color(uiColor: .secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 10))
        }
    }

    private func row(_ label: String, _ value: String, ok: Bool? = nil) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
            Spacer(minLength: 12)
            Text(value)
                .multilineTextAlignment(.trailing)
                .foregroundStyle(ok == false ? Color.red : (ok == true ? Color.green : Color.secondary))
        }
        .font(.subheadline)
    }
}
