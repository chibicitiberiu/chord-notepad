package com.tibich.chordnotepad.audio

import android.content.Context
import android.media.AudioManager
import com.tibich.chordnotepad.bridge.AudioLaunchOptions
import java.io.File

private const val SOUNDFONT_ASSET = "soundfont/GeneralUser-GS.sf2"
private const val DEFAULT_SAMPLE_RATE = 48_000

/**
 * The audio part of the launch environment: the device's native output rate
 * and buffer size (no resampler), and the SoundFont as a real file.
 * Does I/O; call it off the main thread.
 */
fun audioLaunchOptions(context: Context): AudioLaunchOptions {
    val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    val rate = am.getProperty(AudioManager.PROPERTY_OUTPUT_SAMPLE_RATE)?.toIntOrNull() ?: DEFAULT_SAMPLE_RATE
    val frames = am.getProperty(AudioManager.PROPERTY_OUTPUT_FRAMES_PER_BUFFER)?.toIntOrNull() ?: 0
    return AudioLaunchOptions(rate, frames, installSoundfont(context).path)
}

/**
 * Copies the SoundFont from the APK's assets to filesDir (FluidSynth needs a
 * path). Copied again after an app update, in case the SoundFont changed.
 */
fun installSoundfont(context: Context): File {
    val dest = File(context.filesDir, SOUNDFONT_ASSET)
    val stamp = File(dest.path + ".stamp")
    val version = context.packageManager.getPackageInfo(context.packageName, 0).lastUpdateTime.toString()
    if (dest.isFile && stamp.isFile && stamp.readText() == version) return dest
    dest.parentFile?.mkdirs()
    val tmp = File(dest.path + ".part")
    context.assets.open(SOUNDFONT_ASSET).use { input ->
        tmp.outputStream().use { input.copyTo(it, 1 shl 16) }
    }
    check(tmp.renameTo(dest)) { "Can't move the SoundFont into place: $dest" }
    stamp.writeText(version)
    return dest
}
