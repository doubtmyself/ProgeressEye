package com.chg.progeresseye.ui.screen.settings

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import coil3.compose.SubcomposeAsyncImage
import coil3.request.ImageRequest
import coil3.request.crossfade
import com.chg.progeresseye.R
import com.chg.progeresseye.ui.theme.BackgroundDark
import com.chg.progeresseye.ui.theme.ErrorRed
import com.chg.progeresseye.ui.theme.OnSurfaceDark
import com.chg.progeresseye.ui.theme.OnSurfaceVariantDark
import com.chg.progeresseye.ui.theme.OutlineDark
import com.chg.progeresseye.ui.theme.OutlineVariantDark
import com.chg.progeresseye.ui.theme.Primary
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.chg.progeresseye.ui.theme.SurfaceContainerDark
import com.google.firebase.auth.FirebaseAuth

// ═════════════════════════════════════════════════════════
// SettingsContent — account, notifications, appearance, about
// ═════════════════════════════════════════════════════════

@Composable
fun SettingsContent(
    onSignOut: () -> Unit = {},
    modifier: Modifier = Modifier,
    viewModel: SettingsViewModel = viewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val currentUser = remember { FirebaseAuth.getInstance().currentUser }
    var showLogoutDialog by remember { mutableStateOf(false) }

    // ── Logout confirmation dialog ──
    if (showLogoutDialog) {
        LogoutConfirmDialog(
            onConfirm = {
                showLogoutDialog = false
                onSignOut()
            },
            onDismiss = { showLogoutDialog = false },
        )
    }

    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .background(BackgroundDark),
        contentPadding = PaddingValues(top = 8.dp, bottom = 24.dp),
    ) {
        // ── ACCOUNT ──
        item { SectionHeader(stringResource(R.string.settings_section_account)) }
        item { Spacer(Modifier.height(8.dp)) }
        item {
            AccountCard(
                email = currentUser?.email,
                photoUrl = currentUser?.photoUrl?.toString(),
                onLogout = { showLogoutDialog = true },
            )
        }

        // ── NOTIFICATIONS ──
        item { Spacer(Modifier.height(24.dp)) }
        item { SectionHeader(stringResource(R.string.settings_section_notifications)) }
        item { Spacer(Modifier.height(8.dp)) }
        item {
            NotificationsCard(
                completionAlerts = state.completionAlerts,
                stallWarnings = state.stallWarnings,

                onToggleCompletion = viewModel::toggleCompletionAlerts,
                onToggleStall = viewModel::toggleStallWarnings,

            )
        }

        // ── APPEARANCE ──
        item { Spacer(Modifier.height(24.dp)) }
        item { SectionHeader(stringResource(R.string.settings_section_appearance)) }
        item { Spacer(Modifier.height(8.dp)) }
        item {
            AppearanceCard()
        }

        // ── ABOUT ──
        item { Spacer(Modifier.height(24.dp)) }
        item { SectionHeader(stringResource(R.string.settings_section_about)) }
        item { Spacer(Modifier.height(8.dp)) }
        item { AboutCard() }
    }
}

// ═════════════════════════════════════════════════════════
// Section header — uppercase, labelMedium
// ═════════════════════════════════════════════════════════

@Composable
private fun SectionHeader(title: String) {
    Text(
        text = title,
        style = MaterialTheme.typography.labelMedium,
        color = OnSurfaceVariantDark,
        modifier = Modifier.padding(horizontal = 16.dp),
    )
}

// ═════════════════════════════════════════════════════════
// Reusable settings card wrapper
// ═════════════════════════════════════════════════════════

@Composable
private fun SettingsCard(
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(containerColor = SurfaceContainerDark),
        border = BorderStroke(1.dp, OutlineVariantDark),
        shape = RoundedCornerShape(12.dp),
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
        content = content,
    )
}

// ═════════════════════════════════════════════════════════
// Fallback avatar (used for loading, error, and null photo)
// ═════════════════════════════════════════════════════════

@Composable
private fun FallbackAvatar(modifier: Modifier = Modifier) {
    Box(
        modifier = modifier.background(OutlineDark, CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            imageVector = Icons.Filled.Person,
            contentDescription = null,
            tint = OnSurfaceVariantDark,
            modifier = Modifier.size(28.dp),
        )
    }
}

// ═════════════════════════════════════════════════════════
// ACCOUNT card — profile photo, email, plan, logout
// ═════════════════════════════════════════════════════════

