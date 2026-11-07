package com.tibich.chordnotepad.ui

import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialogDefaults
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ProvideTextStyle
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.movableContentOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties

/** From this much height (above the keyboard) the dialog has Material's spacing. */
const val ROOMY_DIALOG_HEIGHT_DP = 360f

/** Under this much height, in a window at least [SIDE_DIALOG_MIN_WIDTH_DP] wide, the buttons go beside the content. */
const val SIDE_DIALOG_HEIGHT_DP = 240f
const val SIDE_DIALOG_MIN_WIDTH_DP = 480f

/** How a [KeyboardSafeAlertDialog] lays itself out in the room it has. */
enum class DialogShape {
    /** Material's: the title, the text, the buttons, spaced 24 / 16 / 24 dp. */
    ROOMY,

    /** The same, spaced 16 / 8 / 12 dp. */
    TIGHT,

    /**
     * A phone in landscape with the keyboard up (about 115 dp): a small
     * title and the text on the left, the buttons stacked on the right, so
     * the field still has room.
     */
    SIDE,
}

/** The shape for [widthDp] × [heightDp] of room above the keyboard. */
fun dialogShape(widthDp: Float, heightDp: Float): DialogShape = when {
    heightDp >= ROOMY_DIALOG_HEIGHT_DP -> DialogShape.ROOMY
    heightDp < SIDE_DIALOG_HEIGHT_DP && widthDp >= SIDE_DIALOG_MIN_WIDTH_DP -> DialogShape.SIDE
    else -> DialogShape.TIGHT
}

/**
 * An [androidx.compose.material3.AlertDialog] look-alike for dialogs with a
 * text field, which stays usable above the keyboard (L4).
 *
 * The platform dialog window panned the stock one up so the focused field
 * showed, which took the title off the top and left the buttons, the hint and
 * the error under the keyboard (phone landscape; on a tablet the title was
 * still clipped). This one draws in a window that fills the screen and keeps
 * itself inside the safe area, keyboard included: the title and the buttons
 * always show, and the [text] between them scrolls when there isn't room.
 * With very little height ([DialogShape.SIDE]) the buttons go to the right.
 * A tap outside the card dismisses it, as with the stock dialog.
 */
@Composable
fun KeyboardSafeAlertDialog(
    onDismissRequest: () -> Unit,
    confirmButton: @Composable () -> Unit,
    dismissButton: (@Composable () -> Unit)? = null,
    title: (@Composable () -> Unit)? = null,
    text: (@Composable () -> Unit)? = null,
    containerColor: Color = AlertDialogDefaults.containerColor,
) {
    Dialog(
        onDismissRequest = onDismissRequest,
        properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false),
    ) {
        BoxWithConstraints(
            Modifier
                .fillMaxSize()
                .pointerInput(onDismissRequest) { detectTapGestures { onDismissRequest() } }
                .safeDrawingPadding()
                .padding(horizontal = 24.dp, vertical = 4.dp),
            contentAlignment = Alignment.Center,
        ) {
            val shape = dialogShape(maxWidth.value, maxHeight.value)
            Surface(
                // Taps on the card don't reach the dismiss behind it.
                Modifier
                    .widthIn(min = 280.dp, max = if (shape == DialogShape.SIDE) 720.dp else 560.dp)
                    .pointerInput(Unit) { detectTapGestures { } },
                shape = AlertDialogDefaults.shape,
                color = containerColor,
                tonalElevation = AlertDialogDefaults.TonalElevation,
            ) {
                val titleSlot: @Composable (TextStyle, Dp) -> Unit = { style, gap ->
                    if (title != null) {
                        CompositionLocalProvider(LocalContentColor provides AlertDialogDefaults.titleContentColor) {
                            ProvideTextStyle(style) { Box(Modifier.padding(bottom = gap)) { title() } }
                        }
                    }
                }
                // Movable: when the keyboard comes up the shape changes, and the
                // field must move to the new layout, not be made again (that
                // dropped its selection and the keyboard's session).
                val currentText by rememberUpdatedState(text)
                val textScroll = rememberScrollState()
                val textSlot = remember {
                    movableContentOf { m: Modifier ->
                        currentText?.let { content ->
                            CompositionLocalProvider(LocalContentColor provides AlertDialogDefaults.textContentColor) {
                                ProvideTextStyle(MaterialTheme.typography.bodyMedium) {
                                    // A fade while there's more below (L9: the Loop dialog's count).
                                    Box(m.moreBelowFade(textScroll, containerColor).verticalScroll(textScroll)) { content() }
                                }
                            }
                        }
                    }
                }
                when (shape) {
                    // Every dp counts here: the field and the line under it should both show.
                    DialogShape.SIDE -> Row(Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) {
                        Column(Modifier.weight(1f, fill = false)) {
                            titleSlot(MaterialTheme.typography.titleMedium, 0.dp)
                            textSlot(Modifier.weight(1f, fill = false))
                        }
                        Column(
                            Modifier.padding(start = 16.dp),
                            horizontalAlignment = Alignment.End,
                        ) {
                            confirmButton()
                            dismissButton?.invoke()
                        }
                    }
                    else -> {
                        val roomy = shape == DialogShape.ROOMY
                        Column(Modifier.padding(if (roomy) 24.dp else 16.dp)) {
                            titleSlot(MaterialTheme.typography.headlineSmall, if (roomy) 16.dp else 8.dp)
                            textSlot(Modifier.weight(1f, fill = false).padding(bottom = if (roomy) 24.dp else 12.dp))
                            Row(
                                Modifier.align(Alignment.End),
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                dismissButton?.invoke()
                                confirmButton()
                            }
                        }
                    }
                }
            }
        }
    }
}
