package io.github.chibicitiberiu.chordnotepad.about

import io.github.chibicitiberiu.chordnotepad.BuildConfig

/**
 * What About shows about this build. There is no build date: it would make
 * the APK differ between two builds of the same source (reproducible builds).
 *
 * @property versionName The `VERSION` file's version (Gradle `versionName`).
 * @property versionCode The integer Android compares versions by.
 * @property commit The short git commit the build was made from, or `unknown`.
 * @property buildType `release` or `debug`.
 */
data class BuildInfo(
    val versionName: String,
    val versionCode: Int,
    val commit: String,
    val buildType: String,
) {
    companion object {
        /** The running app's build info. */
        val current = BuildInfo(
            versionName = BuildConfig.VERSION_NAME,
            versionCode = BuildConfig.VERSION_CODE,
            commit = BuildConfig.COMMIT,
            buildType = BuildConfig.BUILD_TYPE,
        )
    }
}

/** The project's home, opened only when the user taps the link. */
const val SOURCE_URL = "https://github.com/chibicitiberiu/chord-notepad"
