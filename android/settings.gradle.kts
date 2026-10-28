pluginManagement {
    repositories {
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

// Keep build outputs off the source tree's partition when asked to (local.env
// sets this; ~ is small on the dev machine). One subdirectory per checkout path,
// so two clones never share outputs.
providers.environmentVariable("CHORD_NOTEPAD_ANDROID_BUILD_ROOT").orNull?.let { root ->
    val checkout = settingsDir.absolutePath.trimStart('/').replace('/', '_')
    gradle.beforeProject {
        val name = if (path == ":") "root" else path.trimStart(':').replace(':', '_')
        layout.buildDirectory.set(File("$root/$checkout/$name"))
    }
}

rootProject.name = "ChordNotepad"
include(":app")
