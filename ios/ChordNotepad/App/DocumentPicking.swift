import Foundation
import UIKit
import UniformTypeIdentifiers
import os

/// The system's document pickers, as the app uses them (docs/IOS.md,
/// "Files"). A seam: CI can't drive UIDocumentPickerViewController without UI
/// tests, so the session test puts a stand-in here that answers as the user
/// would. Each call ends with exactly one `done`.
@MainActor
protocol DocumentPicking: AnyObject {
    /// Open: the file the user picked (security-scoped), or nil.
    func pickToOpen(contentTypes: [UTType], done: @escaping (URL?) -> Void)
    /// Save As: move `file` (an empty one the app made, with the suggested
    /// name) where the user picks; the file where it went, or nil.
    func pickToMove(_ file: URL, done: @escaping (URL?) -> Void)
    /// An export: copy `file` where the user picks; where it went, or nil.
    func pickToExport(_ file: URL, done: @escaping (URL?) -> Void)
}

/// ``DocumentPicking`` with UIDocumentPickerViewController, presented over
/// whatever is on screen.
@MainActor
final class SystemDocumentPicker: NSObject, DocumentPicking, UIDocumentPickerDelegate {
    private var done: ((URL?) -> Void)?

    func pickToOpen(contentTypes: [UTType], done: @escaping (URL?) -> Void) {
        let picker = UIDocumentPickerViewController(forOpeningContentTypes: contentTypes, asCopy: false)
        picker.allowsMultipleSelection = false
        present(picker, done: done)
    }

    func pickToMove(_ file: URL, done: @escaping (URL?) -> Void) {
        present(UIDocumentPickerViewController(forExporting: [file], asCopy: false), done: done)
    }

    func pickToExport(_ file: URL, done: @escaping (URL?) -> Void) {
        present(UIDocumentPickerViewController(forExporting: [file], asCopy: true), done: done)
    }

    private func present(_ picker: UIDocumentPickerViewController, done: @escaping (URL?) -> Void) {
        // One picker at a time: one still open (it shouldn't be) is answered as cancelled.
        finish(nil)
        guard let top = Self.topViewController() else {
            Log.ui.error("No window to present the document picker from")
            done(nil)
            return
        }
        self.done = done
        picker.delegate = self
        picker.modalPresentationStyle = .formSheet
        top.present(picker, animated: true)
    }

    func documentPicker(_ controller: UIDocumentPickerViewController, didPickDocumentsAt urls: [URL]) {
        finish(urls.first)
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        finish(nil)
    }

    private func finish(_ url: URL?) {
        guard let done else { return }
        self.done = nil
        done(url)
    }

    /// The view controller on top of the foreground window.
    static func topViewController() -> UIViewController? {
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        let scene = scenes.first { $0.activationState == .foregroundActive } ?? scenes.first
        var top = (scene?.windows.first { $0.isKeyWindow } ?? scene?.windows.first)?.rootViewController
        while let presented = top?.presentedViewController, !presented.isBeingDismissed {
            top = presented
        }
        return top
    }
}
