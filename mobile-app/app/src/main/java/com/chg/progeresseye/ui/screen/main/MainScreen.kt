package com.chg.progeresseye.ui.screen.main

import android.app.Activity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.outlined.Dashboard
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Snackbar
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.annotation.StringRes
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import com.chg.progeresseye.R
import com.chg.progeresseye.ui.screen.dashboard.DashboardUiState
import com.chg.progeresseye.domain.model.DeviceData
import com.chg.progeresseye.domain.model.TaskData
import com.chg.progeresseye.domain.model.TaskStatus
import com.chg.progeresseye.ui.screen.alerts.AlertsContent
import com.chg.progeresseye.ui.screen.dashboard.DashboardContent
import com.chg.progeresseye.ui.screen.dashboard.DashboardViewModel
import com.chg.progeresseye.ui.screen.settings.SettingsContent
import com.chg.progeresseye.ui.screen.settings.SettingsViewModel
import com.chg.progeresseye.ui.theme.BackgroundDark
import com.chg.progeresseye.ui.theme.OnSurfaceDark
import com.chg.progeresseye.ui.theme.Primary
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.chg.progeresseye.ui.theme.Slate400
import com.chg.progeresseye.ui.theme.SurfaceDark
import androidx.lifecycle.compose.LifecycleStartEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.chg.progeresseye.ui.component.BannerAd

// ── Nav items ──
private data class NavItem(
    @param:StringRes val labelResId: Int,
    val icon: ImageVector,
    val selectedIcon: ImageVector,
)

private val navItems = listOf(
    NavItem(R.string.nav_dashboard, Icons.Outlined.Dashboard, Icons.Filled.Dashboard),
    NavItem(R.string.nav_alerts, Icons.Outlined.Notifications, Icons.Filled.Notifications),
    NavItem(R.string.nav_settings, Icons.Outlined.Settings, Icons.Filled.Settings),
)

