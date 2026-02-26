package com.chg.progeresseye.ui.screen.alerts

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.material.icons.outlined.NotificationsNone
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.chg.progeresseye.R
import com.chg.progeresseye.data.model.AlertItem
import com.chg.progeresseye.data.model.AlertType
import com.chg.progeresseye.ui.theme.BackgroundDark
import com.chg.progeresseye.ui.theme.OnSurfaceDark
import com.chg.progeresseye.ui.theme.OnSurfaceVariantDark
import com.chg.progeresseye.ui.theme.OutlineVariantDark
import com.chg.progeresseye.ui.theme.Primary
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.chg.progeresseye.ui.theme.StatusComplete
import com.chg.progeresseye.ui.theme.StatusOffline
import com.chg.progeresseye.ui.theme.StatusStalled
import com.chg.progeresseye.ui.theme.SurfaceContainerDark

// ═════════════════════════════════════════════════════════
// AlertsContent — empty state + alert list
// TODO: Replace with FCM + local Room DB storage
// ═════════════════════════════════════════════════════════

@Composable
fun AlertsContent(modifier: Modifier = Modifier) {
    val viewModel: AlertsViewModel = viewModel()
    val alerts by viewModel.alerts.collectAsStateWithLifecycle()

    if (alerts.isEmpty()) {
        EmptyAlertsState(modifier = modifier)
    } else {
        AlertList(
            alerts = alerts,
            onAlertClick = { viewModel.markAsRead(it.id) },
            onClearAll = { viewModel.clearAll() },
            modifier = modifier,
        )
    }
}

// ═════════════════════════════════════════════════════════
// Empty State
// ═════════════════════════════════════════════════════════

@Composable
private fun EmptyAlertsState(modifier: Modifier = Modifier) {
    Box(
        modifier = modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Icon(
                imageVector = Icons.Outlined.NotificationsNone,
                contentDescription = null,
                tint = OnSurfaceVariantDark,
                modifier = Modifier.size(48.dp),
            )
            Text(
                text = stringResource(R.string.alerts_empty_title),
                style = MaterialTheme.typography.titleMedium,
                color = OnSurfaceVariantDark,
            )
            Text(
                text = stringResource(R.string.alerts_empty_body),
                style = MaterialTheme.typography.bodyMedium,
                color = StatusOffline,
                textAlign = TextAlign.Center,
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Alert List
// ═════════════════════════════════════════════════════════

@Composable
private fun AlertList(
    alerts: List<AlertItem>,
    onAlertClick: (AlertItem) -> Unit,
    onClearAll: () -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        // ── Header row: count + clear ──
        item(key = "header") {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 4.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = pluralStringResource(R.plurals.alerts_count, alerts.size, alerts.size),
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = OnSurfaceVariantDark,
                )
                TextButton(onClick = onClearAll) {
                    Text(
                        text = stringResource(R.string.alerts_clear_all),
                        style = MaterialTheme.typography.labelLarge,
                        color = Primary,
                    )
                }
            }
        }

        // ── Alert cards ──
        items(alerts, key = { it.id }) { alert ->
            AlertCard(
                alert = alert,
                onClick = { onAlertClick(alert) },
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Alert Card
// ═════════════════════════════════════════════════════════

@Composable
private fun AlertCard(alert: AlertItem, onClick: () -> Unit) {
    val (icon, tint) = alertVisuals(alert.type)

    Surface(
        shape = RoundedCornerShape(12.dp),
        color = SurfaceContainerDark,
        border = BorderStroke(1.dp, OutlineVariantDark),
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.Top,
        ) {
            // ── Icon badge ──
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(tint.copy(alpha = 0.20f)),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = tint,
                    modifier = Modifier.size(22.dp),
                )
            }

            Spacer(modifier = Modifier.width(12.dp))

            // ── Text content ──
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = alert.title,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = OnSurfaceDark,
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = alert.body,
                    style = MaterialTheme.typography.bodySmall,
                    color = OnSurfaceVariantDark,
                )
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = formatRelativeTime(alert.timestamp),
                    style = MaterialTheme.typography.labelSmall,
                    color = OnSurfaceVariantDark,
                )
            }

            // ── Unread dot ──
            if (!alert.isRead) {
                Spacer(modifier = Modifier.width(8.dp))
                Box(
                    modifier = Modifier
                        .padding(top = 6.dp)
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(Primary),
                )
            }
        }
    }
}

// ═════════════════════════════════════════════════════════
// Helpers
// ═════════════════════════════════════════════════════════

/** Returns icon + color for each [AlertType]. */
private fun alertVisuals(type: AlertType): Pair<ImageVector, Color> = when (type) {
    AlertType.COMPLETION -> Icons.Outlined.CheckCircle to StatusComplete
    AlertType.STALL      -> Icons.Outlined.Warning     to StatusStalled
    AlertType.OFFLINE    -> Icons.Outlined.CloudOff     to StatusOffline
}

/**
 * Simple relative time formatter.
 *
 * Returns "Just now", "X min ago", "X hours ago", "Yesterday", or "X days ago".
 */
@Composable
internal fun formatRelativeTime(timestamp: Long): String {
    val diff = System.currentTimeMillis() - timestamp
    val minutes = diff / 60_000
    val hours = diff / 3_600_000
    val days = diff / 86_400_000
    return when {
        minutes < 1 -> stringResource(R.string.alerts_just_now)
        minutes < 60 -> pluralStringResource(
            R.plurals.alerts_min_ago,
            minutes.toInt(),
            minutes.toInt(),
        )
        hours < 24 -> pluralStringResource(
            R.plurals.alerts_hours_ago,
            hours.toInt(),
            hours.toInt(),
        )
        hours < 48 -> stringResource(R.string.alerts_yesterday)
        else -> pluralStringResource(
            R.plurals.alerts_days_ago,
            days.toInt(),
            days.toInt(),
        )
    }
}

// ═════════════════════════════════════════════════════════
// Preview
// ═════════════════════════════════════════════════════════

private val previewAlerts = listOf(
    AlertItem(
        id = "p1",
        type = AlertType.COMPLETION,
        title = "Rendering Complete",
        body = "Premiere Pro rendering finished — 100 %.",
        deviceName = "DESKTOP-ABC",
        timestamp = System.currentTimeMillis() - 12 * 60_000,
    ),
    AlertItem(
        id = "p2",
        type = AlertType.STALL,
        title = "Download Stalled",
        body = "File download hasn't progressed in 15 min.",
        deviceName = "WORKSTATION-2",
        timestamp = System.currentTimeMillis() - 3 * 3_600_000,
    ),
    AlertItem(
        id = "p3",
        type = AlertType.OFFLINE,
        title = "Device Offline",
        body = "LAPTOP-HOME lost connection.",
        deviceName = "LAPTOP-HOME",
        timestamp = System.currentTimeMillis() - 26 * 3_600_000,
        isRead = true,
    ),
)

@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun AlertsEmptyPreview() {
    ProgressEyeTheme {
        EmptyAlertsState(modifier = Modifier.background(BackgroundDark))
    }
}

@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun AlertsListPreview() {
    ProgressEyeTheme {
        AlertList(
            alerts = previewAlerts,
            onAlertClick = {},
            onClearAll = {},
            modifier = Modifier.background(BackgroundDark),
        )
    }
}
