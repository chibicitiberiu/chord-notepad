import Foundation

/// Where the bundled User Guide lives (Android's `ui/help/HelpLinks.kt`). The
/// app's `WKURLSchemeHandler` serves `<app>/help/` under this scheme and
/// nothing else; every other load is blocked, and a link to a web site opens
/// in Safari when tapped.
public enum HelpLinks {
    /// The scheme the guide is served under.
    public static let scheme = "cnhelp"
    /// Its host.
    public static let host = "guide"
    /// The guide's pages are under this prefix.
    public static let prefix = "\(scheme)://\(host)/"
    /// The guide's first page.
    public static let startURL = prefix + "index.html"

    /// True when `url` is a page or a file of the bundled guide (loads in the web view).
    public static func isInternal(_ url: String) -> Bool { url.hasPrefix(prefix) }

    /// True when `url` should open in another app (a web link the guide mentions).
    public static func isExternal(_ url: String) -> Bool {
        !isInternal(url) && (url.hasPrefix("http://") || url.hasPrefix("https://") || url.hasPrefix("mailto:"))
    }

    /// The file of the guide `url` names, relative to the guide's folder
    /// (`index.html` for the root or a folder), or nil when it isn't the
    /// guide's or would leave its folder. The query and the fragment are
    /// dropped; the path is percent-decoded.
    public static func resourcePath(_ url: String) -> String? {
        guard isInternal(url) else { return nil }
        var rest = String(url.dropFirst(prefix.count))
        if let cut = rest.firstIndex(where: { $0 == "?" || $0 == "#" }) { rest = String(rest[..<cut]) }
        guard let decoded = rest.removingPercentEncoding else { return nil }
        var parts: [String] = []
        for part in decoded.split(separator: "/", omittingEmptySubsequences: false) {
            switch part {
            case "", ".": continue
            case "..": return nil
            default: parts.append(String(part))
            }
        }
        if parts.contains(where: { $0.contains("\\") || $0.contains("\0") }) { return nil }
        if parts.isEmpty || decoded.hasSuffix("/") { parts.append("index.html") }
        return parts.joined(separator: "/")
    }

    /// The MIME type the scheme handler answers a guide file with.
    public static func mimeType(_ path: String) -> String {
        switch (path as NSString).pathExtension.lowercased() {
        case "html", "htm": return "text/html"
        case "css": return "text/css"
        case "js": return "text/javascript"
        case "json": return "application/json"
        case "png": return "image/png"
        case "jpg", "jpeg": return "image/jpeg"
        case "gif": return "image/gif"
        case "webp": return "image/webp"
        case "svg": return "image/svg+xml"
        case "ico": return "image/x-icon"
        case "woff": return "font/woff"
        case "woff2": return "font/woff2"
        case "ttf": return "font/ttf"
        case "txt": return "text/plain"
        default: return "application/octet-stream"
        }
    }

    /// Whether a file of `mimeType` is text (served with `charset=utf-8`).
    public static func isText(_ mimeType: String) -> Bool {
        mimeType.hasPrefix("text/") || mimeType == "application/json" || mimeType == "image/svg+xml"
    }
}

/// The guide screen's texts (Android's `strings_help.xml`).
public enum UserGuideTexts {
    public static let title = "User Guide"
    public static let back = "Back"
    /// The guide isn't in the app (a build without it).
    public static let missing = "The user guide isn't part of this build."
}
