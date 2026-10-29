package io.github.chibicitiberiu.chordnotepad.ui.play

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.ui.icons.IconTints
import io.github.chibicitiberiu.chordnotepad.ui.icons.MdiIcon
import io.github.chibicitiberiu.chordnotepad.ui.theme.appColors

/** What the player shows. */
data class PlayerState(
    /** The song pill: "90 · 3/4 · G". */
    val pill: String,
    val playing: Boolean,
    val metronome: Boolean,
    /** The speed badge ("1.25×"), null at 100 %. */
    val speedBadge: String?,
    val sheetVisible: Boolean,
    /** Position and activity: "Bar 6/24 · Playing Em". */
    val status: String,
    /** For the buttons' descriptions. */
    val voicingLabel: String,
    val instrumentLabel: String,
)

/** What the player's buttons do. */
interface PlayerActions {
    fun songDefaults()
    fun voicing()
    fun instrument()
    fun rewind()
    fun playPause()
    fun toggleMetronome()
    fun speed()
    fun toggleSheet()
}

/**
 * The player at the bottom in Play mode (toolbar background): the song pill,
 * then voicing · instrument · ⏮ · ▶/⏸ · metronome · speed · chord sheet, then
 * the status line. The side icons are monochrome, softly tinted when on.
 * There's no Stop: ⏸ keeps the playhead, ⏮ stops and goes back to the start.
 *
 * @param compact The narrow landscape column: smaller buttons, so all seven fit.
 */
@Composable
fun Player(state: PlayerState, actions: PlayerActions, compact: Boolean, modifier: Modifier = Modifier) {
    val colors = appColors
    Column(modifier.background(colors.surface2)) {
        HorizontalDivider(color = colors.line)
        Column(Modifier.fillMaxWidth().padding(start = 10.dp, end = 10.dp, top = 2.dp, bottom = 4.dp)) {
            Row(Modifier.fillMaxWidth().height(26.dp).padding(top = 2.dp), horizontalArrangement = Arrangement.Center) {
                SongPill(state.pill, actions::songDefaults)
            }
            val side = if (compact) 38.dp else 42.dp
            Row(
                Modifier.fillMaxWidth().height(60.dp),
                horizontalArrangement = Arrangement.spacedBy(if (compact) 0.dp else 6.dp, Alignment.CenterHorizontally),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                SideButton(R.drawable.mdi_music, stringResource(R.string.player_voicing, state.voicingLabel), false, side, actions::voicing)
                SideButton(R.drawable.mdi_guitar_acoustic, stringResource(R.string.player_instrument, state.instrumentLabel), false, side, actions::instrument)
                SideButton(R.drawable.mdi_skip_previous, stringResource(R.string.player_rewind), false, side, actions::rewind)
                PlayButton(state.playing, if (compact) 48.dp else 54.dp, actions::playPause)
                SideButton(R.drawable.mdi_metronome, stringResource(R.string.player_metronome), state.metronome, side, actions::toggleMetronome)
                SideButton(
                    R.drawable.mdi_speedometer,
                    stringResource(R.string.player_speed),
                    state.speedBadge != null, side, actions::speed, badge = state.speedBadge,
                )
                SideButton(
                    R.drawable.mdi_dock_bottom,
                    stringResource(if (state.sheetVisible) R.string.player_sheet_hide else R.string.player_sheet_show),
                    state.sheetVisible, side, actions::toggleSheet,
                )
            }
            Text(
                state.status,
                Modifier.fillMaxWidth().height(16.dp),
                color = colors.muted,
                fontSize = 11.sp,
                lineHeight = 16.sp,
                textAlign = TextAlign.Center,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

/** 𝄞 90 · 3/4 · G ⌄: muted purple text, no background; opens Song defaults. */
@Composable
private fun SongPill(text: String, onClick: () -> Unit) {
    val colors = appColors
    Row(
        Modifier
            .height(26.dp)
            .clip(RoundedCornerShape(13.dp))
            .clickable(onClickLabel = stringResource(R.string.song_defaults_title), onClick = onClick)
            .padding(horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        MdiIcon(R.drawable.mdi_music_clef_treble, colors.pill, size = 15.dp)
        Text(text, color = colors.pill, fontSize = 13.sp, fontWeight = FontWeight.Medium, maxLines = 1)
        MdiIcon(R.drawable.mdi_chevron_down, IconTints.Off, size = 15.dp)
    }
}

@Composable
private fun SideButton(icon: Int, label: String, on: Boolean, size: Dp, onClick: () -> Unit, badge: String? = null) {
    val colors = appColors
    Box(Modifier.size(size)) {
        Box(
            Modifier
                .size(size)
                .clip(CircleShape)
                .background(if (on) colors.primarySoft else Color.Transparent)
                .clickable(role = Role.Button, onClick = onClick)
                .semantics {
                    contentDescription = label
                    if (on) stateDescription = "on"
                },
            contentAlignment = Alignment.Center,
        ) {
            MdiIcon(icon, if (on) colors.primary else colors.icon, size = if (size < 40.dp) 24.dp else 26.dp)
        }
        if (badge != null) {
            Text(
                badge,
                Modifier
                    .align(Alignment.TopEnd)
                    .offset(x = 4.dp, y = 2.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(colors.primary)
                    .padding(horizontal = 3.dp, vertical = 1.dp),
                color = colors.onPrimary,
                fontSize = 9.sp,
                lineHeight = 10.sp,
                fontWeight = FontWeight.Medium,
            )
        }
    }
}

/** The big round ▶/⏸ in the primary colour. */
@Composable
private fun PlayButton(playing: Boolean, size: Dp, onClick: () -> Unit) {
    val colors = appColors
    val label = stringResource(if (playing) R.string.player_pause else R.string.player_play)
    Box(
        Modifier
            .padding(horizontal = if (size < 50.dp) 2.dp else 4.dp)
            .size(size)
            .shadow(3.dp, CircleShape)
            .clip(CircleShape)
            .background(colors.primary)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = label },
        contentAlignment = Alignment.Center,
    ) {
        MdiIcon(if (playing) R.drawable.mdi_pause else R.drawable.mdi_play, colors.onPrimary, size = 34.dp)
    }
}