@Composable
private fun AccountCard(
    email: String?,
    photoUrl: String?,
    onLogout: () -> Unit,
) {
    SettingsCard {
        // Profile row
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            // Profile photo
            if (photoUrl != null) {
                SubcomposeAsyncImage(
                    model = ImageRequest.Builder(LocalContext.current)
                        .data(photoUrl)
                        .crossfade(true)
                        .build(),
                    contentDescription = stringResource(R.string.cd_profile_photo),
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .size(56.dp)
                        .clip(CircleShape),
                    loading = { FallbackAvatar(Modifier.fillMaxSize()) },
                    error = { FallbackAvatar(Modifier.fillMaxSize()) },
                )
            } else {
                FallbackAvatar(Modifier.size(56.dp))
            }

            Spacer(Modifier.width(16.dp))

            Column {
                Text(
                    text = email ?: stringResource(R.string.settings_no_email),
                    style = MaterialTheme.typography.titleMedium,
                    color = OnSurfaceDark,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    text = stringResource(R.string.settings_free_plan),
                    style = MaterialTheme.typography.bodySmall,
                    color = OnSurfaceVariantDark,
                )
            }
        }

        HorizontalDivider(color = OutlineVariantDark)

        // Logout button
        Box(modifier = Modifier.padding(16.dp)) {
            OutlinedButton(
                onClick = onLogout,
                border = BorderStroke(1.dp, ErrorRed.copy(alpha = 0.5f)),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = ErrorRed,
                ),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.Logout,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = stringResource(R.string.settings_logout),
                    style = MaterialTheme.typography.labelLarge,
                )
            }
        }
    }
}

// ═════════════════════════════════════════════════════════
// NOTIFICATIONS card — toggle switches
// ═════════════════════════════════════════════════════════

@Composable
private fun NotificationsCard(
    completionAlerts: Boolean,
    stallWarnings: Boolean,

    onToggleCompletion: () -> Unit,
    onToggleStall: () -> Unit,

) {
    SettingsCard {
        ToggleRow(stringResource(R.string.settings_completion_alerts), completionAlerts, onToggleCompletion)
        HorizontalDivider(color = OutlineVariantDark)
        ToggleRow(stringResource(R.string.settings_stall_warnings), stallWarnings, onToggleStall)

    }
}

@Composable
private fun ToggleRow(
    label: String,
    checked: Boolean,
    onToggle: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onToggle)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyLarge,
            color = OnSurfaceDark,
            modifier = Modifier.weight(1f),
        )
        Switch(
            checked = checked,
            onCheckedChange = null,
            colors = SwitchDefaults.colors(
                checkedThumbColor = Color.White,
                checkedTrackColor = Primary,
                checkedBorderColor = Color.Transparent,
                uncheckedThumbColor = OnSurfaceVariantDark,
                uncheckedTrackColor = OutlineDark,
                uncheckedBorderColor = Color.Transparent,
            ),
        )
    }
}

// ═════════════════════════════════════════════════════════
// APPEARANCE card — theme (disabled)
// ═════════════════════════════════════════════════════════

@Composable
private fun AppearanceCard(
) {
    SettingsCard {
        // Theme row — dark only for now
        // TODO: 라이트 모드 구현 시 Theme 선택 드롭다운 활성화
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = stringResource(R.string.settings_theme),
                style = MaterialTheme.typography.bodyLarge,
                color = OnSurfaceDark,
                modifier = Modifier.weight(1f),
            )
            Text(
                text = stringResource(R.string.settings_theme_dark),
                style = MaterialTheme.typography.bodyMedium,
                color = OnSurfaceVariantDark,
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// ABOUT card — version + licenses
// ═════════════════════════════════════════════════════════

@Composable
private fun AboutCard() {
    SettingsCard {
        // Version row
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = stringResource(R.string.settings_version),
                style = MaterialTheme.typography.bodyLarge,
                color = OnSurfaceDark,
                modifier = Modifier.weight(1f),
            )
            Text(
                text = "1.0.0",
                style = MaterialTheme.typography.bodyMedium,
                color = OnSurfaceVariantDark,
            )
        }

        HorizontalDivider(color = OutlineVariantDark)

        // Open Source Licenses
        // TODO: OSS 라이선스 화면 구현 및 네비게이션 연결
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { /* TODO: Navigate to licenses screen */ }
                .padding(horizontal = 16.dp, vertical = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = stringResource(R.string.settings_oss_licenses),
                style = MaterialTheme.typography.bodyLarge,
                color = OnSurfaceDark,
                modifier = Modifier.weight(1f),
            )
            Icon(
                imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                contentDescription = null,
                tint = OnSurfaceVariantDark,
                modifier = Modifier.size(20.dp),
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Logout confirmation dialog
// ═════════════════════════════════════════════════════════

@Composable
private fun LogoutConfirmDialog(
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = SurfaceContainerDark,
        titleContentColor = OnSurfaceDark,
        textContentColor = OnSurfaceVariantDark,
        title = {
            Text(
                text = stringResource(R.string.settings_logout_title),
                style = MaterialTheme.typography.titleLarge,
            )
        },
        text = {
            Text(
                text = stringResource(R.string.settings_logout_message),
                style = MaterialTheme.typography.bodyMedium,
            )
        },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text(
                    text = stringResource(R.string.settings_logout),
                    color = ErrorRed,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(
                    text = stringResource(R.string.settings_cancel),
                    color = OnSurfaceVariantDark,
                )
            }
        },
    )
}

@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun SettingsContentPreview() {
    ProgressEyeTheme {
        SettingsContent()
    }
}
