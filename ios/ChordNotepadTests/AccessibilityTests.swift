import ChordNotepadKit
import SwiftUI
import UIKit
import XCTest

@testable import ChordNotepad

/// VoiceOver's view of every catalog screen: each is hosted in a window of
/// the app's scene and its accessibility elements are walked as an assistive
/// technology walks them (the containers' elements, then the views). A
/// button without a label, or with one SwiftUI made from an image's name
/// (`mdi_menu`, `chevron.right`), fails; so does a screen whose walk finds
/// no elements at all, and the main screens must show the buttons the
/// session test and CI's screenshots know by identifier.
@MainActor
final class AccessibilityTests: XCTestCase {
    struct Element {
        let label: String
        let identifier: String
        let traits: UIAccessibilityTraits
        let frame: CGRect
        let kind: String
    }

    /// SwiftUI builds its accessibility tree only for an assistive technology
    /// (run 45513358669's walk found no SwiftUI element without this): turn
    /// on the automation accessibility XCUITest and KIF use, through the
    /// simulator's libAccessibility (test bundle only; the app never calls it).
    override class func setUp() {
        super.setUp()
        guard let library = dlopen("/usr/lib/libAccessibility.dylib", RTLD_NOW),
              let symbol = dlsym(library, "_AXSSetAutomationEnabled") else {
            print("Accessibility: libAccessibility's _AXSSetAutomationEnabled not found")
            return
        }
        typealias SetEnabled = @convention(c) (Int32) -> Void
        unsafeBitCast(symbol, to: SetEnabled.self)(1)
    }

    /// An element's identifier: SwiftUI's nodes answer `accessibilityIdentifier`
    /// without declaring `UIAccessibilityIdentification`.
    private static func identifier(of object: NSObject) -> String {
        if let identified = object as? UIAccessibilityIdentification {
            return identified.accessibilityIdentifier ?? ""
        }
        let selector = NSSelectorFromString("accessibilityIdentifier")
        guard object.responds(to: selector) else { return "" }
        return object.perform(selector)?.takeUnretainedValue() as? String ?? ""
    }

    /// The accessibility elements under `root`, in VoiceOver's order.
    static func elements(under root: NSObject) -> [Element] {
        var found: [Element] = []
        var seen = Set<ObjectIdentifier>()
        func walk(_ object: NSObject, depth: Int) {
            guard depth < 80, seen.insert(ObjectIdentifier(object)).inserted else { return }
            if let view = object as? UIView, view.isHidden || view.alpha == 0 { return }
            if object.accessibilityElementsHidden { return }
            if object.isAccessibilityElement {
                found.append(Element(label: object.accessibilityLabel ?? "", identifier: identifier(of: object),
                                     traits: object.accessibilityTraits, frame: object.accessibilityFrame,
                                     kind: String(describing: type(of: object))))
                return
            }
            if let children = object.accessibilityElements, !children.isEmpty {
                children.compactMap { $0 as? NSObject }.forEach { walk($0, depth: depth + 1) }
                return
            }
            let count = object.accessibilityElementCount()
            if count != NSNotFound, count > 0 {
                for index in 0..<count {
                    if let child = object.accessibilityElement(at: index) as? NSObject { walk(child, depth: depth + 1) }
                }
                return
            }
            if let view = object as? UIView {
                view.subviews.forEach { walk($0, depth: depth + 1) }
            }
        }
        walk(root, depth: 0)
        return found
    }

