import ChordNotepadKit
import UIKit
import XCTest

@testable import ChordNotepad

extension SessionTests {
    /// The editor's remaining features, live in a real text view: Find and
    /// Replace all on a song (the matches painted, one undo step), the pinch
    /// (the session's size, the view's font), the font family and size from
    /// Settings, the app's shortcuts (through ``AppModel/shortcut(_:)``, as the
    /// menu commands call it, and the text view's own key command through
    /// the responder chain) and the side column's width in UserDefaults.
    func checkTheEditorsFeatures(_ model: AppModel) async throws {
        let editor = model.editor
        let session = try XCTUnwrap(model.session)
        XCTAssertEqual(model.ui.route, MainRoute.none)
        let window = UIWindow(frame: CGRect(x: 0, y: 0, width: 402, height: 600))
        let host = EditorHost()
        let view = host.textView
        let coordinator = SongEditor.Coordinator(controller: editor)
        view.delegate = coordinator
        host.frame = window.bounds
        window.addSubview(host)
        window.isHidden = false
        editor.attach(view)
        defer {
            editor.detach(view)
            window.isHidden = true
        }

        // -- a song with known chords, in Edit --------------------------------------------
        let song = "{key: C}\nAm C Am G\nla am la\nAm7 F Am\n"
        model.selectMode(.edit)
        session.submit(.restoreDraft(document: nil, modified: true, readOnly: false, text: song))
        var ok = await model.waitFor(timeout: .seconds(30)) { _ in
            editor.model.text == song && editor.model.highlightedIdentity == editor.model.identity
        }
        XCTAssertTrue(ok, "the song in the editor: \(editor.model.text.debugDescription)")

        // -- Find: Command-F's handler, the query typed, the matches painted -------------------
        model.shortcut(.findAndReplace)
        XCTAssertTrue(editor.model.find.open && editor.model.find.replacing)
        editor.find(.matchCase(true))
        editor.find(.wholeWord(true))
        editor.find(.query("Am"))
        XCTAssertEqual(editor.model.find.countText, "1 of 3")
        XCTAssertEqual(view.selectedRange, NSRange(location: 9, length: 2))
        let palette = EditorPalette.forScheme(dark: view.traitCollection.userInterfaceStyle == .dark)
        XCTAssertEqual(view.textStorage.attribute(.backgroundColor, at: 9, effectiveRange: nil) as? UIColor,
                       palette.findCurrent.uiColor, "the current match")
        XCTAssertEqual(view.textStorage.attribute(.backgroundColor, at: 14, effectiveRange: nil) as? UIColor,
                       palette.findMatch.uiColor, "another match")
        model.shortcut(.findNext)
        XCTAssertEqual(editor.model.find.countText, "2 of 3")
        model.shortcut(.findPrevious)
        XCTAssertEqual(editor.model.find.countText, "1 of 3")

        // -- Replace all: the session's one edit, its status, one undo step ----------------------
        editor.find(.replacement("Em"))
        editor.find(.replaceAll)
        ok = await model.waitFor(timeout: .seconds(30)) { snapshot in
            editor.model.text == "{key: C}\nEm C Em G\nla am la\nAm7 F Em\n"
                && snapshot.status?.text == "Replaced 3 matches"
        }
        XCTAssertTrue(ok, "replaced: \(editor.model.text.debugDescription), status \(String(describing: model.snapshot.status))")
        XCTAssertEqual(view.text, editor.model.text)
        XCTAssertEqual(editor.model.find.countText, "No matches")
        editor.perform(.undo)
        XCTAssertEqual(editor.model.text, song, "Replace all is one step")
        XCTAssertEqual(view.text, song)
        XCTAssertEqual(editor.model.find.matches.count, 3)
        editor.find(.close)
        XCTAssertFalse(editor.model.find.open)
        XCTAssertNil(view.textStorage.attribute(.backgroundColor, at: 9, effectiveRange: nil))

        // -- the pinch: steps to the session, the size kept, the view's font --------------------
        let before = editor.model.fontPoints
        editor.pinched(.began, scale: 1)
        editor.pinched(.changed, scale: 1.25)
        editor.pinched(.changed, scale: 1.5)
        editor.pinched(.ended, scale: 1.5)
        let pinched = EditorFont.pinchSize(before, zoom: 1.5)
        ok = await model.waitFor(timeout: .seconds(10)) { $0.editor?.fontSize == pinched && $0.settings?.values.fontSize == pinched }
        XCTAssertTrue(ok, "pinched to \(pinched): \(String(describing: model.snapshot.editor?.fontSize))")
        XCTAssertEqual(view.font?.pointSize, EditorAppearance.font(
            kind: editor.model.fontKind, points: pinched, category: view.traitCollection.preferredContentSizeCategory).pointSize)
        // Command-0 (the app's), then Command-+ (the text view's own key command, through the responder chain).
        model.shortcut(.fontReset)
        ok = await model.waitFor(timeout: .seconds(10)) { $0.editor?.fontSize == EditorFont.defaultPoints }
        XCTAssertTrue(ok)
        let plus = try XCTUnwrap(view.keyCommands?.first { $0.input == "+" && $0.modifierFlags == .command })
        XCTAssertTrue(plus.attributes.contains(.hidden), "listed once, as the app's Larger Text")
        XCTAssertTrue(UIApplication.shared.sendAction(plus.action, to: view, from: plus, for: nil))
        ok = await model.waitFor(timeout: .seconds(10)) { $0.editor?.fontSize == EditorFont.defaultPoints + 1 }
        XCTAssertTrue(ok, "Command-+ in the text")
        // Shortcuts wait while something is over the screen.
        model.ui.route = .menu
        model.shortcut(.fontSmaller)
        model.shortcut(.find)
        XCTAssertFalse(editor.model.find.open)
        model.ui.route = .none
        try await Task.sleep(for: .milliseconds(300))
        XCTAssertEqual(model.snapshot.editor?.fontSize, EditorFont.defaultPoints + 1, "ignored under the menu")
        model.shortcut(.fontReset)

        // -- the font family and size from Settings, as the editor draws them -------------------
        model.openSettings(page: .general)
        ok = await model.waitForSettings(timeout: .seconds(30)) { $0.ui.phase == .editing && $0.ui.draft != nil }
        XCTAssertTrue(ok)
        model.settingsAct { $0.updateDraft { draft in
            draft.fontKind = .serif
            draft.fontSize = 16
        } }
        ok = await model.waitFor(timeout: .seconds(10)) { _ in
            editor.model.fontKind == .serif && editor.model.fontPoints == 16
        }
        XCTAssertTrue(ok, "\(String(describing: model.snapshot.editor))")
        let serif = EditorAppearance.font(kind: .serif, points: 16,
                                          category: view.traitCollection.preferredContentSizeCategory)
        XCTAssertEqual(view.font?.fontName, serif.fontName)
        XCTAssertEqual(view.font?.pointSize, serif.pointSize)
        XCTAssertEqual((view.textStorage.attribute(.font, at: 0, effectiveRange: nil) as? UIFont)?.fontName, serif.fontName)
        model.settingsAct { $0.updateDraft { draft in
            draft.fontKind = .monospace
            draft.fontSize = EditorFont.defaultPoints
        } }
        ok = await model.waitFor(timeout: .seconds(10)) { _ in
            editor.model.fontKind == .monospace && editor.model.fontPoints == EditorFont.defaultPoints
        }
        XCTAssertTrue(ok)
        model.settingsAct { $0.requestClose() }
        XCTAssertEqual(model.ui.route, MainRoute.none)

        // -- the side column's width, kept in UserDefaults across launches --------------------
        let key = UiPreferences.sideFractionKey
        let saved = UserDefaults.standard.object(forKey: key)
        model.keepSideFraction(0.62)
        XCTAssertEqual(UserDefaults.standard.double(forKey: key), 0.62)
        XCTAssertEqual(model.sideFraction, 0.62)
        XCTAssertEqual(UiPreferences(store: UserDefaultsPreferences()).sideFraction, 0.62, "the next launch's")
        model.keepSideFraction(0.9)
        XCTAssertEqual(model.sideFraction, MainMetrics.sideFractionMax)
        if let saved { UserDefaults.standard.set(saved, forKey: key) } else { UserDefaults.standard.removeObject(forKey: key) }
    }
}