// ═════════════════════════════════════════════════════════
// MainScreen — Scaffold + BottomNav + tab content
// ═════════════════════════════════════════════════════════

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen(
    onSignOut: () -> Unit = {},
    onDeleteAccount: () -> Unit = {},
    showPrivacyButton: Boolean = false,
    onShowPrivacyOptions: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    val dashboardViewModel: DashboardViewModel = hiltViewModel()
    val settingsViewModel: SettingsViewModel = hiltViewModel()
    val dashboardState by dashboardViewModel.uiState.collectAsStateWithLifecycle()
    val userPlan by dashboardViewModel.userPlan.collectAsStateWithLifecycle()
    val isAdFreeModeEnabled by dashboardViewModel.isAdFreeModeEnabled.collectAsStateWithLifecycle()
    val adFreePassRemainingMs by dashboardViewModel.adFreePassRemainingMs.collectAsStateWithLifecycle()
    val isRewardedAdLoading by dashboardViewModel.isRewardedAdLoading.collectAsStateWithLifecycle()
    val showAllPcs by dashboardViewModel.showAllPcs.collectAsStateWithLifecycle()
    val defaultDeviceId by dashboardViewModel.defaultDeviceId.collectAsStateWithLifecycle()
    val requiresForcedSignOut = dashboardState.requiresForcedSignOut
    val context = LocalContext.current
    val activity = context as? Activity
    var selectedTab by rememberSaveable { mutableIntStateOf(0) }
    val safeSelectedTab = selectedTab.coerceIn(0, navItems.lastIndex)
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(userPlan, isAdFreeModeEnabled) {
        if (userPlan == "free" && !isAdFreeModeEnabled) {
            dashboardViewModel.loadRewardedAd(context.applicationContext)
        }
    }

    // Show screenshot error as Snackbar
    val screenshotError = dashboardState.screenshotError
    LaunchedEffect(screenshotError) {
        if (screenshotError != null) {
            snackbarHostState.showSnackbar(screenshotError)
            dashboardViewModel.clearScreenshotError()
        }
    }

    LaunchedEffect(requiresForcedSignOut) {
        if (requiresForcedSignOut) {
            dashboardViewModel.consumeForcedSignOut()
            onSignOut()
        }
    }

    // RTDB listener active only while app is in foreground (started/resumed)
    LifecycleStartEffect(dashboardViewModel) {
        dashboardViewModel.startListening()
        onStopOrDispose { dashboardViewModel.stopListening() }
    }

    // 앱 시작/포그라운드 복귀 시 구독 상태 재확인 — 만료/취소 자동 반영
    LifecycleStartEffect(settingsViewModel) {
        settingsViewModel.refreshSubscriptionStatus()
        onStopOrDispose { }
    }

    Scaffold(
        modifier = modifier.fillMaxSize(),
            snackbarHost = {
                SnackbarHost(hostState = snackbarHostState) { data ->
                    Snackbar(
                        snackbarData = data,
                        containerColor = Color(0xFF1E293B),
                        contentColor = Color(0xFFEF4444),
                        shape = RoundedCornerShape(12.dp),
                    )
                }
            },
            topBar = {
                Column(modifier = Modifier.statusBarsPadding()) {
                    if (userPlan != "pro" && !isAdFreeModeEnabled) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(SurfaceDark),
                        ) {
                            BannerAd(modifier = Modifier.fillMaxWidth())
                        }
                    }
                    val currentNav = navItems[safeSelectedTab]
                    CommonTopBar(
                        title = stringResource(currentNav.labelResId),
                        icon = currentNav.selectedIcon,
                        adFreePassRemainingMs = if (safeSelectedTab == 0) adFreePassRemainingMs else 0L,
                    )
                    HorizontalDivider(color = Color(0xFF1E293B), thickness = 1.dp)
                }
            },
            bottomBar = {
                MainBottomBar(
                    selectedIndex = safeSelectedTab,
                    onIndexSelected = { index ->
                        // if (index == 0 && safeSelectedTab == 0) {
                        //     // 대시보드 탭 재클릭 → 패스 초기화
                        //     dashboardViewModel.clearAdFreePass()
                        // }
                        selectedTab = index
                    },
                )
            },
            containerColor = BackgroundDark,
        ) { padding ->
            when (safeSelectedTab) {
                0 -> DashboardContent(
                    uiState = dashboardState,
                    userPlan = userPlan,
                    isAdFreeMode = isAdFreeModeEnabled,
                    isAdLoading = isRewardedAdLoading,
                    showAllPcs = showAllPcs,
                    defaultDeviceId = defaultDeviceId,
                    onSelectDevice = { dashboardViewModel.saveDefaultDevice(it) },
                    onDeleteDevice = { dashboardViewModel.deleteDevice(it) },
                    onRequestScreenshot = { deviceId ->
                        if (userPlan == "free" && !isAdFreeModeEnabled && adFreePassRemainingMs <= 0L && activity != null) {
                            dashboardViewModel.showRewardedAdThen(activity) { dashboardViewModel.requestScreenshot(deviceId) }
                        } else {
                            dashboardViewModel.requestScreenshot(deviceId)
                        }
                    },
                    onSleep = { deviceId ->
                        if (userPlan == "free" && !isAdFreeModeEnabled && adFreePassRemainingMs <= 0L && activity != null) {
                            dashboardViewModel.showRewardedAdThen(activity) { dashboardViewModel.sendSleepCommand(deviceId) }
                        } else {
                            dashboardViewModel.sendSleepCommand(deviceId)
                        }
                    },
                    onShutdown = { deviceId ->
                        if (userPlan == "free" && !isAdFreeModeEnabled && adFreePassRemainingMs <= 0L && activity != null) {
                            dashboardViewModel.showRewardedAdThen(activity) { dashboardViewModel.sendShutdownCommand(deviceId) }
                        } else {
                            dashboardViewModel.sendShutdownCommand(deviceId)
                        }
                    },
                    onRefresh = { dashboardViewModel.refresh() },
                    onUpgradeToPro = { selectedTab = 2 },
                    modifier = Modifier.padding(padding),
                )
                1 -> AlertsContent(modifier = Modifier.padding(padding))
                else -> SettingsContent(
                    onSignOut = onSignOut,
                    onDeleteAccount = onDeleteAccount,
                    showPrivacyButton = showPrivacyButton,
                    onShowPrivacyOptions = onShowPrivacyOptions,
                    modifier = Modifier.padding(padding),
                    viewModel = settingsViewModel,
                )
            }
        }
}

