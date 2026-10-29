// Top-level build file. Module configuration lives in app/build.gradle.kts.
plugins {
    alias(libs.plugins.android.application) apply false
    // AGP 9 compiles Kotlin itself ("built-in Kotlin"); declaring KGP here only
    // pins the Kotlin compiler version it uses.
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.chaquopy) apply false
    alias(libs.plugins.aboutlibraries) apply false
}
