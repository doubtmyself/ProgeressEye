package com.chg.progeresseye.ui.component

import androidx.annotation.StringRes
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.outlined.Dashboard
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chg.progeresseye.R
import com.chg.progeresseye.ui.theme.BackgroundDark
import com.chg.progeresseye.ui.theme.OnSurfaceDark
import com.chg.progeresseye.ui.theme.Primary

private val StatusBarColor = BackgroundDark
private val TopBarColor = BackgroundDark
private val BottomBarColor = BackgroundDark
private val Unselected = Color(0xFF94A3B8)

enum class PreviewNavTab {
    DASHBOARD,
    ALERTS,
    SETTINGS,
}

private data class PreviewNavItem(
    @param:StringRes val labelResId: Int,
    val icon: ImageVector,
    val selectedIcon: ImageVector,
)

private val previewNavItems = listOf(
    PreviewNavItem(R.string.nav_dashboard, Icons.Outlined.Dashboard, Icons.Filled.Dashboard),
    PreviewNavItem(R.string.nav_alerts, Icons.Outlined.Notifications, Icons.Filled.Notifications),
    PreviewNavItem(R.string.nav_settings, Icons.Outlined.Settings, Icons.Filled.Settings),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PreviewAppScaffold(
    selectedTab: PreviewNavTab,
    content: @Composable (PaddingValues) -> Unit,
) {
    val selectedIndex = when (selectedTab) {
        PreviewNavTab.DASHBOARD -> 0
        PreviewNavTab.ALERTS -> 1
        PreviewNavTab.SETTINGS -> 2
    }
    val current = previewNavItems[selectedIndex]

    Scaffold(
        modifier = Modifier
            .fillMaxSize()
            .background(StatusBarColor),
        topBar = {
            Column(
                modifier = Modifier
                    .statusBarsPadding()
                    .background(StatusBarColor),
            ) {
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
                                    imageVector = current.selectedIcon,
                                    contentDescription = null,
                                    tint = Primary,
                                    modifier = Modifier.size(20.dp),
                                )
                            }
                            Text(
                                text = stringResource(current.labelResId),
                                fontWeight = FontWeight.Bold,
                                fontSize = 20.sp,
                                letterSpacing = (-0.3).sp,
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = TopBarColor,
                        titleContentColor = OnSurfaceDark,
                    ),
                    windowInsets = WindowInsets(0, 0, 0, 0),
                )
                HorizontalDivider(color = Color(0xFF1E293B), thickness = 1.dp)
            }
        },
        bottomBar = {
            NavigationBar(
                containerColor = BottomBarColor,
                contentColor = Unselected,
                tonalElevation = 0.dp,
            ) {
                previewNavItems.forEachIndexed { index, item ->
                    val selected = index == selectedIndex
                    NavigationBarItem(
                        selected = selected,
                        onClick = {},
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
                            unselectedIconColor = Unselected,
                            unselectedTextColor = Unselected,
                        ),
                    )
                }
            }
        },
        containerColor = BackgroundDark,
    ) { padding ->
        content(padding)
    }
}
