package com.chg.progeresseye.ui.screen.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Settings
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
// SettingsContent — placeholder empty state
// TODO: 계정, 알림 설정, 테마, 언어, 로그아웃 구현
// ═════════════════════════════════════════════════════════

@Composable
fun SettingsContent(modifier: Modifier = Modifier) {
    Box(
        modifier = modifier.fillMaxSize(),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Icon(
                imageVector = Icons.Outlined.Settings,
                contentDescription = null,
                tint = Slate400,
                modifier = Modifier.size(48.dp),
            )
            Text(
                text = "Settings",
                style = MaterialTheme.typography.titleMedium,
                color = Slate400,
            )
            Text(
                text = "Account, notifications, and\napp preferences.",
                style = MaterialTheme.typography.bodyMedium,
                color = Slate500,
                textAlign = TextAlign.Center,
            )
        }
    }
}
