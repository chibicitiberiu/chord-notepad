import ChordNotepadKit
import SwiftUI
import WebKit
import os

/// ☰ › User guide (Android's `UserGuideScreen`): the Sphinx guide built with
/// `-t ios` into `<app>/help` (the "User guide" build phase), shown in a web
/// view that reaches only those files: they are served under the `cnhelp:`
/// scheme (``HelpLinks``) by ``HelpSchemeHandler``, and a content rule list
/// blocks every other load. A link to a web site opens in Safari when tapped.
///
/// ← leaves the guide, as Android's bar button does; a swipe from the left
/// edge goes back through the guide's pages (Android's system Back). The page
/// follows the app's light or dark look (`prefers-color-scheme`), as Android
/// themes its WebView to match the app.
struct UserGuideScreen: View {
    var close: () -> Void = {}
    /// A link that couldn't be opened.
    var linkFailed: () -> Void = {}
    /// The first page is on screen (`-CNScreen guide` waits for it).
    var loaded: (String) -> Void = { _ in }

    @Environment(\.colorScheme) private var scheme
    private var colors: AppColors { .forScheme(dark: scheme == .dark) }

    var body: some View {
        VStack(spacing: 0) {
            PageBar(title: UserGuideTexts.title, colors: colors, back: close)
            if UserGuideFiles.available {
                GuideWebView(dark: scheme == .dark, background: UIColor(colors.surface.swiftUI),
                             linkFailed: linkFailed, loaded: loaded)
            } else {
                Text(UserGuideTexts.missing)
                    .foregroundColor(colors.text.swiftUI)
                    .padding(24)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            }
        }
        .background(colors.surface.swiftUI.ignoresSafeArea())
        .accessibilityIdentifier("user-guide-screen")
    }
}

/// Where the guide is in the app.
enum UserGuideFiles {
    static var directory: URL { AppPaths.bundle.appendingPathComponent("help", isDirectory: true) }
    static var available: Bool {
        FileManager.default.fileExists(atPath: directory.appendingPathComponent("index.html").path)
    }
}

/// The guide's web view. Its page (kept over a rotation by SwiftUI keeping
/// the view) and its history are WebKit's.
struct GuideWebView: UIViewRepresentable {
    let dark: Bool
    let background: UIColor
    var linkFailed: () -> Void = {}
    var loaded: (String) -> Void = { _ in }

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.setURLSchemeHandler(HelpSchemeHandler(root: UserGuideFiles.directory), forURLScheme: HelpLinks.scheme)
        // JavaScript stays on: the theme's menu and the search need it. Nothing
        // leaves the app (the rule list below), and no data persists.
        configuration.websiteDataStore = .nonPersistent()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.navigationDelegate = context.coordinator
        view.allowsBackForwardNavigationGestures = true
        view.allowsLinkPreview = false
        // No white flash before the page.
        view.isOpaque = false
        view.backgroundColor = background
        view.scrollView.backgroundColor = background
        view.overrideUserInterfaceStyle = dark ? .dark : .light
        view.accessibilityIdentifier = "user-guide-web"
        // Block every load that isn't the guide's, then load the first page.
        WKContentRuleListStore.default().compileContentRuleList(
            forIdentifier: "cnhelp-only", encodedContentRuleList: Self.rules) { list, error in
            if let list {
                view.configuration.userContentController.add(list)
            } else {
                Log.ui.error("Guide rules: \(String(describing: error), privacy: .public)")
            }
            view.load(URLRequest(url: URL(string: HelpLinks.startURL)!))
        }
        return view
    }

    func updateUIView(_ view: WKWebView, context: Context) {
        context.coordinator.parent = self
        view.overrideUserInterfaceStyle = dark ? .dark : .light
        view.backgroundColor = background
        view.scrollView.backgroundColor = background
    }

    /// Block everything, then let the guide's own scheme through.
    static let rules = """
        [{"trigger": {"url-filter": ".*"}, "action": {"type": "block"}},
         {"trigger": {"url-filter": "^\(HelpLinks.scheme):"}, "action": {"type": "ignore-previous-rules"}}]
        """

    @MainActor
    final class Coordinator: NSObject, WKNavigationDelegate {
        var parent: GuideWebView

        init(_ parent: GuideWebView) {
            self.parent = parent
        }

        func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction) async -> WKNavigationActionPolicy {
            let url = action.request.url?.absoluteString ?? ""
            if HelpLinks.isInternal(url) || url == "about:blank" { return .allow }
            // A web link opens in Safari, and only when the user tapped it.
            if action.navigationType == .linkActivated, HelpLinks.isExternal(url), let target = URL(string: url) {
                let failed = parent.linkFailed
                UIApplication.shared.open(target) { opened in
                    if !opened { failed() }
                }
            }
            return .cancel
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.loaded(webView.url?.absoluteString ?? "")
        }
    }
}

/// Serves `<app>/help/` under `cnhelp://guide/` (Android's WebViewAssetLoader):
/// a file outside the folder, or one that isn't there, is a 404.
@MainActor
final class HelpSchemeHandler: NSObject, WKURLSchemeHandler {
    private let root: URL

    init(root: URL) {
        self.root = root
    }

    func webView(_ webView: WKWebView, start task: any WKURLSchemeTask) {
        guard let url = task.request.url else {
            task.didFailWithError(URLError(.badURL))
            return
        }
        guard let path = HelpLinks.resourcePath(url.absoluteString),
              let data = try? Data(contentsOf: root.appendingPathComponent(path)) else {
            Log.ui.error("Guide: no \(url.absoluteString, privacy: .public)")
            let response = HTTPURLResponse(url: url, statusCode: 404, httpVersion: "HTTP/1.1",
                                           headerFields: ["Content-Type": "text/plain"])!
            task.didReceive(response)
            task.didReceive(Data())
            task.didFinish()
            return
        }
        let mime = HelpLinks.mimeType(path)
        let type = HelpLinks.isText(mime) ? "\(mime); charset=utf-8" : mime
        let response = HTTPURLResponse(url: url, statusCode: 200, httpVersion: "HTTP/1.1",
                                       headerFields: ["Content-Type": type, "Content-Length": "\(data.count)"])!
        task.didReceive(response)
        task.didReceive(data)
        task.didFinish()
    }

    func webView(_ webView: WKWebView, stop task: any WKURLSchemeTask) {}
}