    /// A label VoiceOver would read as an asset's or a symbol's name.
    static func looksLikeAnImageName(_ label: String) -> Bool {
        label.range(of: #"^[a-z0-9]+([_.][a-z0-9]+)+$"#, options: .regularExpression) != nil
    }

    /// `screen` drawn with `fixture` in a `device`-sized window, and its elements.
    private func walk(_ screen: CatalogScreen, _ fixture: String, _ device: CatalogRenderer.Device,
                      in scene: UIWindowScene) async -> [Element] {
        let window = UIWindow(windowScene: scene)
        window.frame = CGRect(origin: .zero, size: device.size)
        let host = UIHostingController(rootView: screen.make(PreviewCatalog.scene(fixture), device)
            .frame(width: device.size.width, height: device.size.height))
        window.rootViewController = host
        window.isHidden = false
        defer {
            window.isHidden = true
            window.rootViewController = nil
        }
        host.view.setNeedsLayout()
        host.view.layoutIfNeeded()
        // SwiftUI builds its accessibility nodes after the first frames.
        try? await Task.sleep(for: .milliseconds(150))
        return Self.elements(under: window)
    }

    func testEveryButtonOnEveryCatalogScreenHasALabel() async throws {
        let scene = try XCTUnwrap(UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }.first)
        var problems: [String] = []
        var report: [String] = []
        var buttons = 0
        var byScreen: [String: [Element]] = [:]
        for screen in PreviewCatalog.screens {
            guard let fixture = screen.fixtures.first, let device = screen.devices.first else { continue }
            let elements = await walk(screen, fixture, device, in: scene)
            byScreen[screen.name] = elements
            if elements.isEmpty { problems.append("\(screen.name): no accessibility elements") }
            for element in elements {
                let isButton = element.traits.contains(.button)
                if isButton { buttons += 1 }
                let label = element.label.trimmingCharacters(in: .whitespacesAndNewlines)
                report.append("\(screen.name)\t\(isButton ? "button" : "-")\t\(element.identifier)\t\(label)\t"
                              + "\(element.kind)\t\(element.traits.rawValue)")
                // VoiceOver reads any element: a part of its label named after an image is a bug.
                if label.components(separatedBy: ", ").contains(where: Self.looksLikeAnImageName) {
                    problems.append("\(screen.name): \(element.identifier.isEmpty ? "?" : element.identifier) "
                                    + "labelled \(label.debugDescription)")
                    continue
                }
                guard isButton else { continue }
                if label.isEmpty {
                    problems.append("\(screen.name): button \(element.identifier.isEmpty ? "?" : element.identifier) "
                                    + "at \(element.frame.integral) labelled \(label.debugDescription)")
                }
            }
        }
        // In the log too, so a failed run shows what the walk saw.
        print("Accessibility elements:\n" + report.prefix(400).joined(separator: "\n"))
        let attachment = XCTAttachment(string: report.joined(separator: "\n"))
        attachment.name = "accessibility-elements.tsv"
        attachment.lifetime = .keepAlways
        add(attachment)
        XCTAssertGreaterThan(buttons, 100, "the walk found next to no buttons")
        XCTAssertTrue(problems.isEmpty, problems.joined(separator: "\n"))

        // The buttons the main screens must show, by identifier, with Android's words.
        func expect(_ screen: String, _ identifier: String, _ label: String) {
            let element = byScreen[screen]?.first { $0.identifier == identifier }
            XCTAssertEqual(element?.label, label, "\(screen): \(identifier)")
        }
        expect("play", "menu", AccessibilityLabels.menu)
        expect("play", "save", AccessibilityLabels.save)
        expect("play", "tab-edit", AccessibilityLabels.edit)
        expect("play", "player-play", AccessibilityLabels.playSong)
        expect("play", "player-rewind", AccessibilityLabels.rewind)
        expect("play", "player-metronome", AccessibilityLabels.metronome)
        expect("play", "player-speed", AccessibilityLabels.speed)
        expect("play", "player-sheet", AccessibilityLabels.hideSheet)
        expect("edit", "ribbon-insert", AccessibilityLabels.insert)
        expect("edit", "ribbon-find", AccessibilityLabels.find)
        expect("find", "find-close", AccessibilityLabels.close)
        expect("find", "find-next", AccessibilityLabels.nextMatch)
    }

    func testImageNamesAreToldFromWords() {
        for name in ["mdi_menu", "chevron.right", "arrow.uturn.backward", "settings_close", "ic_capo"] {
            XCTAssertTrue(Self.looksLikeAnImageName(name), name)
        }
        for label in ["Save", "Open the menu", "Voicing: Piano", "Zoom in", "Aa", "W", "Bar 5/56", "C"] {
            XCTAssertFalse(Self.looksLikeAnImageName(label), label)
        }
    }
}
