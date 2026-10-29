import java.io.File
import java.net.URI
import java.security.MessageDigest
import java.util.zip.ZipFile
import javax.inject.Inject

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.chaquopy)
    alias(libs.plugins.aboutlibraries)
}

// ---------------------------------------------------------------------------
// Version: versionName comes from the repo's VERSION file. versionCode is
// (MAJ*10000 + MIN*100 + PATCH)*10 + rebuild, written as a literal on purpose
// (docs/ANDROID_PORT_PLAN.md, "Version scheme"); a test will check the pair.
// ---------------------------------------------------------------------------
val repoRoot: Directory = rootProject.layout.projectDirectory.dir("..")
val appVersionName: String = providers.fileContents(repoRoot.file("VERSION")).asText.get().trim()
val appVersionCode = 4010

// Shown in About: the commit the build was made from (never a date, so builds
// stay reproducible). "unknown" outside a git checkout; -PcnCommit=<id> sets it.
val appCommit: String = providers.gradleProperty("cnCommit").orElse(
    providers.exec {
        commandLine("git", "-C", repoRoot.asFile.path, "rev-parse", "--short=9", "HEAD")
        isIgnoreExitValue = true
    }.standardOutput.asText.map { it.trim().ifEmpty { "unknown" } },
).get()

// ABIs: arm64-v8a (phones) + x86_64 (emulator). `-PcnAbis=x86_64` builds one.
val appAbis: List<String> = providers.gradleProperty("cnAbis")
    .orElse("arm64-v8a,x86_64").get().split(",").map { it.trim() }.filter { it.isNotEmpty() }

// Downloads/prebuilts cache shared with android/tools (see local.env.example).
val androidCacheDir: String = providers.environmentVariable("CHORD_NOTEPAD_ANDROID_CACHE")
    .orElse("/mnt/data_linux/Bin/android/cache").get()

// music21: "trimmed" (default, data files stripped by tools/strip_music21.py)
// or "full" (the upstream wheel, for size comparisons).
val music21Mode: String = providers.gradleProperty("cnMusic21").orElse("trimmed").get()
val music21Version = "10.3.0"
val music21TrimmedWheel: Provider<RegularFile> =
    layout.buildDirectory.file("wheels/music21-$music21Version+cnstrip1-py3-none-any.whl")

// The Python bridge's DTO schema (session.bridge's dump), checked by the
// Kotlin contract test (BridgeSchemaContractTest).
val bridgeSchemaPath: String = repoRoot.file("android/bridge_schema.json").asFile.path

val buildPythonExe: String = providers.environmentVariable("CHAQUOPY_BUILD_PYTHON")
    .orElse("python3.14").get()

// Python packages: pinned with hashes in android/requirements.txt and installed
// offline from this wheelhouse (filled by tools/build_wheelhouse.py).
val pythonRequirements: RegularFile = repoRoot.file("android/requirements.txt")
val wheelhouseDir: String = "$androidCacheDir/wheelhouse"
val pythonPins: List<Pair<String, String>> =
    providers.fileContents(pythonRequirements).asText.get().lines()
        .map { it.substringBefore('#').trim() }
        .mapNotNull { Regex("""^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)""").find(it) }
        .map { it.groupValues[1] to it.groupValues[2] }
check(pythonPins.any { it.first == "music21" && it.second == music21Version }) {
    "android/requirements.txt must pin music21==$music21Version (strip_music21.py's version)"
}

