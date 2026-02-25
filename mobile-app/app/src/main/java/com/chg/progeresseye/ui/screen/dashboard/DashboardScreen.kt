package com.chg.progeresseye.ui.screen.dashboard

import androidx.compose.animation.core.EaseOutCubic
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.DesktopWindows
import androidx.compose.material.icons.outlined.Memory
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.RemoveRedEye
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Thermostat
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chg.progeresseye.ui.theme.BackgroundDark
import com.chg.progeresseye.ui.theme.OnSurfaceDark
import com.chg.progeresseye.ui.theme.Primary
import com.chg.progeresseye.ui.theme.ProgressGradientEnd
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.chg.progeresseye.ui.theme.StatusComplete
import com.chg.progeresseye.ui.theme.StatusOffline
import com.chg.progeresseye.ui.theme.StatusStalled
import com.chg.progeresseye.ui.theme.SurfaceContainerDark
import com.chg.progeresseye.ui.theme.SurfaceContainerHighDark
import com.chg.progeresseye.ui.theme.SurfaceDark

// ── Local palette (dashboard-specific) ──
private val Slate400 = Color(0xFF94A3B8)
private val Slate800 = Color(0xFF1E293B)
private val Blue300 = Color(0xFF93C5FD)
private val Emerald300 = Color(0xFF6EE7B7)
private val Emerald500 = Color(0xFF10B981)
private val Amber300 = Color(0xFFFCD34D)
private val Amber500 = Color(0xFFF59E0B)
private val Amber600 = Color(0xFFD97706)

// ── Status constants ──
private const val STATUS_RUNNING = "r"
private const val STATUS_COMPLETE = "c"
private const val STATUS_STALLED = "f"

// ── Preview model ──
private data class PreviewTask(
    val label: String,
    val progress: Float,
    val status: String,
    val subtitle: String,
)

private val previewTasks = listOf(
    PreviewTask("Premiere Rendering", 0.732f, STATUS_RUNNING, "Est. remaining time: 14 mins"),
    PreviewTask("File Download", 1.0f, STATUS_COMPLETE, "Completed at 10:42 AM"),
    PreviewTask("Installation", 0.345f, STATUS_STALLED, "No change detected for 5m"),
)

// ═════════════════════════════════════════════════════════
// DashboardScreen
// ═════════════════════════════════════════════════════════

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    onSettingsClick: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    Scaffold(
        topBar = { DashboardTopBar(onSettingsClick = onSettingsClick) },
        bottomBar = { DashboardBottomBar() },
        containerColor = BackgroundDark,
        modifier = modifier,
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item {
                DeviceCard(
                    deviceName = "DESKTOP-ABC",
                    isOnline = true,
                    tasks = previewTasks,
                )
            }
        }
    }
}

// ═════════════════════════════════════════════════════════
// Top App Bar
// ═════════════════════════════════════════════════════════

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DashboardTopBar(onSettingsClick: () -> Unit) {
    TopAppBar(
        title = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                // Logo icon
                Box(
                    modifier = Modifier
                        .size(32.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(Primary.copy(alpha = 0.20f)),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = Icons.Outlined.RemoveRedEye,
                        contentDescription = null,
                        tint = Primary,
                        modifier = Modifier.size(20.dp),
                    )
                }
                Text(
                    text = "ProgressEye",
                    fontWeight = FontWeight.Bold,
                    fontSize = 20.sp,
                    letterSpacing = (-0.3).sp,
                )
            }
        },
        actions = {
            IconButton(onClick = onSettingsClick) {
                Icon(
                    imageVector = Icons.Outlined.Settings,
                    contentDescription = "Settings",
                    tint = Slate400,
                )
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = BackgroundDark,
            titleContentColor = OnSurfaceDark,
        ),
    )
}

// ═════════════════════════════════════════════════════════
// Device Card
// ═════════════════════════════════════════════════════════

@Composable
private fun DeviceCard(
    deviceName: String,
    isOnline: Boolean,
    tasks: List<PreviewTask>,
) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = SurfaceDark,
        border = BorderStroke(1.dp, SurfaceContainerHighDark),
    ) {
        Column {
            // ── Device header ──
            DeviceHeader(name = deviceName, isOnline = isOnline)

            HorizontalDivider(color = SurfaceContainerHighDark, thickness = 1.dp)

            // ── Tasks ──
            Column(
                modifier = Modifier.padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(24.dp),
            ) {
                tasks.forEach { task ->
                    TaskItem(task = task)
                }
            }

            // ── Footer: Screenshot button ──
            ScreenshotButton()
        }
    }
}