// ═════════════════════════════════════════════════════════
// Common Top Bar — icon + title, shared across all tabs
// ═════════════════════════════════════════════════════════

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CommonTopBar(title: String, icon: ImageVector, adFreePassRemainingMs: Long = 0L) {
    TopAppBar(
        title = {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Box(
                    modifier = Modifier
                        .size(32.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(Primary.copy(alpha = 0.20f)),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        imageVector = icon,
                        contentDescription = null,
                        tint = Primary,
                        modifier = Modifier.size(20.dp),
                    )
                }
                Text(
                    text = title,
                    fontWeight = FontWeight.Bold,
                    fontSize = 20.sp,
                    letterSpacing = (-0.3).sp,
                )
                if (adFreePassRemainingMs > 0L) {
                    val totalSec = adFreePassRemainingMs / 1000
                    val h = totalSec / 3600
                    val m = (totalSec % 3600) / 60
                    val s = totalSec % 60
                    val timeText = if (h > 0) "%d:%02d:%02d".format(h, m, s)
                                   else "%d:%02d".format(m, s)
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(Color(0xFF4ADE80).copy(alpha = 0.15f))
                            .padding(horizontal = 7.dp, vertical = 3.dp),
                    ) {
                        Text(
                            text = "Free $timeText",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = Color(0xFF4ADE80),
                        )
                    }
                }
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = BackgroundDark,
            titleContentColor = OnSurfaceDark,
        ),
        windowInsets = WindowInsets(0, 0, 0, 0),
    )
}

// ═════════════════════════════════════════════════════════
// Bottom Navigation Bar
// ═════════════════════════════════════════════════════════

