package com.tibich.chordnotepad.ui.about

import android.widget.Toast
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.unit.dp
import com.tibich.chordnotepad.R
import com.tibich.chordnotepad.about.BuildInfo
import com.tibich.chordnotepad.about.SOURCE_URL
import com.tibich.chordnotepad.ui.icons.AppIcons

/** The id of the app's own entry in the licence list (the AGPL text). */
const val APP_LICENCE_ID = "chord-notepad"

/**
 * Help > About: name, version and build, what the app is, who wrote it, its
 * licence and source, and the way to the open source licences.
 *
 * @param onBack Leave the screen.
 * @param onOpenLicence Show the app's own licence text.
 * @param onOpenLicences Show the list of open source licences.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AboutScreen(
    info: BuildInfo,
    onBack: () -> Unit,
    onOpenLicence: () -> Unit,
    onOpenLicences: () -> Unit,
) {
    val context = LocalContext.current
    val linkFailed = stringResource(R.string.about_open_failed)
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.about_title)) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(AppIcons.ArrowBack, contentDescription = stringResource(R.string.licences_back))
                    }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 24.dp, vertical = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                stringResource(R.string.app_name),
                style = MaterialTheme.typography.headlineMedium,
                fontWeight = FontWeight.Bold,
            )
            Column(Modifier.padding(vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                InfoRow(stringResource(R.string.about_version), info.versionName)
                InfoRow(stringResource(R.string.about_build_type), info.buildType)
                InfoRow(stringResource(R.string.about_build_number), info.versionCode.toString())
                InfoRow(stringResource(R.string.about_commit), info.commit)
            }
            Text(
                stringResource(R.string.about_description),
                style = MaterialTheme.typography.bodyLarge,
                textAlign = TextAlign.Center,
                modifier = Modifier.padding(vertical = 8.dp),
            )
            Text(
                stringResource(R.string.about_copyright),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 12.dp),
            )
            LinkText(stringResource(R.string.about_license), onOpenLicence)
            LinkText(stringResource(R.string.about_source)) {
                if (!openLink(context, SOURCE_URL)) Toast.makeText(context, linkFailed, Toast.LENGTH_SHORT).show()
            }
            HorizontalDivider(Modifier.padding(vertical = 16.dp))
            ListItem(
                headlineContent = { Text(stringResource(R.string.about_licences)) },
                trailingContent = { Icon(AppIcons.ChevronRight, contentDescription = null) },
                modifier = Modifier.fillMaxWidth().clickable(onClick = onOpenLicences),
            )
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(label + ":", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun LinkText(text: String, onClick: () -> Unit) {
    Text(
        text,
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.primary,
        textDecoration = TextDecoration.Underline,
        modifier = Modifier.clickable(onClick = onClick).padding(vertical = 8.dp),
    )
}
