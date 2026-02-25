package com.chg.progeresseye.ui.screen.dashboard

import androidx.compose.animation.core.EaseOutCubic
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.rememberTransformableState
import androidx.compose.foundation.gestures.transformable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
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
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.outlined.BrokenImage
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.DesktopWindows
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil3.compose.SubcomposeAsyncImage
import coil3.request.ImageRequest
import coil3.request.crossfade
import com.chg.progeresseye.data.model.DashboardUiState
import com.chg.progeresseye.data.model.DeviceData
import com.chg.progeresseye.data.model.TaskData
import com.chg.progeresseye.data.model.TaskStatus
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
private val Amber300 = Color(0xFFFCD34D)
private val Amber500 = Color(0xFFF59E0B)
private val Amber600 = Color(0xFFD97706)

// ═════════════════════════════════════════════════════════
// DashboardContent — content only, used by MainScreen
// ═════════════════════════════════════════════════════════

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardContent(
    uiState: DashboardUiState,
    onRequestScreenshot: (deviceId: String) -> Unit = {},
    onRefresh: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    when {
        uiState.isLoading -> {
            Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = Primary)
            }
        }

        uiState.error != null -> {
            Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(
                    text = uiState.error,
                    color = Color(0xFFEF4444),
                    style = MaterialTheme.typography.bodyMedium,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(32.dp),
                )
            }
        }

        uiState.devices.isEmpty() -> {
            Box(modifier = modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        imageVector = Icons.Outlined.DesktopWindows,
                        contentDescription = null,
                        tint = Slate400,
                        modifier = Modifier.size(48.dp),
                    )
                    Spacer(modifier = Modifier.height(16.dp))
                    Text(
                        text = "No devices registered",
                        style = MaterialTheme.typography.titleMedium,
                        color = OnSurfaceDark,
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "Connect a PC with ProgressEye agent\nto start monitoring.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Slate400,
                        textAlign = TextAlign.Center,
                    )
                }
            }
        }

        else -> {
            PullToRefreshBox(
                isRefreshing = uiState.isRefreshing,
                onRefresh = onRefresh,
                modifier = modifier.fillMaxSize(),
            ) {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(16.dp),
                ) {
                    items(uiState.devices, key = { it.id }) { device ->
                        DeviceCard(
                            device = device,
                            isScreenshotLoading = uiState.screenshotLoadingDeviceId == device.id,
                            onRequestScreenshot = { onRequestScreenshot(device.id) },
                        )
                    }
            }
        }
    }
}
}

// ═════════════════════════════════════════════════════════
// Device Card
// ═════════════════════════════════════════════════════════

@Composable
private fun DeviceCard(
    device: DeviceData,
    isScreenshotLoading: Boolean,
    onRequestScreenshot: () -> Unit,
) {
    var showFullScreenshot by remember { mutableStateOf(false) }

    Surface(
        shape = RoundedCornerShape(16.dp),
        color = SurfaceDark,
        border = BorderStroke(1.dp, SurfaceContainerHighDark),
    ) {
        Column {
            DeviceHeader(name = device.name, isOnline = device.isOnline)
            HorizontalDivider(color = SurfaceContainerHighDark, thickness = 1.dp)

            if (device.tasks.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(32.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        text = "No active tasks",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Slate400,
                    )
                }
            } else {
                Column(
                    modifier = Modifier.padding(20.dp),
                    verticalArrangement = Arrangement.spacedBy(24.dp),
                ) {
                    device.tasks.forEach { task -> TaskItem(task = task) }
                }
            }

            // Screenshot preview (if available)
            if (device.screenshotUrl != null) {
                ScreenshotPreview(
                    url = device.screenshotUrl,
                    onClick = { showFullScreenshot = true },
                )
            }

            ScreenshotButton(
                isLoading = isScreenshotLoading,
                onClick = onRequestScreenshot,
            )
        }
    }

    // Fullscreen screenshot dialog
    if (showFullScreenshot && device.screenshotUrl != null) {
        FullScreenImageDialog(
            url = device.screenshotUrl,
            onDismiss = { showFullScreenshot = false },
        )
    }
}