@Composable
private fun MainBottomBar(
    selectedIndex: Int,
    onIndexSelected: (Int) -> Unit,
) {
    NavigationBar(
        containerColor = BackgroundDark,
        contentColor = Slate400,
        tonalElevation = 0.dp,
    ) {
        navItems.forEachIndexed { index, item ->
            val selected = index == selectedIndex
            NavigationBarItem(
                selected = selected,
                onClick = { onIndexSelected(index) },
                icon = {
                    Icon(
                        imageVector = if (selected) item.selectedIcon else item.icon,
                        contentDescription = stringResource(item.labelResId),
                    )
                },
                label = {
                    Text(
                        text = stringResource(item.labelResId),
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
private fun MainScreenDashboardPreview() {
    ProgressEyeTheme {
        MainScreenPreviewContent(selectedTab = 0)
    }
}

@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun MainScreenAlertsPreview() {
    ProgressEyeTheme {
        MainScreenPreviewContent(selectedTab = 1)
    }
}

@Preview(showBackground = true, showSystemUi = true)
@Composable
private fun MainScreenSettingsPreview() {
    ProgressEyeTheme {
        MainScreenPreviewContent(selectedTab = 2)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MainScreenPreviewContent(selectedTab: Int) {
    val safeSelectedTab = selectedTab.coerceIn(0, navItems.lastIndex)
    Scaffold(
        modifier = Modifier.fillMaxSize(),
        topBar = {
            Column(modifier = Modifier.statusBarsPadding()) {
                val currentNav = navItems[safeSelectedTab]
                CommonTopBar(title = stringResource(currentNav.labelResId), icon = currentNav.selectedIcon)
                HorizontalDivider(color = Color(0xFF1E293B), thickness = 1.dp)
            }
        },
        bottomBar = {
            MainBottomBar(
                selectedIndex = safeSelectedTab,
                onIndexSelected = {},
            )
        },
        containerColor = BackgroundDark,
    ) { padding ->
        when (safeSelectedTab) {
            0 -> DashboardContent(
                uiState = previewDashboardState,
                userPlan = "pro",
                modifier = Modifier.padding(padding),
            )
            1 -> PreviewTabPlaceholder(
                rows = previewAlerts,
                modifier = Modifier.padding(padding),
            )
            else -> PreviewSettingsSample(
                rows = previewSettings,
                modifier = Modifier.padding(padding),
            )
        }
    }
}

@Composable
private fun PreviewTabPlaceholder(
    rows: List<PreviewAlertRow>,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        items(rows) { row ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(SurfaceDark)
                    .padding(14.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(
                        text = row.title,
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.SemiBold,
                        color = OnSurfaceDark,
                    )
                    Text(
                        text = row.body,
                        style = MaterialTheme.typography.bodySmall,
                        color = Slate400,
                    )
                }
                Text(
                    text = row.time,
                    style = MaterialTheme.typography.labelSmall,
                    color = Slate400,
                )
            }
        }
    }
}

@Composable
private fun PreviewSettingsSample(
    rows: List<PreviewSettingRow>,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        items(rows) { row ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(SurfaceDark)
                    .padding(horizontal = 14.dp, vertical = 16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(
                        text = row.title,
                        style = MaterialTheme.typography.bodyLarge,
                        color = OnSurfaceDark,
                    )
                    row.subtitle?.let {
                        Text(
                            text = it,
                            style = MaterialTheme.typography.bodySmall,
                            color = Slate400,
                        )
                    }
                }
                Text(
                    text = row.value,
                    style = MaterialTheme.typography.labelLarge,
                    color = Primary,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }
    }
}

private data class PreviewAlertRow(
    val title: String,
    val body: String,
    val time: String,
)

private data class PreviewSettingRow(
    val title: String,
    val subtitle: String?,
    val value: String,
)

private val previewAlerts = listOf(
    PreviewAlertRow("Main Quest 완료", "DESKTOP-Preview - Main Quest가 완료되었습니다.", "방금 전"),
    PreviewAlertRow("사이드 작업 정체", "DESKTOP-Preview - 10분 동안 진행률 변화가 없습니다.", "10분 전"),
    PreviewAlertRow("PC 오프라인", "DESKTOP-Preview 연결이 끊어졌습니다.", "1시간 전"),
)

private val previewSettings = listOf(
    PreviewSettingRow("계정", "reg13@example.com", "연결됨"),
    PreviewSettingRow("완료 알림", "작업 완료 시 푸시 알림", "ON"),
    PreviewSettingRow("정체 경고", "진행률이 멈추면 경고", "ON"),
    PreviewSettingRow("테마", "현재 다크 모드", "Dark"),
)

private val previewDashboardState = DashboardUiState(
    isLoading = false,
    devices = listOf(
        DeviceData(
            id = "pc_preview",
            name = "DESKTOP-Preview",
            platform = "windows",
            isOnline = true,
            lastSeen = 0L,
            isMonitoring = true,
            tasks = listOf(
                TaskData(
                    id = "task-1",
                    label = "Main Quest",
                    progress = 0.63f,
                    status = TaskStatus.RUNNING,
                ),
                TaskData(
                    id = "task-2",
                    label = "Side Job",
                    progress = 1f,
                    status = TaskStatus.COMPLETED,
                ),
            ),
            cpuUsage = 34f,
            gpuUsage = 48f,
            ramUsage = 72f,
        ),
    ),
)
