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
        // In the app's scene, so it can be the key window (the app's own window holds AppModel.shared's
        // editor, not this test's model).
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        let window = UIWindow(windowScene: scene)
        window.frame = CGRect(x: 0, y: 0, width: 402, height: 600)
        let host = EditorHost()
        let view = host.textView
        let coordinator = SongEditor.Coordinator(controller: editor)
        view.delegate = coordinator
        host.frame = window.bounds
        window.addSubview(host)
        // The key window, so actions sent to no target go to its first responder.
        let previousKey = scene.windows.first { $0.isKeyWindow }
        window.makeKeyAndVisible()
        XCTAssertTrue(window.isKeyWindow)
        editor.attach(view)
        defer {
            editor.detach(view)
            window.isHidden = true
            previousKey?.makeKey()
        }
        /// Send a system menu action as a key press does: to no target, so to whoever has the keys.
        func sendMenuAction(_ name: String) -> Bool {
            UIApplication.shared.sendAction(NSSelectorFromString(name), to: nil, from: nil, for: nil)
        }
        /// A few main-loop turns (the host takes the keys on the next one).
        func settle() async { try? await Task.sleep(for: .milliseconds(300)) }

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
        // The system menu's Find Next and Find Previous (Command-G, Shift-Command-G), sent to no
        // target as a key press sends them: the host has the keys in Edit before the text is
        // tapped, and they pass through the text once it has them.
        await settle()
        XCTAssertTrue(host.isFirstResponder, "the host takes the keys nothing else has")
        XCTAssertFalse(view.canPerformAction(NSSelectorFromString("find:"), withSender: nil), "the text passes it on")
        XCTAssertTrue(host.canPerformAction(NSSelectorFromString("open:"), withSender: nil))
        XCTAssertTrue(sendMenuAction("findNext:"))
        XCTAssertEqual(editor.model.find.countText, "2 of 3")
        XCTAssertTrue(view.becomeFirstResponder())
        XCTAssertTrue(sendMenuAction("findPrevious:"))
        XCTAssertEqual(editor.model.find.countText, "1 of 3")
        // In Play the frozen text lets the keys go and the host takes them: no keyboard, and
        // the text's own keys (undo, the line commands) don't reach it.
        model.selectMode(.play)
        await settle()
        XCTAssertFalse(view.isFirstResponder)
        XCTAssertTrue(host.isFirstResponder)
        XCTAssertFalse(editor.model.find.replacing, "Play finds without the Replace row")
        XCTAssertTrue(sendMenuAction("findNext:"))
        XCTAssertEqual(editor.model.find.countText, "2 of 3")
        model.selectMode(.edit)
        XCTAssertTrue(editor.model.find.canReplace)
        editor.find(.showReplace(true))
        editor.find(.previous)
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
        XCTAssertTrue(UIApplication.shared.sendAction(try XCTUnwrap(plus.action), to: view, from: plus, for: nil))
        ok = await model.waitFor(timeout: .seconds(10)) { $0.editor?.fontSize == EditorFont.defaultPoints + 1 }
        XCTAssertTrue(ok, "Command-+ in the text")
        // Command-? opens the user guide (Android's F1).
        model.shortcut(.userGuide)
        XCTAssertEqual(model.ui.route, .userGuide)
        model.ui.route = .none
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

        // -- VoiceOver in Play: each chord its own element, activated as a tap (S0 issue 8) -----
        model.selectMode(.play)
        let elements = try XCTUnwrap(view.accessibilityElements as? [PlayTextElement], "Play's elements")
        XCTAssertFalse(view.isAccessibilityElement, "the text view is their container in Play")
        XCTAssertEqual(elements.map(\.accessibilityLabel),
                       ["{key: C}", "Am", "C", "Am", "G", "la am la", "Am7", "F", "Am"])
        let chordC = elements[2], chordG = elements[4]
        XCTAssertTrue(chordG.accessibilityTraits.contains(.button))
        XCTAssertEqual(elements[0].accessibilityTraits, .staticText)
        XCTAssertGreaterThan(chordG.accessibilityFrame.minX, chordC.accessibilityFrame.maxX, "G is right of C")
        XCTAssertEqual(chordG.accessibilityFrame.minY, chordC.accessibilityFrame.minY, accuracy: 1)
        XCTAssertTrue(chordG.accessibilityActivate())
        ok = await model.waitFor(timeout: .seconds(10)) { $0.playback?.playheadOffset == 17 }
        XCTAssertTrue(ok, "the playhead on G: \(String(describing: model.snapshot.playback?.playheadOffset))")
        ok = await model.waitFor(timeout: .seconds(5)) { _ in chordG.accessibilityTraits.contains(.selected) }
        XCTAssertTrue(ok, "the marker's chord is the selected one")
        XCTAssertFalse(elements[0].accessibilityActivate(), "text does nothing")
        model.selectMode(.edit)
        XCTAssertNil(view.playElements, "Edit has the text view's own accessibility")
        XCTAssertNil(view.accessibilityElements as? [PlayTextElement])

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
