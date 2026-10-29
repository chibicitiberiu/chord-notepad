package io.github.chibicitiberiu.chordnotepad.ui.sheets

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.chibicitiberiu.chordnotepad.ui.theme.appColors

/**
 * The frame every picker uses (docs/design/android-ui-spec.md, "Sheets"):
 * a modal bottom sheet on surface-low with a drag handle, a title row
 * ([leading] before the title, [trailing] after it), a scrollable [body]
 * and the [actions] row at the bottom, above a divider.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PickerSheet(
    title: String,
    onDismiss: () -> Unit,
    actions: @Composable RowScope.() -> Unit,
    leading: (@Composable () -> Unit)? = null,
    trailing: (@Composable () -> Unit)? = null,
    subtitle: String? = null,
    body: @Composable ColumnScope.() -> Unit,
) {
    val colors = appColors
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
        containerColor = colors.surfaceLow,
        contentColor = colors.text,
        shape = RoundedCornerShape(topStart = 18.dp, topEnd = 18.dp),
        dragHandle = {
            Box(
                Modifier.padding(top = 10.dp, bottom = 8.dp).size(width = 32.dp, height = 4.dp)
                    .clip(RoundedCornerShape(2.dp)).background(colors.grip),
            )
        },
    ) {
        Column(Modifier.padding(horizontal = 18.dp).navigationBarsPadding().padding(bottom = 12.dp)) {
            Row(
                Modifier.fillMaxWidth().padding(top = 2.dp, bottom = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                leading?.invoke()
                Text(
                    title,
                    Modifier.weight(1f).semantics { heading() },
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Medium,
                    color = colors.text,
                )
                trailing?.invoke()
            }
            if (subtitle != null) {
                Text(subtitle, fontSize = 12.sp, lineHeight = 17.sp, color = colors.muted, modifier = Modifier.padding(bottom = 6.dp))
            }
            Column(Modifier.weight(1f, fill = false).verticalScroll(rememberScrollState()), content = body)
            HorizontalDivider(Modifier.padding(top = 10.dp), color = colors.line)
            Row(
                Modifier.fillMaxWidth().padding(top = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
                content = actions,
            )
        }
    }
}

/** A row in a sheet: [leading] icon, the label, [sub] on the right, [trailing]. */
@Composable
fun SheetRow(
    label: String,
    onClick: () -> Unit,
    leading: (@Composable () -> Unit)? = null,
    sub: String? = null,
    subMonospace: Boolean = false,
    role: Role? = null,
    trailing: (@Composable () -> Unit)? = null,
) {
    val colors = appColors
    Row(
        Modifier
            .fillMaxWidth()
            .heightIn(min = 46.dp)
            .clip(RoundedCornerShape(10.dp))
            .clickable(role = role, onClick = onClick)
            .padding(horizontal = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        leading?.invoke()
        Text(label, Modifier.weight(1f), fontSize = 14.sp, color = colors.text)
        if (sub != null) {
            Text(
                sub,
                fontSize = 12.sp,
                color = colors.muted,
                fontFamily = if (subMonospace) androidx.compose.ui.text.font.FontFamily.Monospace else null,
            )
        }
        trailing?.invoke()
    }
}

/** A small uppercase section heading inside a sheet or the drawer. */
@Composable
fun SheetSection(text: String, modifier: Modifier = Modifier) {
    Text(
        text.uppercase(),
        modifier.padding(top = 12.dp, bottom = 2.dp, start = 6.dp),
        fontSize = 11.sp,
        fontWeight = FontWeight.Medium,
        letterSpacing = 0.66.sp,
        color = appColors.muted,
    )
}

/** A text button in the sheet's primary colour. */
@Composable
fun SheetTextButton(label: String, onClick: () -> Unit, enabled: Boolean = true, leading: (@Composable () -> Unit)? = null) {
    TextButton(onClick = onClick, enabled = enabled) {
        if (leading != null) {
            leading()
            Spacer(Modifier.size(6.dp))
        }
        Text(label, fontSize = 14.sp, fontWeight = FontWeight.Medium)
    }
}

/** The filled primary button that closes a sheet (Done). */
@Composable
fun SheetDoneButton(label: String, onClick: () -> Unit) {
    val colors = appColors
    androidx.compose.material3.Button(
        onClick = onClick,
        colors = androidx.compose.material3.ButtonDefaults.buttonColors(containerColor = colors.primary, contentColor = colors.onPrimary),
    ) {
        Text(label, fontSize = 14.sp, fontWeight = FontWeight.Medium)
    }
}

/** Pushes the following actions to the right. */
@Composable
fun RowScope.ActionsSpacer() {
    Spacer(Modifier.weight(1f))
}
