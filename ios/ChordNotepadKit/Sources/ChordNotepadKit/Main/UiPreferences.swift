import Foundation

/// Where view-only preferences are kept: `UserDefaults` in the app, a
/// dictionary in the tests.
public protocol PreferenceStore: AnyObject {
    func double(forKey key: String) -> Double?
    func set(_ value: Double, forKey key: String)
}

/// A store in memory (the tests).
public final class MemoryPreferences: PreferenceStore {
    public private(set) var values: [String: Double]

    public init(_ values: [String: Double] = [:]) {
        self.values = values
    }

    public func double(forKey key: String) -> Double? { values[key] }
    public func set(_ value: Double, forKey key: String) { values[key] = value }
}

/// View-only preferences the session doesn't keep (Android's `UiPreferences`):
/// the landscape chord sheet column's width. The portrait sheet's height is
/// the session's (`set_chord_sheet_height`, shared with the desktop's sash); a
/// column width has no desktop counterpart, so it stays on the device.
public struct UiPreferences {
    /// Android's key in its `ui` preferences.
    public static let sideFractionKey = "side_fraction"

    public let store: PreferenceStore

    public init(store: PreferenceStore) {
        self.store = store
    }

    /// The landscape chord sheet column's share of the width, 30–70 % (50 %
    /// until the handle is first dragged); what it reads and writes is clamped.
    public var sideFraction: Double {
        get { clampSideFraction(store.double(forKey: Self.sideFractionKey) ?? MainMetrics.sideFractionDefault) }
        nonmutating set { store.set(clampSideFraction(newValue), forKey: Self.sideFractionKey) }
    }
}
