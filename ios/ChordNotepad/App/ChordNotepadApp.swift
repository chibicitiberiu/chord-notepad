import SwiftUI
import UIKit

@main
struct ChordNotepadApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @StateObject private var model = AppModel.shared
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            MainView(model: model, editor: model.editor)
                .task { await model.launch() }
                // A song opened from Files or another app (CFBundleDocumentTypes),
                // in place: a security-scoped URL the store bookmarks.
                .onOpenURL { model.openURL($0) }
        }
        .onChange(of: scenePhase) { _, phase in
            model.scenePhaseChanged(phase)
        }
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        Log.ui.info("Launch \(BuildInfo.current.line, privacy: .public)")
        Diagnostics.shared.start()
        return true
    }
}
