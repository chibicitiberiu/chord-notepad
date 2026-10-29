package io.github.chibicitiberiu.chordnotepad.ui.main

import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.chibicitiberiu.chordnotepad.R
import io.github.chibicitiberiu.chordnotepad.ui.icons.ConvertIcon
import io.github.chibicitiberiu.chordnotepad.ui.icons.IconTints
import io.github.chibicitiberiu.chordnotepad.ui.icons.MdiIcon
import io.github.chibicitiberiu.chordnotepad.ui.theme.appColors
import kotlinx.coroutines.launch

/** What the Edit ribbon's buttons do. */
interface RibbonActions {
    fun undo()
    fun redo()
    fun insert()
    fun transpose()
    fun identify()
    fun setNotation(notation: String)
    fun convert()
}

/** The › chevron scrolls the ribbon this far. */
private const val MORE_SCROLL_DP = 140

/**
 * The Edit ribbon, one 48 dp row: Undo, Redo | Insert, Transpose, Identify |
 * AB/Do, Convert. It scrolls sideways by dragging; a fade and a › chevron
 * show there's more to the right, a fade on the left once scrolled.
 *
 * @param notation `american` or `european`, null before the session says.
 */
@Composable
fun EditRibbon(
    actions: RibbonActions,
    canUndo: Boolean,
    canRedo: Boolean,
    notation: String?,
    modifier: Modifier = Modifier,
    scroll: ScrollState = rememberScrollState(),
) {
    val colors = appColors
    val edges by remember(scroll) { derivedStateOf { RibbonEdges.of(scroll.value, scroll.maxValue) } }
    val scope = rememberCoroutineScope()
    val morePx = with(LocalDensity.current) { MORE_SCROLL_DP.dp.toPx() }
    Box(modifier.height(BAR_HEIGHT_DP.dp).background(colors.surface2)) {
        Row(
            Modifier.fillMaxHeight().horizontalScroll(scroll).padding(horizontal = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(1.dp),
        ) {
            RibbonButton(stringResource(R.string.menu_undo), enabled = canUndo, onClick = actions::undo) {
                MdiIcon(R.drawable.mdi_undo, IconTints.Undo)
            }
            RibbonButton(stringResource(R.string.menu_redo), enabled = canRedo, onClick = actions::redo) {
                MdiIcon(R.drawable.mdi_redo, IconTints.Undo)
            }
            RibbonSeparator()
            RibbonButton(stringResource(R.string.ribbon_insert), onClick = actions::insert) {
                MdiIcon(R.drawable.mdi_plus, IconTints.Insert)
            }
            RibbonButton(stringResource(R.string.ribbon_transpose), onClick = actions::transpose) {
                androidx.compose.material3.Icon(
                    painterResource(R.drawable.ic_transpose), null,
                    Modifier.size(width = 32.dp, height = 24.dp), tint = IconTints.Transpose,
                )
            }
            RibbonButton(stringResource(R.string.ribbon_identify), onClick = actions::identify) {
                MdiIcon(R.drawable.mdi_piano, IconTints.Identify)
            }
            RibbonSeparator()
            NotationSegments(notation, actions::setNotation)
            RibbonButton(stringResource(R.string.ribbon_convert), onClick = actions::convert) {
                ConvertIcon()
            }
            // Room for the chevron at the very end.
            Box(Modifier.width(24.dp))
        }
        if (edges.fadeLeft) {
            Box(
                Modifier.align(Alignment.CenterStart).width(36.dp).fillMaxHeight()
                    .background(Brush.horizontalGradient(listOf(colors.surface2, Color.Transparent))),
            )
        }
        if (edges.more) {
            Box(
                Modifier.align(Alignment.CenterEnd).width(36.dp).fillMaxHeight()
                    .background(Brush.horizontalGradient(0f to Color.Transparent, 0.7f to colors.surface2)),
            )
            Box(
                Modifier
                    .align(Alignment.CenterEnd)
                    .width(28.dp)
                    .fillMaxHeight()
                    .clickable(onClickLabel = stringResource(R.string.ribbon_more)) {
                        scope.launch { scroll.animateScrollTo((scroll.value + morePx).toInt()) }
                    },
                contentAlignment = Alignment.Center,
            ) {
                MdiIcon(R.drawable.mdi_chevron_right, colors.muted, size = 22.dp)
            }
        }
    }
}

/** One ribbon button: the icon over a small caption. */
@Composable
private fun RibbonButton(label: String, enabled: Boolean = true, onClick: () -> Unit, icon: @Composable () -> Unit) {
    val colors = appColors
    Column(
        Modifier
            .heightIn(min = 44.dp)
            .widthIn(min = 44.dp)
            .clip(RoundedCornerShape(10.dp))
            .clickable(enabled = enabled, role = Role.Button, onClick = onClick)
            .alpha(if (enabled) 1f else 0.38f)
            .padding(horizontal = 5.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(1.dp, Alignment.CenterVertically),
    ) {
        Box(Modifier.height(24.dp), contentAlignment = Alignment.Center) { icon() }
        Text(
            label,
            color = colors.text,
            fontSize = 10.sp,
            lineHeight = 12.sp,
            fontWeight = FontWeight.Medium,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.widthIn(max = 70.dp),
        )
    }
}

@Composable
private fun RibbonSeparator() {
    Box(Modifier.padding(horizontal = 4.dp).width(1.dp).height(28.dp).background(appColors.line))
}

/** AB | Do: the notation the text is read in. */
@Composable
private fun NotationSegments(notation: String?, onSelect: (String) -> Unit) {
    val colors = appColors
    val shape = RoundedCornerShape(15.dp)
    Row(
        Modifier
            .padding(horizontal = 2.dp)
            .height(30.dp)
            .clip(shape)
            .border(1.dp, colors.line, shape)
            .selectableGroup(),
    ) {
        for ((value, label) in listOf("american" to R.string.notation_american, "european" to R.string.notation_european)) {
            val on = notation == value
            Box(
                Modifier
                    .fillMaxHeight()
                    .background(if (on) colors.primarySoft else colors.surfaceLow)
                    .selectable(selected = on, role = Role.RadioButton) { if (!on) onSelect(value) }
                    .padding(horizontal = 9.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    stringResource(label),
                    color = if (on) colors.primary else colors.muted,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Medium,
                )
            }
        }
    }
}

/** A floating Undo / Redo chip, shown above the keyboard while the header is collapsed. */
@Composable
fun FloatingUndoChip(actions: RibbonActions, canUndo: Boolean, canRedo: Boolean, modifier: Modifier = Modifier) {
    val colors = appColors
    androidx.compose.material3.Surface(
        modifier,
        shape = RoundedCornerShape(22.dp),
        color = colors.surface,
        shadowElevation = 4.dp,
    ) {
        Row {
            BarIconButton(R.drawable.mdi_undo, stringResource(R.string.menu_undo), IconTints.Undo.copy(alpha = if (canUndo) 1f else 0.38f), actions::undo, Modifier.size(40.dp))
            BarIconButton(R.drawable.mdi_redo, stringResource(R.string.menu_redo), IconTints.Undo.copy(alpha = if (canRedo) 1f else 0.38f), actions::redo, Modifier.size(40.dp))
        }
    }
}
