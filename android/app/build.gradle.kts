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

android {
    namespace = "io.github.chibicitiberiu.chordnotepad"
    // Current AndroidX/Compose releases require compiling against API 37;
    // the app still targets 36.
    compileSdk = 37
    // Only used for libc++_shared.so (the FluidSynth prebuilt needs it).
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
            // Every dependency is listed explicitly: music21's declared deps
            // pull in numpy/matplotlib/joblib, which it never imports here.
            options("--no-deps")
            if (music21Mode == "full") {
                install("music21==$music21Version")
            } else {
                // Through --find-links rather than a file path: pip records a
                // path install in direct_url.json, which made the APK depend on
                // the checkout location (M2 reproducibility check).
                options("--find-links", music21TrimmedWheel.get().asFile.parentFile.path)
                install("music21==$music21Version+cnstrip1")
            }
            // What music21 actually imports (verified by import probe).
            install("chardet==6.0.0.post1")
            install("webcolors==25.10.0")
            install("more-itertools==11.2.1")
            install("requests==2.34.2")
            install("urllib3==2.8.0")
            install("idna==3.20")
            install("certifi==2026.10.23")
            install("charset-normalizer==3.5.2")
            // Core deps
            install("pychord==1.4.0")
            install("mido==1.3.3")
            install("pyfluidsynth==1.4.0")
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
// Trimmed music21 wheel (tools/strip_music21.py), built before Chaquopy's pip.
// ---------------------------------------------------------------------------
val stripMusic21 = tasks.register<Exec>("stripMusic21") {
    description = "Builds the data-trimmed music21 wheel"
    val script = repoRoot.file("android/tools/strip_music21.py")
    inputs.file(script)
    outputs.file(music21TrimmedWheel)
    environment("CHORD_NOTEPAD_ANDROID_CACHE", androidCacheDir)
    commandLine(
        buildPythonExe, "-I", script.asFile.path,
        "--out-dir", music21TrimmedWheel.get().asFile.parentFile.path,
    )
}
if (music21Mode != "full") {
    tasks.matching { it.name.matches(Regex("install.*PythonRequirements")) }.configureEach {
        dependsOn(stripMusic21)
    }
}

// ---------------------------------------------------------------------------
// FluidSynth 2.6.0 upstream Android prebuilt (development only; M6 builds the
// natives from source). Extracted into a generated jniLibs directory together
// with libc++_shared.so from the NDK.
// ---------------------------------------------------------------------------
abstract class PrepareFluidSynth : DefaultTask() {
    @get:Input abstract val url: Property<String>
    @get:Input abstract val sha256: Property<String>
    @get:Input abstract val zipPath: Property<String>
    @get:Input abstract val abis: ListProperty<String>
    @get:Input abstract val libs: ListProperty<String>
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

    @TaskAction
    fun run() {
        val zip = File(zipPath.get())
        if (!zip.exists() || sha256Of(zip) != sha256.get()) {
            zip.parentFile.mkdirs()
            val part = File(zip.path + ".part")
            URI(url.get()).toURL().openStream().use { input -> part.outputStream().use { input.copyTo(it) } }
            part.renameTo(zip)
        }
        val actual = sha256Of(zip)
        check(actual == sha256.get()) { "FluidSynth prebuilt hash mismatch: $actual" }

        val out = outputDir.get().asFile
        out.deleteRecursively()
        val triples = mapOf("arm64-v8a" to "aarch64-linux-android", "x86_64" to "x86_64-linux-android")
        ZipFile(zip).use { zf ->
            for (abi in abis.get()) {
                val abiDir = File(out, abi).apply { mkdirs() }
                for (lib in libs.get()) {
                    val entry = zf.getEntry("lib/$abi/$lib") ?: error("missing lib/$abi/$lib in ${zip.name}")
                    zf.getInputStream(entry).use { input ->
                        File(abiDir, lib).outputStream().use { input.copyTo(it) }
                    }
                }
                val triple = triples[abi] ?: error("unknown ABI $abi")
                val cxx = libcxx.files.single { it.parentFile.name == triple }
                cxx.copyTo(File(abiDir, "libc++_shared.so"), overwrite = true)
            }
        }
    }
}

val prepareFluidSynth = tasks.register<PrepareFluidSynth>("prepareFluidSynth") {
    description = "Extracts the FluidSynth prebuilt .so files into generated jniLibs"
    url.set("https://github.com/FluidSynth/fluidsynth/releases/download/v2.6.0/fluidsynth-v2.6.0-android24.zip")
    sha256.set("81cd70dddb3381cda02c430a6657923766d1acb83de11d266d7a19aee3c7ca4d")
    zipPath.set("$androidCacheDir/fluidsynth-v2.6.0-android24.zip")
    abis.set(appAbis)
    // libfluidsynth needs liboboe and libsndfile; libsndfile needs the codecs.
    libs.set(listOf(
        "libfluidsynth.so", "liboboe.so", "libsndfile.so", "libFLAC.so", "libogg.so",
        "libopus.so", "libvorbis.so", "libvorbisenc.so", "libvorbisfile.so",
    ))
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
        variant.sources.jniLibs?.addGeneratedSourceDirectory(prepareFluidSynth, PrepareFluidSynth::outputDir)
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
