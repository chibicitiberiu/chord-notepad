// swift-tools-version:6.0
//
// ChordNotepadKit: the iOS app's non-UI half (docs/IOS.md). It embeds CPython,
// runs the shared core on its own threads and exposes the JSON session bridge
// to Swift. No UIKit or SwiftUI, so `swift test` runs it on Linux against the
// real core.

import Foundation
import PackageDescription

// Where the CPython headers and libpython come from when building for the host.
// iOS builds link Python.xcframework in the app instead (docs/IOS.md), so
// nothing here may leak into an iOS link:
//  - Linux: pkg-config's python3-embed (Fedora: python3-devel).
//  - macOS: only when CN_PYTHON_PKGCONFIG names a pkg-config package (CI's
//    kit tests on a Mac). A manifest is evaluated for the host, so an
//    unconditional pkgConfig would hand a Mac's Homebrew flags to the iOS build.
let environment = ProcessInfo.processInfo.environment
#if os(Linux)
let pythonPkgConfig: String? = environment["CN_PYTHON_PKGCONFIG"] ?? "python3-embed"
#else
let pythonPkgConfig: String? = environment["CN_PYTHON_PKGCONFIG"]
#endif

let package = Package(
    name: "ChordNotepadKit",
    platforms: [.iOS(.v17), .macOS(.v14)],
    products: [
        .library(name: "ChordNotepadKit", targets: ["ChordNotepadKit"]),
    ],
    targets: [
        // Python.h, found as <Python/Python.h> (the iOS framework) or <Python.h>.
        .systemLibrary(
            name: "CPython",
            path: "Sources/CPython",
            pkgConfig: pythonPkgConfig
        ),
        // Every Python C API call lives here: the interpreter's start, the
        // _cnbridge extension module (events and document store callbacks)
        // and the calls into the session handle. Swift sees plain C only.
        .target(
            name: "CNBridge",
            dependencies: ["CPython"],
            path: "Sources/CNBridge",
            linkerSettings: [
                .linkedLibrary("python3.14", .when(platforms: [.linux, .macOS])),
            ]
        ),
        .target(
            name: "ChordNotepadKit",
            dependencies: ["CNBridge"],
            path: "Sources/ChordNotepadKit",
            resources: [.copy("Python")]
        ),
        .testTarget(
            name: "ChordNotepadKitTests",
            dependencies: ["ChordNotepadKit"],
            path: "Tests/ChordNotepadKitTests",
            exclude: ["python"]
        ),
    ]
)
