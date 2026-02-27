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
import com.chg.progeresseye.R
import com.chg.progeresseye.data.model.DashboardUiState
import com.chg.progeresseye.data.model.DeviceData
import com.chg.progeresseye.data.model.TaskData
import com.chg.progeresseye.data.model.TaskStatus
import com.chg.progeresseye.ui.screen.alerts.AlertsContent
import com.chg.progeresseye.ui.screen.dashboard.DashboardContent
import com.chg.progeresseye.ui.screen.dashboard.DashboardViewModel
import com.chg.progeresseye.ui.screen.settings.SettingsContent
import com.chg.progeresseye.ui.theme.BackgroundDark
import com.chg.progeresseye.ui.theme.OnSurfaceDark
import com.chg.progeresseye.ui.theme.Primary
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.chg.progeresseye.ui.theme.SurfaceDark
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.compose.LifecycleStartEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.chg.progeresseye.ui.component.BannerAd

// ── Local palette ──
private val Slate400 = Color(0xFF94A3B8)

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
    modifier: Modifier = Modifier,
) {
    val dashboardViewModel: DashboardViewModel = viewModel()
    val dashboardState by dashboardViewModel.uiState.collectAsStateWithLifecycle()
    val userPlan by dashboardViewModel.userPlan.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val activity = context as? Activity
    var selectedTab by rememberSaveable { mutableIntStateOf(0) }
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(userPlan) {
        if (userPlan == "free") {
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

    // RTDB listener active only while app is in foreground (started/resumed)
    LifecycleStartEffect(dashboardViewModel) {
        dashboardViewModel.startListening()
        onStopOrDispose { dashboardViewModel.stopListening() }
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
                    if (userPlan != "pro") {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(SurfaceDark),
                        ) {
                            BannerAd(modifier = Modifier.fillMaxWidth())
                        }
                    }
                    val currentNav = navItems[selectedTab]
                    CommonTopBar(title = stringResource(currentNav.labelResId), icon = currentNav.selectedIcon)
                    HorizontalDivider(color = Color(0xFF1E293B), thickness = 1.dp)
                }
            },
            bottomBar = {
                MainBottomBar(
                    selectedIndex = selectedTab,
                    onIndexSelected = { selectedTab = it },
                )
            },
            containerColor = BackgroundDark,
        ) { padding ->
            when (selectedTab) {
                0 -> DashboardContent(
                    uiState = dashboardState,
                    userPlan = userPlan,
                    onRequestScreenshot = { deviceId ->
                        if (userPlan == "free" && activity != null) {
                            dashboardViewModel.showRewardedAdThenScreenshot(activity, deviceId)
                        } else {
                            dashboardViewModel.requestScreenshot(deviceId)
                        }
                    },
                    onRefresh = { dashboardViewModel.refresh() },
                    modifier = Modifier.padding(padding),
                )
                1 -> AlertsContent(modifier = Modifier.padding(padding))
                2 -> SettingsContent(onSignOut = onSignOut, modifier = Modifier.padding(padding))
            }
        }
}

// ═════════════════════════════════════════════════════════
// Common Top Bar — icon + title, shared across all tabs
// ═════════════════════════════════════════════════════════

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CommonTopBar(title: String, icon: ImageVector) {
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
        containerColor = SurfaceDark,
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
    Scaffold(
        modifier = Modifier.fillMaxSize(),
        topBar = {
            Column(modifier = Modifier.statusBarsPadding()) {
                val currentNav = navItems[selectedTab]
                CommonTopBar(title = stringResource(currentNav.labelResId), icon = currentNav.selectedIcon)
                HorizontalDivider(color = Color(0xFF1E293B), thickness = 1.dp)
            }
        },
        bottomBar = {
            MainBottomBar(
                selectedIndex = selectedTab,
                onIndexSelected = {},
            )
        },
        containerColor = BackgroundDark,
    ) { padding ->
        when (selectedTab) {
            0 -> DashboardContent(
                uiState = previewDashboardState,
                userPlan = "pro",
                modifier = Modifier.padding(padding),
            )
            1 -> AlertsContent(modifier = Modifier.padding(padding))
            else -> SettingsContent(
                onSignOut = {},
                modifier = Modifier.padding(padding),
            )
        }
    }
}

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
