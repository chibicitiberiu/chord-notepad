package com.tibich.chordnotepad.ui.icons

import androidx.annotation.DrawableRes
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.tibich.chordnotepad.R

/**
 * One of the app's vector icons (Material Design Icons in `res/drawable`,
 * see `android/tools/mdi_icons.py`, and our own capo and 3/4), tinted
 * [tint]. Decorative when [description] is null.
 */
@Composable
fun MdiIcon(@DrawableRes icon: Int, tint: Color, modifier: Modifier = Modifier, size: Dp = 24.dp, description: String? = null) {
    Icon(painterResource(icon), contentDescription = description, modifier = modifier.size(size), tint = tint)
}

/** The Convert notation icon's letter colours (blue C, orange Do). */
private val ConvertBlue = Color(0xFF1E88E5)
private val ConvertOrange = Color(0xFFFB8C00)

/**
 * Convert notation: a blue **C** at the top left with ↘, an orange ↖ **Do**
 * at the bottom right. The arrows are Material's `arrow_right_alt` rotated
 * (the arrow `swap_horiz` uses); the letters are Roboto Bold.
 */
@Composable
fun ConvertIcon(modifier: Modifier = Modifier) {
    val bold = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Bold, textAlign = TextAlign.Start)
    Box(modifier.size(width = 26.dp, height = 24.dp)) {
        Text("C", Modifier.offset(x = 2.dp, y = (-2).dp), color = ConvertBlue, style = bold.copy(fontSize = 13.sp, lineHeight = 13.sp))
        Icon(
            painterResource(R.drawable.ic_arrow_right_alt), null,
            Modifier.offset(x = 10.dp, y = (-1).dp).size(15.dp).rotate(45f), tint = ConvertBlue,
        )
        Icon(
            painterResource(R.drawable.ic_arrow_right_alt), null,
            Modifier.offset(x = 0.dp, y = 10.dp).size(15.dp).rotate(225f), tint = ConvertOrange,
        )
        Text("Do", Modifier.offset(x = 12.dp, y = 10.dp), color = ConvertOrange, style = bold.copy(fontSize = 11.sp, lineHeight = 11.sp))
    }
}

/** Per-function icon tints in the ribbon, sheets and drawer (the agreed mockup's). */
object IconTints {
    val Undo = Color(0xFF5C6BC0)
    val Insert = Color(0xFF2E7D32)
    val Transpose = Color(0xFF8E24AA)
    val Identify = Color(0xFF00897B)
    val Save = Color(0xFF1E88E5)
    val Tempo = Color(0xFFE53935)
    val Time = Color(0xFFEF6C00)
    val Key = Color(0xFF00897B)
    val Capo = Color(0xFFEF6C00)
    val Label = Color(0xFF8E24AA)
    val Loop = Color(0xFF1E88E5)
    val NewSong = Color(0xFF2E7D32)
    val Open = Color(0xFF1E88E5)
    val Recent = Color(0xFF8E24AA)
    val Export = Color(0xFFEF6C00)
    val Settings = Color(0xFF546E7A)
    val Guide = Color(0xFF00897B)
    val QuickStart = Color(0xFFF9A825)
    val About = Color(0xFF5C6BC0)
    val Zoom = Color(0xFF546E7A)
    val Off = Color(0xFF9E9E9E)
}