// ═════════════════════════════════════════════════════════
// Device Header
// ═════════════════════════════════════════════════════════

@Composable
private fun DeviceHeader(
    name: String,
    isOnline: Boolean,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(20.dp),
        verticalAlignment = Alignment.Top,
    ) {
        // Device avatar
        Box(
            modifier = Modifier
                .size(48.dp)
                .clip(CircleShape)
                .background(Slate800),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = Icons.Outlined.DesktopWindows,
                contentDescription = null,
                tint = Slate400,
                modifier = Modifier.size(24.dp),
            )
        }

        Spacer(modifier = Modifier.width(16.dp))

        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            // Device name
            Text(
                text = name,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )

            // Online status
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(if (isOnline) StatusComplete else StatusOffline),
                )
                Text(
                    text = if (isOnline) "Online" else "Offline",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Medium,
                    color = if (isOnline) StatusComplete else StatusOffline,
                )
            }

            // Metric chips
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.padding(top = 4.dp),
            ) {
                MetricChip(
                    icon = Icons.Outlined.Memory,
                    value = "42%",
                    delta = "▼ 2%",
                    deltaColor = Emerald500,
                )
                MetricChip(
                    icon = Icons.Outlined.Thermostat,
                    value = "65°C",
                    delta = "▲ 1°",
                    deltaColor = Amber500,
                )
            }
        }

        // More options
        IconButton(onClick = { /* TODO */ }) {
            Icon(
                imageVector = Icons.Outlined.MoreVert,
                contentDescription = "More options",
                tint = Slate400,
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Metric Chip
// ═════════════════════════════════════════════════════════

@Composable
private fun MetricChip(
    icon: ImageVector,
    value: String,
    delta: String,
    deltaColor: Color,
) {
    Surface(
        shape = RoundedCornerShape(6.dp),
        color = Slate800.copy(alpha = 0.60f),
        border = BorderStroke(1.dp, Color(0xFF334155).copy(alpha = 0.50f)),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = Slate400,
                modifier = Modifier.size(16.dp),
            )
            Text(
                text = value,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = OnSurfaceDark,
            )
            Text(
                text = delta,
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                color = deltaColor,
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Task Item
// ═════════════════════════════════════════════════════════

@Composable
private fun TaskItem(task: PreviewTask) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        // Row 1: Label + Badge | Percentage or check icon
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = task.label,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.SemiBold,
                )
                StatusBadge(status = task.status)
            }

            when (task.status) {
                STATUS_COMPLETE -> Icon(
                    imageVector = Icons.Outlined.CheckCircle,
                    contentDescription = "Complete",
                    tint = StatusComplete,
                    modifier = Modifier.size(20.dp),
                )
                else -> {
                    val color = when (task.status) {
                        STATUS_RUNNING -> Primary
                        STATUS_STALLED -> Amber500
                        else -> Slate400
                    }
                    Text(
                        text = "%.1f%%".format(task.progress * 100),
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Medium,
                        color = color,
                    )
                }
            }
        }

        // Row 2: Progress bar
        val animatedProgress by animateFloatAsState(
            targetValue = task.progress,
            animationSpec = tween(durationMillis = 600, easing = EaseOutCubic),
            label = "progress",
        )

        GradientProgressBar(
            progress = animatedProgress,
            status = task.status,
            modifier = Modifier
                .fillMaxWidth()
                .height(8.dp),
        )

        // Row 3: Subtitle or warning
        when (task.status) {
            STATUS_STALLED -> {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Icon(
                        imageVector = Icons.Outlined.Warning,
                        contentDescription = null,
                        tint = Amber600,
                        modifier = Modifier.size(14.dp),
                    )
                    Text(
                        text = task.subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.Medium,
                        color = Amber600,
                    )
                }
            }
            else -> {
                Text(
                    text = task.subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = Slate400,
                )
            }
        }
    }
}

// ═════════════════════════════════════════════════════════
// Status Badge
// ═════════════════════════════════════════════════════════

