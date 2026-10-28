import java.io.File
import java.net.URI
import java.security.MessageDigest
import java.util.zip.ZipFile

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.chaquopy)
}

// ---------------------------------------------------------------------------
// Version: versionName comes from the repo's VERSION file. versionCode is
// (MAJ*10000 + MIN*100 + PATCH)*10 + rebuild, written as a literal on purpose
// (docs/ANDROID_PORT_PLAN.md, "Version scheme"); a test will check the pair.
// ---------------------------------------------------------------------------
val repoRoot: Directory = rootProject.layout.projectDirectory.dir("..")
val appVersionName: String = providers.fileContents(repoRoot.file("VERSION")).asText.get().trim()
val appVersionCode = 4010

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

androidComponents {
    onVariants { variant ->
        variant.sources.assets?.addGeneratedSourceDirectory(copySoundfont, CopyIntoAssets::outputDir)
        variant.sources.assets?.addGeneratedSourceDirectory(copySpikeSample, CopyIntoAssets::outputDir)
        variant.sources.jniLibs?.addGeneratedSourceDirectory(prepareNativeLibs, PrepareNativeLibs::outputDir)
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.foundation)
    implementation(libs.androidx.compose.material3)
}