android {
    namespace = "io.github.chibicitiberiu.chordnotepad"
    // Current AndroidX/Compose releases require compiling against API 37;
    // the app still targets 36.
    compileSdk = 37
    // Same NDK as android/native/build.sh; Gradle itself only takes
    // libc++_shared.so from it.
    ndkVersion = "27.3.13750724"

    defaultConfig {
        applicationId = "io.github.chibicitiberiu.chordnotepad"
        minSdk = 24
        targetSdk = 36
        versionCode = appVersionCode
        versionName = appVersionName
        buildConfigField("String", "COMMIT", "\"$appCommit\"")
        ndk {
            abiFilters += appAbis
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            // M2 spike: debug-signed so the release APK installs. Real signing
            // (upload key / offline FOSS key) is M6.
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    testOptions {
        unitTests {
            // android.util.Log and friends return defaults in JVM tests; the
            // tested logic itself stays Android-free.
            isReturnDefaultValues = true
            all {
                // The bridge contract (step 14 commits it; the test skips
                // while it is missing). See docs/ANDROID.md, "Bridge contract".
                it.systemProperty("cn.bridgeSchema", bridgeSchemaPath)
                // The licence data the app bundles (AboutLibrariesTest, LicenceCatalogTest).
                it.systemProperty("cn.licensesDir", file("src/main/assets/licenses").path)
                it.systemProperty("cn.requirements", pythonRequirements.asFile.path)
                // The generated User Guide (HelpAssetsTest).
                it.systemProperty("cn.helpDir", layout.buildDirectory.dir("generated/help/assets/help").get().asFile.path)
            }
        }
    }

    // No signed dependency blob in the APK (reproducibility, F-Droid).
    dependenciesInfo {
        includeInApk = false
        includeInBundle = false
    }

    packaging {
        jniLibs {
            // Store .so files uncompressed and page-aligned; loaded from the APK.
            useLegacyPackaging = false
        }
    }
}

chaquopy {
    defaultConfig {
        version = "3.14"
        buildPython(buildPythonExe)
        pip {
            // Offline: everything comes from the hash-checked wheelhouse
            // (tools/build_wheelhouse.py, pins in android/requirements.txt);
            // no PyPI or chaquo.com index is consulted. Every dependency is
            // listed explicitly: music21's declared deps pull in
            // numpy/matplotlib/joblib, which it never imports here.
            options("--no-deps", "--no-index", "--find-links", wheelhouseDir)
            for ((name, version) in pythonPins) {
                if (name != "music21") install("$name==$version")
            }
            if (music21Mode == "full") {
                install("music21==$music21Version")
            } else {
                // Through --find-links rather than a file path: pip records a
                // path install in direct_url.json, which made the APK depend on
                // the checkout location (M2 reproducibility check).
                options("--find-links", music21TrimmedWheel.get().asFile.parentFile.path)
                install("music21==$music21Version+cnstrip1")
            }
        }
    }
    sourceSets {
        getByName("main") {
            // The shared core, minus the Tk UI and desktop-only modules
            // (same list as tests/test_core_import_guard.py DESKTOP_ONLY).
            srcDir("../../src")
            exclude(
                "__init__.py",
                "**/__pycache__/**",
                "ui/**",
                "main.py",
                "application.py",
                "utils/display_scaling.py",
                "utils/file_dialogs.py",
                "utils/icon_loader.py",
                "utils/ui_helpers.py",
            )
        }
    }
}

// ---------------------------------------------------------------------------
// Offline wheelhouse and the trimmed music21 wheel (tools/strip_music21.py),
// both ready before Chaquopy's pip runs.
// ---------------------------------------------------------------------------
val prepareWheelhouse = tasks.register<Exec>("prepareWheelhouse") {
    description = "Checks the offline wheelhouse against android/requirements.txt (downloads only missing pins)"
    val script = repoRoot.file("android/tools/build_wheelhouse.py")
    // The script hash-checks the wheelhouse itself and only goes online for
    // files that are missing; under `gradlew --offline` it only checks.
    outputs.upToDateWhen { false }
    commandLine(
        buildPythonExe, "-I", script.asFile.path,
        if (gradle.startParameter.isOffline) "check" else "fetch",
        "--requirements", pythonRequirements.asFile.path,
        "--wheelhouse", wheelhouseDir,
    )
}

val stripMusic21 = tasks.register<Exec>("stripMusic21") {
    description = "Builds the data-trimmed music21 wheel"
    dependsOn(prepareWheelhouse)
    val script = repoRoot.file("android/tools/strip_music21.py")
    inputs.file(script)
    outputs.file(music21TrimmedWheel)
    commandLine(
        buildPythonExe, "-I", script.asFile.path,
        "--wheel", "$wheelhouseDir/music21-$music21Version-py3-none-any.whl",
        "--out-dir", music21TrimmedWheel.get().asFile.parentFile.path,
    )
}
tasks.matching { it.name.matches(Regex("install.*PythonRequirements")) }.configureEach {
    dependsOn(prepareWheelhouse)
    if (music21Mode != "full") dependsOn(stripMusic21)
}

// ---------------------------------------------------------------------------
// Native libraries: FluidSynth, Oboe, libsndfile and its codecs.
//   cnNatives=source (default): cross-compiled from the pinned submodules in
//     android/native by android/native/build.sh (mirrors upstream's Android CI).
//   cnNatives=prebuilt: upstream's FluidSynth 2.6.0 Android release zip,
//     sha256-pinned; a fallback for when the submodules aren't checked out.
// Either way they land in a generated jniLibs directory together with
// libc++_shared.so from the NDK.
// ---------------------------------------------------------------------------
val nativesMode: String = providers.gradleProperty("cnNatives").orElse("source").get()
check(nativesMode == "source" || nativesMode == "prebuilt") {
    "cnNatives must be 'source' or 'prebuilt', not '$nativesMode'"
}
val nativeLibs = listOf(
    // libfluidsynth needs liboboe and libsndfile; libsndfile needs the codecs.
    "libfluidsynth.so", "liboboe.so", "libsndfile.so", "libFLAC.so", "libogg.so",
    "libopus.so", "libvorbis.so", "libvorbisenc.so", "libvorbisfile.so",
)
val androidProjectDir: File = rootProject.layout.projectDirectory.asFile
// Same per-checkout scheme as settings.gradle.kts and build.sh's default, so a
// hand-run build.sh and Gradle share one output directory.
val nativeOutDir: File = providers.environmentVariable("CHORD_NOTEPAD_ANDROID_BUILD_ROOT").orNull
    ?.let { File(it, androidProjectDir.absolutePath.trimStart('/').replace('/', '_') + "/native") }
    ?: File(androidProjectDir, "build/native")

val buildNatives = tasks.register<Exec>("buildNatives") {
    description = "Cross-compiles FluidSynth and its dependencies (android/native/build.sh)"
    val script = File(androidProjectDir, "native/build.sh")
    // build.sh keeps its own input stamp per ABI and returns at once when
    // nothing changed, so let it decide.
    outputs.upToDateWhen { false }
    outputs.dirs(appAbis.map { File(nativeOutDir, "$it/lib") })
    environment("ANDROID_HOME", androidComponents.sdkComponents.sdkDirectory.get().asFile.path)
    commandLine(
        "bash", script.path,
        "--abis", appAbis.joinToString(","),
        "--out", nativeOutDir.path,
        "--jobs", providers.gradleProperty("cnNativeJobs").orElse("4").get(),
    )
}

abstract class PrepareNativeLibs : DefaultTask() {
    @get:Input abstract val mode: Property<String>
    @get:Input abstract val abis: ListProperty<String>
    @get:Input abstract val libs: ListProperty<String>
    /** mode=source: the libraries build.sh produced, one lib dir per ABI. */
    @get:InputFiles @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val builtLibs: ConfigurableFileCollection
    @get:Internal abstract val builtDir: Property<String>
    /** mode=prebuilt: the upstream zip. */
    @get:Input abstract val url: Property<String>
    @get:Input abstract val sha256: Property<String>
    @get:Input abstract val zipPath: Property<String>
    /** libc++_shared.so per ABI from the NDK (only these files are task inputs,
     *  not the whole multi-GB NDK directory). */
    @get:InputFiles @get:PathSensitive(PathSensitivity.RELATIVE)
    abstract val libcxx: ConfigurableFileCollection
    @get:OutputDirectory abstract val outputDir: DirectoryProperty

    private fun sha256Of(file: File): String {
        val md = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buf = ByteArray(1 shl 16)
            while (true) {
                val n = input.read(buf)
                if (n < 0) break
                md.update(buf, 0, n)
            }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }

    private fun prebuiltZip(): File {
        val zip = File(zipPath.get())
        if (!zip.exists() || sha256Of(zip) != sha256.get()) {
            zip.parentFile.mkdirs()
            val part = File(zip.path + ".part")
            URI(url.get()).toURL().openStream().use { input -> part.outputStream().use { input.copyTo(it) } }
            part.renameTo(zip)
        }
        val actual = sha256Of(zip)
        check(actual == sha256.get()) { "FluidSynth prebuilt hash mismatch: $actual" }
        return zip
    }

    @TaskAction
    fun run() {
        val out = outputDir.get().asFile
        out.deleteRecursively()
        val triples = mapOf("arm64-v8a" to "aarch64-linux-android", "x86_64" to "x86_64-linux-android")
        val zip = if (mode.get() == "prebuilt") ZipFile(prebuiltZip()) else null
        try {
            for (abi in abis.get()) {
                val abiDir = File(out, abi).apply { mkdirs() }
                for (lib in libs.get()) {
                    val dest = File(abiDir, lib)
                    if (zip != null) {
                        val entry = zip.getEntry("lib/$abi/$lib") ?: error("missing lib/$abi/$lib in the prebuilt zip")
                        zip.getInputStream(entry).use { input -> dest.outputStream().use { input.copyTo(it) } }
                    } else {
                        val src = File(builtDir.get(), "$abi/lib/$lib")
                        check(src.isFile) { "missing $src (did buildNatives run?)" }
                        src.copyTo(dest, overwrite = true)
                    }
                }
                val triple = triples[abi] ?: error("unknown ABI $abi")
                val cxx = libcxx.files.single { it.parentFile.name == triple }
                cxx.copyTo(File(abiDir, "libc++_shared.so"), overwrite = true)
            }
        } finally {
            zip?.close()
        }
    }
}

val prepareNativeLibs = tasks.register<PrepareNativeLibs>("prepareNativeLibs") {
    description = "Collects the FluidSynth .so files (source-built or prebuilt) into generated jniLibs"
    mode.set(nativesMode)
    abis.set(appAbis)
    libs.set(nativeLibs)
    builtDir.set(nativeOutDir.path)
    if (nativesMode == "source") {
        builtLibs.from(buildNatives)
    }
    url.set("https://github.com/FluidSynth/fluidsynth/releases/download/v2.6.0/fluidsynth-v2.6.0-android24.zip")
    sha256.set("81cd70dddb3381cda02c430a6657923766d1acb83de11d266d7a19aee3c7ca4d")
    zipPath.set("$androidCacheDir/fluidsynth-v2.6.0-android24.zip")
    val triples = mapOf("arm64-v8a" to "aarch64-linux-android", "x86_64" to "x86_64-linux-android")
    libcxx.from(androidComponents.sdkComponents.ndkDirectory.map { ndk ->
        appAbis.map { abi ->
            ndk.file("toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/${triples.getValue(abi)}/libc++_shared.so")
        }
    })
    outputDir.set(layout.buildDirectory.dir("generated/fluidsynth/jniLibs"))
}

// ---------------------------------------------------------------------------
// Assets shared with the desktop app, copied into the APK at build time instead
// of duplicated in git: the SoundFont (resources/soundfont) and, for the M2
// spike screen, a sample song (examples/).
// ---------------------------------------------------------------------------
abstract class CopyIntoAssets : DefaultTask() {
    @get:InputFile abstract val source: RegularFileProperty
    @get:Input abstract val targetPath: Property<String>
    @get:OutputDirectory abstract val outputDir: DirectoryProperty

    @TaskAction
    fun run() {
        val out = outputDir.get().asFile
        out.deleteRecursively()
        val dest = File(out, targetPath.get())
        dest.parentFile.mkdirs()
        source.get().asFile.copyTo(dest, overwrite = true)
    }
}

val copySoundfont = tasks.register<CopyIntoAssets>("copySoundfont") {
    description = "Copies GeneralUser-GS.sf2 into generated assets"
    source.set(repoRoot.file("resources/soundfont/GeneralUser-GS.sf2"))
    targetPath.set("soundfont/GeneralUser-GS.sf2")
    outputDir.set(layout.buildDirectory.dir("generated/soundfont/assets"))
}

// M2 spike only.
val copySpikeSample = tasks.register<CopyIntoAssets>("copySpikeSample") {
    description = "Copies the spike screen's sample song into generated assets"
    source.set(repoRoot.file("examples/02_american_complete.txt"))
    targetPath.set("spike/sample.txt")
    outputDir.set(layout.buildDirectory.dir("generated/spike/assets"))
}

// ---------------------------------------------------------------------------
// Chord sheet: the six base clef/glyph PNGs that Kotlin draws the staff view's
// image ops with, exported from src/chord_sheet/clef_assets.py at build time
// (tools/export_clef_glyphs.py) instead of committed as binaries. They land in
// assets/chord_sheet/<asset>.png plus glyphs.json (docs/ANDROID.md).
// ---------------------------------------------------------------------------
abstract class ExportClefGlyphs @Inject constructor(
    private val execOps: ExecOperations,
) : DefaultTask() {
    @get:Input abstract val pythonExe: Property<String>
    @get:InputFile abstract val script: RegularFileProperty
    /** The module that embeds the PNGs (the script's only import). */
    @get:InputFile abstract val clefAssets: RegularFileProperty
    @get:Internal abstract val srcDir: Property<String>
    @get:OutputDirectory abstract val outputDir: DirectoryProperty

    @TaskAction
    fun run() {
        val out = outputDir.get().asFile
        out.deleteRecursively()
        execOps.exec {
            commandLine(
                pythonExe.get(), "-I", script.get().asFile.path,
                "--src", srcDir.get(),
                "--out-dir", File(out, "chord_sheet").path,
            )
        }
    }
}

val exportClefGlyphs = tasks.register<ExportClefGlyphs>("exportClefGlyphs") {
    description = "Exports the chord sheet's base clef/glyph PNGs into generated assets"
    pythonExe.set(buildPythonExe)
    script.set(repoRoot.file("android/tools/export_clef_glyphs.py"))
    clefAssets.set(repoRoot.file("src/chord_sheet/clef_assets.py"))
    srcDir.set(repoRoot.dir("src").asFile.path)
    outputDir.set(layout.buildDirectory.dir("generated/chordSheetGlyphs/assets"))
}

// ---------------------------------------------------------------------------
// User Guide: the Sphinx help (help/*.rst) built with `-t android` (the same
// as `make docs-html-android`) into assets/help/, shown offline in a WebView.
// Needs a Python with the Sphinx stack of the desktop docs build: set
// CHORD_NOTEPAD_DOCS_PYTHON (android/local.env.example) to the pipenv venv's
// python, or install android/docs-requirements.txt into CHAQUOPY_BUILD_PYTHON
// (what CI does). SOURCE_DATE_EPOCH is set, so the HTML is reproducible.
// ---------------------------------------------------------------------------
val docsPythonExe: String = providers.environmentVariable("CHORD_NOTEPAD_DOCS_PYTHON").orElse(buildPythonExe).get()

abstract class BuildAndroidHelp @Inject constructor(
    private val execOps: ExecOperations,
) : DefaultTask() {
    @get:Input abstract val pythonExe: Property<String>
    @get:InputDirectory @get:PathSensitive(PathSensitivity.RELATIVE) abstract val helpDir: DirectoryProperty
    @get:InputFile @get:PathSensitive(PathSensitivity.RELATIVE) abstract val versionFile: RegularFileProperty
    @get:Internal abstract val scratchDir: DirectoryProperty
    @get:OutputDirectory abstract val outputDir: DirectoryProperty

    @TaskAction
    fun run() {
        val out = outputDir.get().asFile
        out.deleteRecursively()
        val html = File(out, "help")
        val scratch = scratchDir.get().asFile.apply { deleteRecursively(); mkdirs() }
        try {
            execOps.exec {
                // -W: a docs warning fails the build. Reproducible: no
                // timestamps in the theme's output; the epoch pins the rest.
                environment("SOURCE_DATE_EPOCH", "1700000000")
                environment("PYTHONHASHSEED", "0")
                commandLine(
                    pythonExe.get(), "-m", "sphinx", "-t", "android", "-b", "html", "-q", "-W", "--keep-going",
                    "-d", File(scratch, "doctrees").path, helpDir.get().asFile.path, html.path,
                )
            }
        } catch (e: Exception) {
            throw GradleException(
                "Building the Android help failed. It needs Sphinx (see android/local.env.example: " +
                    "CHORD_NOTEPAD_DOCS_PYTHON, or pip install -r android/docs-requirements.txt). ${e.message}",
                e,
            )
        }
        // Keep the APK lean: build bookkeeping, and the font formats WebView
        // never asks for (it takes the woff2/woff the theme's CSS lists first).
        File(html, ".buildinfo").delete()
        File(html, "objects.inv").delete()
        html.walkBottomUp().filter { it.isFile && it.extension in setOf("ttf", "eot", "otf") }.forEach { it.delete() }
        File(html, "_static/css/fonts").listFiles { f -> f.extension == "svg" }?.forEach { it.delete() }
    }
}

val buildAndroidHelp = tasks.register<BuildAndroidHelp>("buildAndroidHelp") {
    description = "Builds the Android User Guide (sphinx -t android) into generated assets/help"
    pythonExe.set(docsPythonExe)
    helpDir.set(repoRoot.dir("help"))
    versionFile.set(repoRoot.file("VERSION"))
    scratchDir.set(layout.buildDirectory.dir("tmp/helpDoctrees"))
    outputDir.set(layout.buildDirectory.dir("generated/help/assets"))
}

androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addGeneratedSourceDirectory(exportClefGlyphs, ExportClefGlyphs::outputDir)
        variant.sources.assets?.addGeneratedSourceDirectory(buildAndroidHelp, BuildAndroidHelp::outputDir)
        variant.sources.assets?.addGeneratedSourceDirectory(copySoundfont, CopyIntoAssets::outputDir)
        variant.sources.assets?.addGeneratedSourceDirectory(copySpikeSample, CopyIntoAssets::outputDir)
        variant.sources.jniLibs?.addGeneratedSourceDirectory(prepareNativeLibs, PrepareNativeLibs::outputDir)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.process)
    implementation(libs.androidx.webkit)
    implementation(libs.kotlinx.serialization.json)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.foundation)
    implementation(libs.androidx.compose.material3)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
}

// ---------------------------------------------------------------------------
// Open source licences: AboutLibraries' plugin turns the Maven dependencies'
// POM data into aboutlibraries.json at build time (a raw resource). Offline:
// no remote licence or funding lookups, so the build needs no network beyond
// the Maven artifacts themselves. Everything the plugin can't see (Python,
// native libraries, packages, the SoundFont) is in src/main/licenses
// (docs/ANDROID.md, "Licences screen").
// ---------------------------------------------------------------------------
aboutLibraries {
    offlineMode = true
    collect {
        fetchRemoteLicense = false
        fetchRemoteFunding = false
    }
}

// The unit tests check the generated Maven licence data against the texts we
// bundle, so they run after the plugin task and get its output path.
val aboutLibrariesJsonPath: String =
    layout.buildDirectory.file("generated/aboutLibraries/debug/res/raw/aboutlibraries.json").get().asFile.path
tasks.matching { it.name == "testDebugUnitTest" }.configureEach {
    dependsOn(buildAndroidHelp)
    dependsOn(tasks.matching { it.name == "prepareLibraryDefinitionsDebug" })
    (this as Test).systemProperty("cn.aboutLibrariesJson", aboutLibrariesJsonPath)
}