// ═════════════════════════════════════════════════════════
// Screenshot Preview (thumbnail inside DeviceCard)
// ═════════════════════════════════════════════════════════

@Composable
private fun ScreenshotPreview(url: String, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp, vertical = 8.dp),
    ) {
        Surface(
            shape = RoundedCornerShape(12.dp),
            color = Slate800,
            border = BorderStroke(1.dp, SurfaceContainerHighDark),
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick),
        ) {
            SubcomposeAsyncImage(
                model = ImageRequest.Builder(LocalContext.current)
                    .data(url)
                    .crossfade(true)
                    .build(),
                contentDescription = "Screenshot preview",
                contentScale = ContentScale.FillWidth,
                modifier = Modifier
                    .fillMaxWidth()
                    .aspectRatio(16f / 9f)
                    .clip(RoundedCornerShape(12.dp)),
                loading = {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator(
                            color = Primary,
                            modifier = Modifier.size(24.dp),
                            strokeWidth = 2.dp,
                        )
                    }
                },
                error = {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(
                            Icons.Outlined.BrokenImage,
                            contentDescription = "Failed to load",
                            tint = Slate400,
                            modifier = Modifier.size(32.dp),
                        )
                    }
                },
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Fullscreen Image Dialog (pinch-to-zoom)
// ═════════════════════════════════════════════════════════

@Composable
private fun FullScreenImageDialog(url: String, onDismiss: () -> Unit) {
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color.Black),
        ) {
            var scale by remember { mutableFloatStateOf(1f) }
            var offset by remember { mutableStateOf(Offset.Zero) }
            val state = rememberTransformableState { zoomChange, panChange, _ ->
                scale = (scale * zoomChange).coerceIn(1f, 5f)
                offset = if (scale == 1f) Offset.Zero else offset + panChange
            }

            SubcomposeAsyncImage(
                model = ImageRequest.Builder(LocalContext.current)
                    .data(url)
                    .crossfade(true)
                    .build(),
                contentDescription = "Screenshot fullscreen",
                contentScale = ContentScale.Fit,
                modifier = Modifier
                    .fillMaxSize()
                    .graphicsLayer(
                        scaleX = scale,
                        scaleY = scale,
                        translationX = offset.x,
                        translationY = offset.y,
                    )
                    .transformable(state = state),
                loading = {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator(color = Primary)
                    }
                },
                error = {
                    Box(
                        modifier = Modifier.fillMaxSize(),
                        contentAlignment = Alignment.Center,
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Outlined.BrokenImage,
                                contentDescription = null,
                                tint = Slate400,
                                modifier = Modifier.size(48.dp),
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text("Failed to load image", color = Slate400)
                        }
                    }
                },
            )

            // Close button
            IconButton(
                onClick = onDismiss,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(16.dp),
            ) {
                Icon(
                    Icons.Filled.Close,
                    contentDescription = "Close",
                    tint = Color.White,
                    modifier = Modifier.size(28.dp),
                )
            }
        }
    }
}

// ═════════════════════════════════════════════════════════
// Device Header
// ═════════════════════════════════════════════════════════

@Composable
private fun DeviceHeader(name: String, isOnline: Boolean) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(20.dp),
        verticalAlignment = Alignment.Top,
    ) {
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
            Text(
                text = name,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
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
            // TODO: CPU usage, temperature metrics (MetricChip) — 추후 구현
        }

        IconButton(onClick = { /* TODO: device options menu */ }) {
            Icon(Icons.Outlined.MoreVert, "More options", tint = Slate400)
        }
    }
}

// ═════════════════════════════════════════════════════════
// Task Item
// ═════════════════════════════════════════════════════════

