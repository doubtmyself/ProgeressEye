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
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.SwipeToDismissBox
import androidx.compose.material3.SwipeToDismissBoxValue
import androidx.compose.material3.rememberSwipeToDismissBoxState
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.material.icons.outlined.NotificationsNone
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Icon
import androidx.compose.material3.CircularProgressIndicator
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
import com.chg.progeresseye.ui.component.PreviewAppScaffold
import com.chg.progeresseye.ui.component.PreviewNavTab
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
    val isLoading by viewModel.isLoading.collectAsStateWithLifecycle()

    when {
        isLoading -> {
            Box(
                modifier = modifier.fillMaxSize(),
                contentAlignment = Alignment.Center,
            ) {
                CircularProgressIndicator(color = Primary)
            }
        }
        alerts.isEmpty() -> EmptyAlertsState(modifier = modifier)
        else -> AlertList(
            alerts = alerts,
            onAlertClick = { viewModel.markAsRead(it.id) },
            onDelete = { viewModel.deleteAlert(it.id) },
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
    onDelete: (AlertItem) -> Unit,
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
            SwipeToDismissAlertCard(
                alert = alert,
                onClick = { onAlertClick(alert) },
                onDismiss = { onDelete(alert) },
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Swipe-to-Dismiss wrapper
// ═════════════════════════════════════════════════════════

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SwipeToDismissAlertCard(
    alert: AlertItem,
    onClick: () -> Unit,
    onDismiss: () -> Unit,
) {
    val dismissState = rememberSwipeToDismissBoxState()

    LaunchedEffect(dismissState.currentValue) {
        if (dismissState.currentValue == SwipeToDismissBoxValue.EndToStart ||
            dismissState.currentValue == SwipeToDismissBoxValue.StartToEnd
        ) {
            onDismiss()
        }
    }

    SwipeToDismissBox(
        state = dismissState,
        backgroundContent = {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(StatusOffline.copy(alpha = 0.3f), RoundedCornerShape(12.dp))
                    .padding(horizontal = 20.dp),
                contentAlignment = Alignment.CenterEnd,
            ) {
                Icon(
                    imageVector = Icons.Outlined.Delete,
                    contentDescription = null,
                    tint = StatusOffline,
                )
            }
        },
    ) {
        AlertCard(alert = alert, onClick = onClick)
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
    AlertType.IMAGE_CHANGE -> Icons.Outlined.NotificationsNone to Primary
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
        title = "렌더링 완료",
        body = "Premiere Pro 렌더링이 100% 완료되었습니다.",
        deviceName = "DESKTOP-ABC",
        timestamp = System.currentTimeMillis() - 12 * 60_000,
    ),
    AlertItem(
        id = "p2",
        type = AlertType.STALL,
        title = "다운로드 정체",
        body = "15분 동안 파일 다운로드 진행이 없습니다.",
        deviceName = "WORKSTATION-2",
        timestamp = System.currentTimeMillis() - 3 * 3_600_000,
    ),
    AlertItem(
        id = "p3",
        type = AlertType.OFFLINE,
        title = "기기 오프라인",
        body = "LAPTOP-HOME 연결이 끊어졌습니다.",
        deviceName = "LAPTOP-HOME",
        timestamp = System.currentTimeMillis() - 26 * 3_600_000,
        isRead = true,
    ),
)

@Preview(showBackground = true, showSystemUi = true, locale = "ko")
@Composable
private fun AlertsEmptyPreview() {
    ProgressEyeTheme {
        EmptyAlertsState(modifier = Modifier.background(BackgroundDark))
    }
}

@Preview(showBackground = true, showSystemUi = true, locale = "ko")
@Composable
private fun AlertsListPreview() {
    ProgressEyeTheme {
        AlertList(
            alerts = previewAlerts,
            onAlertClick = {},
            onDelete = {},
            onClearAll = {},
            modifier = Modifier.background(BackgroundDark),
        )
    }
}

@Preview(showBackground = true, showSystemUi = true, locale = "ko")
@Composable
private fun AlertsScreenAppPreview() {
    ProgressEyeTheme {
        PreviewAppScaffold(selectedTab = PreviewNavTab.ALERTS) { padding ->
            AlertList(
                alerts = previewAlerts,
                onAlertClick = {},
                onDelete = {},
                onClearAll = {},
                modifier = Modifier
                    .padding(padding)
                    .background(BackgroundDark),
            )
        }
    }
}