@Composable
private fun StatusBadge(status: String) {
    val (bgColor, textColor, label) = when (status) {
        STATUS_RUNNING -> Triple(Primary.copy(alpha = 0.15f), Blue300, "Running")
        STATUS_COMPLETE -> Triple(StatusComplete.copy(alpha = 0.15f), Emerald300, "Done")
        STATUS_STALLED -> Triple(StatusStalled.copy(alpha = 0.15f), Amber300, "Stalled")
        else -> Triple(StatusOffline.copy(alpha = 0.15f), Slate400, "Unknown")
    }

    Surface(
        shape = RoundedCornerShape(4.dp),
        color = bgColor,
    ) {
        Text(
            text = label,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
            style = MaterialTheme.typography.labelSmall.copy(
                fontSize = 10.sp,
                fontWeight = FontWeight.Bold,
                letterSpacing = 0.5.sp,
            ),
            color = textColor,
        )
    }
}

// ═════════════════════════════════════════════════════════
// Gradient Progress Bar
// ═════════════════════════════════════════════════════════

@Composable
private fun GradientProgressBar(
    progress: Float,
    status: String,
    modifier: Modifier = Modifier,
) {
    Canvas(modifier = modifier.clip(RoundedCornerShape(4.dp))) {
        val cornerRadius = CornerRadius(size.height / 2f)

        // Track
        drawRoundRect(color = Slate800, cornerRadius = cornerRadius)

        // Fill
        if (progress > 0f) {
            val fillBrush = when (status) {
                STATUS_RUNNING -> Brush.horizontalGradient(
                    colors = listOf(Primary, ProgressGradientEnd),
                )
                STATUS_COMPLETE -> Brush.horizontalGradient(
                    colors = listOf(StatusComplete, StatusComplete),
                )
                STATUS_STALLED -> Brush.horizontalGradient(
                    colors = listOf(Amber500, Amber500),
                )
                else -> Brush.horizontalGradient(
                    colors = listOf(Slate400, Slate400),
                )
            }
            drawRoundRect(
                brush = fillBrush,
                size = Size(size.width * progress.coerceIn(0f, 1f), size.height),
                cornerRadius = cornerRadius,
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Screenshot Button (card footer)
// ═════════════════════════════════════════════════════════

@Composable
private fun ScreenshotButton() {
    Surface(
        color = Slate800.copy(alpha = 0.50f),
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
        ) {
            Surface(
                onClick = { /* TODO: screenshot command */ },
                shape = RoundedCornerShape(12.dp),
                color = SurfaceContainerDark,
                border = BorderStroke(1.dp, SurfaceContainerHighDark),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 14.dp),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        imageVector = Icons.Outlined.CameraAlt,
                        contentDescription = null,
                        tint = OnSurfaceDark,
                        modifier = Modifier.size(20.dp),
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Screenshot",
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.SemiBold,
                        color = OnSurfaceDark,
                    )
                }
            }
        }
    }
}

// ═════════════════════════════════════════════════════════
// Bottom Navigation Bar
// ═════════════════════════════════════════════════════════

private data class NavItem(
    val label: String,
    val icon: ImageVector,
    val selectedIcon: ImageVector,
)

private val navItems = listOf(
    NavItem("Dashboard", Icons.Outlined.Settings, Icons.Filled.Dashboard), // placeholder outlined
    NavItem("Alerts", Icons.Outlined.Notifications, Icons.Filled.Notifications),
    NavItem("Settings", Icons.Outlined.Settings, Icons.Filled.Settings),
)

@Composable
private fun DashboardBottomBar() {
    NavigationBar(
        containerColor = SurfaceDark,
        contentColor = Slate400,
        tonalElevation = 0.dp,
    ) {
        navItems.forEachIndexed { index, item ->
            val selected = index == 0
            NavigationBarItem(
                selected = selected,
                onClick = { /* TODO: navigation */ },
                icon = {
                    Icon(
                        imageVector = if (selected) item.selectedIcon else item.icon,
                        contentDescription = item.label,
                    )
                },
                label = {
                    Text(
                        text = item.label,
                        fontSize = 10.sp,
                        fontWeight = if (selected) FontWeight.SemiBold else FontWeight.Medium,
                    )
                },
                colors = NavigationBarItemDefaults.colors(
                    selectedIconColor = Primary,
                    selectedTextColor = Primary,
                    indicatorColor = Primary.copy(alpha = 0.10f),
                    unselectedIconColor = Slate400,
                    unselectedTextColor = Slate400,
                ),
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Preview
// ═════════════════════════════════════════════════════════

@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun DashboardScreenPreview() {
    ProgressEyeTheme {
        DashboardScreen()
    }
}
