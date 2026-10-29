package io.github.chibicitiberiu.chordnotepad.lifecycle

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import androidx.core.content.ContextCompat

/** [AudioFocusGateway] over `AudioManager` (music, gain, no delayed focus). */
class AndroidAudioFocusGateway(context: Context) : AudioFocusGateway {
    private val audioManager = context.applicationContext.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var request: AudioFocusRequest? = null
    private var legacyListener: AudioManager.OnAudioFocusChangeListener? = null

    override fun request(onLoss: () -> Unit): Boolean {
        val listener = AudioManager.OnAudioFocusChangeListener { change ->
            if (change == AudioManager.AUDIOFOCUS_LOSS || change == AudioManager.AUDIOFOCUS_LOSS_TRANSIENT) onLoss()
        }
        val result = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val attributes = AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                .build()
            val req = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                .setAudioAttributes(attributes)
                .setOnAudioFocusChangeListener(listener)
                .build()
            request = req
            audioManager.requestAudioFocus(req)
        } else {
            legacyListener = listener
            @Suppress("DEPRECATION")
            audioManager.requestAudioFocus(listener, AudioManager.STREAM_MUSIC, AudioManager.AUDIOFOCUS_GAIN)
        }
        return result == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
    }

    override fun abandon() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            request?.let { audioManager.abandonAudioFocusRequest(it) }
            request = null
        } else {
            @Suppress("DEPRECATION")
            legacyListener?.let { audioManager.abandonAudioFocus(it) }
            legacyListener = null
        }
    }
}

/** [NoisyGateway] as a receiver registered only while a song plays. */
class AndroidNoisyGateway(context: Context) : NoisyGateway {
    private val app = context.applicationContext
    private var receiver: BroadcastReceiver? = null

    override fun register(onNoisy: () -> Unit) {
        if (receiver != null) return
        val r = object : BroadcastReceiver() {
            override fun onReceive(context: Context, intent: Intent) {
                if (intent.action == AudioManager.ACTION_AUDIO_BECOMING_NOISY) onNoisy()
            }
        }
        // A system broadcast: delivered to a not-exported receiver too.
        ContextCompat.registerReceiver(
            app, r, IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY), ContextCompat.RECEIVER_NOT_EXPORTED,
        )
        receiver = r
    }

    override fun unregister() {
        receiver?.let { app.unregisterReceiver(it) }
        receiver = null
    }
}
