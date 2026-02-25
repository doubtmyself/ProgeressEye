package com.chg.progeresseye.ui.screen.alerts

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.NotificationsNone
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

// ── Local palette ──
private val Slate400 = Color(0xFF94A3B8)
private val Slate500 = Color(0xFF64748B)

// ═════════════════════════════════════════════════════════
// AlertsContent — placeholder empty state
// TODO: 실제 알림 목록 구현 (FCM + RTDB 연동)
// ═════════════════════════════════════════════════════════

@Composable
fun AlertsContent(modifier: Modifier = Modifier) {
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
                tint = Slate400,
                modifier = Modifier.size(48.dp),
            )
            Text(
                text = "No alerts yet",
                style = MaterialTheme.typography.titleMedium,
                color = Slate400,
            )
            Text(
                text = "Alerts will appear here when\ntasks complete or stall.",
                style = MaterialTheme.typography.bodyMedium,
                color = Slate500,
                textAlign = TextAlign.Center,
            )
        }
    }
}