@Composable
private fun TaskItem(task: TaskData) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
                TaskStatus.COMPLETED -> Icon(
                    Icons.Outlined.CheckCircle, "Complete",
                    tint = StatusComplete, modifier = Modifier.size(20.dp),
                )

                else -> {
                    val color = when (task.status) {
                        TaskStatus.RUNNING -> Primary
                        TaskStatus.FROZEN -> Amber500
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

        val animatedProgress by animateFloatAsState(
            targetValue = task.progress,
            animationSpec = tween(durationMillis = 600, easing = EaseOutCubic),
            label = "progress",
        )
        GradientProgressBar(animatedProgress, task.status, Modifier.fillMaxWidth().height(8.dp))

        when (task.status) {
            TaskStatus.FROZEN -> {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Icon(Icons.Outlined.Warning, null, tint = Amber600, modifier = Modifier.size(14.dp))
                    Text(
                        text = "No change detected",
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.Medium,
                        color = Amber600,
                    )
                }
            }

            TaskStatus.COMPLETED -> {
                Text("Completed", style = MaterialTheme.typography.bodySmall, color = StatusComplete)
            }

            else -> {} // Running — no extra subtitle needed
        }
    }
}

// ═════════════════════════════════════════════════════════
// Status Badge
// ═════════════════════════════════════════════════════════

@Composable
private fun StatusBadge(status: String) {
    val (bgColor, textColor, label) = when (status) {
        TaskStatus.RUNNING -> Triple(Primary.copy(alpha = 0.15f), Blue300, "Running")
        TaskStatus.COMPLETED -> Triple(StatusComplete.copy(alpha = 0.15f), Emerald300, "Done")
        TaskStatus.FROZEN -> Triple(StatusStalled.copy(alpha = 0.15f), Amber300, "Stalled")
        else -> Triple(StatusOffline.copy(alpha = 0.15f), Slate400, "Unknown")
    }
    Surface(shape = RoundedCornerShape(4.dp), color = bgColor) {
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
private fun GradientProgressBar(progress: Float, status: String, modifier: Modifier = Modifier) {
    Canvas(modifier = modifier.clip(RoundedCornerShape(4.dp))) {
        val cr = CornerRadius(size.height / 2f)
        drawRoundRect(color = Slate800, cornerRadius = cr)
        if (progress > 0f) {
            val brush = when (status) {
                TaskStatus.RUNNING -> Brush.horizontalGradient(listOf(Primary, ProgressGradientEnd))
                TaskStatus.COMPLETED -> Brush.horizontalGradient(listOf(StatusComplete, StatusComplete))
                TaskStatus.FROZEN -> Brush.horizontalGradient(listOf(Amber500, Amber500))
                else -> Brush.horizontalGradient(listOf(Slate400, Slate400))
            }
            drawRoundRect(
                brush = brush,
                size = Size(size.width * progress.coerceIn(0f, 1f), size.height),
                cornerRadius = cr,
            )
        }
    }
}

// ═════════════════════════════════════════════════════════
// Screenshot Button (card footer)
// ═════════════════════════════════════════════════════════

@Composable
private fun ScreenshotButton(isLoading: Boolean, onClick: () -> Unit) {
    Surface(color = Slate800.copy(alpha = 0.50f)) {
        Box(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Surface(
                onClick = { if (!isLoading) onClick() },
                shape = RoundedCornerShape(12.dp),
                color = SurfaceContainerDark,
                border = BorderStroke(1.dp, SurfaceContainerHighDark),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 14.dp),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    if (isLoading) {
                        CircularProgressIndicator(
                            color = OnSurfaceDark,
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                        )
                    } else {
                        Icon(Icons.Outlined.CameraAlt, null, tint = OnSurfaceDark, modifier = Modifier.size(20.dp))
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = if (isLoading) "Capturing..." else "Screenshot",
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
// Preview
// ═════════════════════════════════════════════════════════

private val previewDevices = listOf(
    DeviceData(
        id = "pc_preview",
        name = "DESKTOP-ABC",
        platform = "Windows-10",
        isOnline = true,
        lastSeen = System.currentTimeMillis(),
        tasks = listOf(
            TaskData("r1", "Premiere Rendering", 0.732f, TaskStatus.RUNNING),
            TaskData("r2", "File Download", 1.0f, TaskStatus.COMPLETED),
            TaskData("r3", "Installation", 0.345f, TaskStatus.FROZEN),
        ),
    ),
)

@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun DashboardContentPreview() {
    ProgressEyeTheme {
        DashboardContent(
            uiState = DashboardUiState(isLoading = false, devices = previewDevices),
            modifier = Modifier.background(BackgroundDark),
        )
    }
}
