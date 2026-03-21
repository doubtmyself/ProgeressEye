package com.chg.progeresseye.ui.screen.settings

import android.app.Activity
import android.content.Intent
import android.widget.Toast
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
import androidx.compose.material.icons.filled.PersonRemove
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil3.compose.SubcomposeAsyncImage
import coil3.request.ImageRequest
import coil3.request.crossfade
import com.chg.progeresseye.R
import com.chg.progeresseye.ui.component.PreviewAppScaffold
import com.chg.progeresseye.ui.component.PreviewNavTab
import com.chg.progeresseye.ui.theme.BackgroundDark
import com.chg.progeresseye.ui.theme.ErrorRed
import com.chg.progeresseye.ui.theme.OnSurfaceDark
import com.chg.progeresseye.ui.theme.OnSurfaceVariantDark
import com.chg.progeresseye.ui.theme.OutlineDark
import com.chg.progeresseye.ui.theme.OutlineVariantDark
import com.chg.progeresseye.ui.theme.Primary
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.chg.progeresseye.ui.theme.SurfaceContainerDark
import com.chg.progeresseye.util.isPro
import com.google.firebase.auth.FirebaseAuth

// ═════════════════════════════════════════════════════════
// SettingsContent — account, notifications, appearance, about
// ═════════════════════════════════════════════════════════

/**
 * 설정 화면의 전체 컨텐츠를 구성하는 최상위 컴포저블입니다.
 * 계정 정보, 알림 설정, 앱 정보(버전, 약관 등) 섹션으로 구성됩니다.
 *
 * @param onSignOut 로그아웃 실행 콜백
 * @param onDeleteAccount 계정 삭제 실행 콜백
 * @param showPrivacyButton 개인정보 보호 옵션 버튼 표시 여부
 * @param onShowPrivacyOptions 개인정보 보호 옵션 클릭 콜백
 * @param modifier 컴포저블에 적용할 Modifier
 * @param viewModel 설정 화면의 상태를 관리하는 ViewModel
 */
@Composable
fun SettingsContent(
    onSignOut: () -> Unit = {},
    onDeleteAccount: () -> Unit = {},
    showPrivacyButton: Boolean = false,
    onShowPrivacyOptions: () -> Unit = {},
    modifier: Modifier = Modifier,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val currentUser = FirebaseAuth.getInstance().currentUser
    val activity = context as? Activity
    var showLogoutDialog by remember { mutableStateOf(false) }
    var showDeleteAccountDialog by remember { mutableStateOf(false) }

    LaunchedEffect(currentUser?.uid) {
        if (currentUser == null) {
            showLogoutDialog = false
            showDeleteAccountDialog = false
        }
    }

    LaunchedEffect(state.billingMessage) {
        val message = state.billingMessage ?: return@LaunchedEffect
        Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
        viewModel.clearBillingMessage()
    }

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

    // ── Delete account confirmation dialog ──
    if (showDeleteAccountDialog) {
        DeleteAccountConfirmDialog(
            onConfirm = {
                showDeleteAccountDialog = false
                onDeleteAccount()
            },
            onDismiss = { showDeleteAccountDialog = false },
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
                isProPlan = state.currentPlan == "pro",
                planLabel = if (state.currentPlan == "pro") {
                    stringResource(R.string.settings_pro_plan)
                } else {
                    stringResource(R.string.settings_free_plan)
                },
                subscriptionPrice = state.subscriptionPrice,
                isAdFreeMode = state.isAdFreeMode,
                isPolicyLoaded = state.isPolicyLoaded,
                canStartSubscription = activity != null && state.isBillingReady && !state.isPurchaseLoading,
                isPurchaseLoading = state.isPurchaseLoading,
                onStartSubscription = {
                    activity?.let { viewModel.startProSubscription(it) }
                },
                onLogout = { showLogoutDialog = true },
                onDeleteAccount = { showDeleteAccountDialog = true },
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

        // ── DISPLAY ──
        if (!state.currentPlan.isPro() && !state.isAdFreeMode) {
            item { Spacer(Modifier.height(24.dp)) }
            item { SectionHeader(stringResource(R.string.settings_section_display)) }
            item { Spacer(Modifier.height(8.dp)) }
            item {
                DisplayCard(
                    showAllPcs = state.showAllPcs,
                    onToggleShowAllPcs = viewModel::toggleShowAllPcs,
                )
            }
        }

        // ── ABOUT ──
        item { Spacer(Modifier.height(24.dp)) }
        item { SectionHeader(stringResource(R.string.settings_section_about)) }
        item { Spacer(Modifier.height(8.dp)) }
        item { AboutCard(showPrivacyButton = showPrivacyButton, onShowPrivacyOptions = onShowPrivacyOptions) }
    }
}

// ═════════════════════════════════════════════════════════
// Section header — uppercase, labelMedium
// ═════════════════════════════════════════════════════════

/**
 * 설정 화면의 각 섹션 제목을 표시하는 헤더 컴포저블입니다.
 *
 * @param title 표시할 섹션 제목
 */
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

/**
 * 설정 화면에서 사용하는 공통 카드 스타일의 컨테이너입니다.
 *
 * @param modifier 컴포저블에 적용할 Modifier
 * @param content 카드 내부에 표시될 컨텐츠
 */
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

/**
 * 프로필 이미지를 불러올 수 없을 때 표시할 기본 아바타 아이콘입니다.
 *
 * @param modifier 컴포저블에 적용할 Modifier
 */
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

/**
 * 사용자 계정 정보를 표시하고 구독 관리 및 로그아웃/탈퇴 기능을 제공하는 카드입니다.
 *
 * @param email 사용자 이메일
 * @param photoUrl 프로필 이미지 URL
 * @param isProPlan 현재 Pro 플랜 사용 여부
 * @param planLabel 플랜 이름 라벨
 * @param subscriptionPrice 포맷팅된 구독 가격 문자열
 * @param isAdFreeMode 전역 광고 제거 모드 활성화 여부
 * @param isPolicyLoaded 정책 정보 로드 완료 여부
 * @param canStartSubscription 구독 시작 가능 여부
 * @param isPurchaseLoading 구매 처리 중 여부
 * @param onStartSubscription 구독 버튼 클릭 콜백
 * @param onLogout 로그아웃 버튼 클릭 콜백
 * @param onDeleteAccount 계정 삭제 버튼 클릭 콜백
 */
@Composable
private fun AccountCard(
    email: String?,
    photoUrl: String?,
    isProPlan: Boolean,
    planLabel: String,
    subscriptionPrice: String?,
    isAdFreeMode: Boolean,
    isPolicyLoaded: Boolean,
    canStartSubscription: Boolean,
    isPurchaseLoading: Boolean,
    onStartSubscription: () -> Unit,
    onLogout: () -> Unit,
    onDeleteAccount: () -> Unit,
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
                    text = planLabel,
                    style = MaterialTheme.typography.bodySmall,
                    color = OnSurfaceVariantDark,
                )
            }
        }

        HorizontalDivider(color = OutlineVariantDark)

        if (isPolicyLoaded && !isAdFreeMode) {
            SubscriptionSection(
                isProPlan = isProPlan,
                subscriptionPrice = subscriptionPrice,
                canStartSubscription = canStartSubscription,
                isPurchaseLoading = isPurchaseLoading,
                onStartSubscription = onStartSubscription,
            )
            HorizontalDivider(color = OutlineVariantDark)
        }

        // Logout button
        Box(modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 16.dp)) {
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

        // Delete account button
        Box(modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 16.dp)) {
            OutlinedButton(
                onClick = onDeleteAccount,
                border = BorderStroke(1.dp, ErrorRed.copy(alpha = 0.5f)),
                colors = ButtonDefaults.outlinedButtonColors(
                    contentColor = ErrorRed,
                ),
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(
                    imageVector = Icons.Filled.PersonRemove,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = stringResource(R.string.settings_delete_account),
                    style = MaterialTheme.typography.labelLarge,
                )
            }
        }
    }
}

/**
 * 계정 카드 내에서 구독 혜택 정보 및 구매 버튼을 제공하는 섹션입니다.
 *
 * @param isProPlan 현재 Pro 플랜 여부
 * @param subscriptionPrice 구독 가격 문자열
 * @param canStartSubscription 버튼 활성화 여부
 * @param isPurchaseLoading 구매 진행 중 여부
 * @param onStartSubscription 구매 시작 버튼 클릭 콜백
 */
@Composable
private fun SubscriptionSection(
    isProPlan: Boolean,
    subscriptionPrice: String?,
    canStartSubscription: Boolean,
    isPurchaseLoading: Boolean,
    onStartSubscription: () -> Unit,
) {
    Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
        Text(
            text = stringResource(R.string.settings_subscription_title),
            style = MaterialTheme.typography.bodyLarge,
            color = OnSurfaceDark,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(Modifier.height(4.dp))
        Text(
            text = if (isProPlan) {
                stringResource(R.string.settings_subscription_active)
            } else {
                subscriptionPrice?.let { price ->
                    stringResource(R.string.settings_subscription_price_format, price)
                } ?: stringResource(R.string.settings_subscription_price_fallback)
            },
            style = MaterialTheme.typography.bodySmall,
            color = OnSurfaceVariantDark,
        )

        if (!isProPlan) {
            Spacer(Modifier.height(8.dp))
            listOf(
                stringResource(R.string.settings_subscription_benefit_ads),
                stringResource(R.string.settings_subscription_benefit_pcs),
            ).forEach { benefit ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "✓",
                        style = MaterialTheme.typography.bodySmall,
                        color = Primary,
                        modifier = Modifier.padding(end = 6.dp),
                    )
                    Text(
                        text = benefit,
                        style = MaterialTheme.typography.bodySmall,
                        color = OnSurfaceVariantDark,
                    )
                }
                Spacer(Modifier.height(2.dp))
            }
        }

        if (!isProPlan) {
            Spacer(Modifier.height(12.dp))
            OutlinedButton(
                onClick = onStartSubscription,
                enabled = canStartSubscription,
                shape = RoundedCornerShape(8.dp),
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (isPurchaseLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                    )
                    Spacer(Modifier.width(8.dp))
                }
                Text(
                    text = stringResource(R.string.settings_subscription_start_button),
                    style = MaterialTheme.typography.labelLarge,
                )
            }
        }
    }
}

// ═════════════════════════════════════════════════════════
// NOTIFICATIONS card — toggle switches
// ═════════════════════════════════════════════════════════

/**
 * 푸시 알림 설정(완료 알림, 정체 경고) 스위치를 포함하는 카드입니다.
 *
 * @param completionAlerts 완료 알림 켜짐 여부
 * @param stallWarnings 정체 경고 켜짐 여부
 * @param onToggleCompletion 완료 알림 토글 콜백
 * @param onToggleStall 정체 경고 토글 콜백
 */
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
private fun DisplayCard(
    showAllPcs: Boolean,
    onToggleShowAllPcs: () -> Unit,
) {
    SettingsCard {
        ToggleRow(stringResource(R.string.settings_show_all_pcs), showAllPcs, onToggleShowAllPcs)
    }
}

/**
 * 텍스트 라벨과 스위치가 있는 단일 설정 행입니다.
 *
 * @param label 표시할 설정 항목 이름
 * @param checked 현재 선택 상태
 * @param onToggle 클릭 시 호출되는 콜백
 */
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
// Generic clickable row — reused in AboutCard
// ═════════════════════════════════════════════════════════

/**
 * 클릭이 가능하고 우측에 추가 컨텐츠를 배치할 수 있는 범용 설정 행입니다.
 *
 * @param label 행의 제목
 * @param onClick 클릭 시 호출되는 콜백
 * @param trailing 우측 끝에 배치할 컴포저블 (예: 화살표 아이콘)
 */
@Composable
private fun ClickableSettingRow(
    label: String,
    onClick: () -> Unit,
    trailing: @Composable (() -> Unit)? = null,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyLarge,
            color = OnSurfaceDark,
            modifier = Modifier.weight(1f),
        )
        trailing?.invoke()
    }
}

// ═════════════════════════════════════════════════════════
// ABOUT card — version + licenses
// ═════════════════════════════════════════════════════════

/**
 * 앱 버전, 개인정보 처리방침, 오픈소스 라이선스 정보를 포함하는 카드입니다.
 *
 * @param showPrivacyButton 광고 개인정보 설정 버튼 표시 여부
 * @param onShowPrivacyOptions 광고 개인정보 설정 클릭 콜백
 */
@Composable
private fun AboutCard(
    showPrivacyButton: Boolean = false,
    onShowPrivacyOptions: () -> Unit = {},
) {
    val context = LocalContext.current
    val configuration = LocalConfiguration.current
    val uriHandler = LocalUriHandler.current
    val lang = configuration.locales[0]?.language ?: "en"
    val policyUrl = if (lang.startsWith("ko")) {
        "https://progresseye-49244.web.app/?lang=ko"
    } else {
        "https://progresseye-49244.web.app/?lang=en"
    }

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
                text = LocalContext.current.packageManager
                    .getPackageInfo(LocalContext.current.packageName, 0).versionName ?: "?",
                style = MaterialTheme.typography.bodyMedium,
                color = OnSurfaceVariantDark,
            )
        }

        HorizontalDivider(color = OutlineVariantDark)

        // Privacy policy
        ClickableSettingRow(
            label = stringResource(R.string.settings_privacy_policy),
            onClick = { uriHandler.openUri(policyUrl) },
            trailing = {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                    contentDescription = null,
                    tint = OnSurfaceVariantDark,
                    modifier = Modifier.size(20.dp),
                )
            },
        )

        // 광고 개인정보 설정 (미국 사용자 전용 — CCPA)
        if (showPrivacyButton) {
            HorizontalDivider(color = OutlineVariantDark)
            ClickableSettingRow(
                label = stringResource(R.string.settings_ad_privacy),
                onClick = onShowPrivacyOptions,
                trailing = {
                    Text(
                        text = stringResource(R.string.settings_ad_reward_personalized),
                        style = MaterialTheme.typography.bodyMedium,
                        color = OnSurfaceVariantDark,
                    )
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                        contentDescription = null,
                        tint = OnSurfaceVariantDark,
                        modifier = Modifier.size(20.dp),
                    )
                },
            )
        }

        HorizontalDivider(color = OutlineVariantDark)

        // Open Source Licenses
        ClickableSettingRow(
            label = stringResource(R.string.settings_oss_licenses),
            onClick = {
                val intent = Intent(context, OssLicensesActivity::class.java)
                if (context !is Activity) {
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                }
                context.startActivity(intent)
            },
            trailing = {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.KeyboardArrowRight,
                    contentDescription = null,
                    tint = OnSurfaceVariantDark,
                    modifier = Modifier.size(20.dp),
                )
            },
        )
    }
}

// ═════════════════════════════════════════════════════════
// Generic confirmation dialog — reused by Logout and DeleteAccount
// ═════════════════════════════════════════════════════════

/**
 * 로그아웃이나 계정 삭제 등을 위한 범용 확인 다이얼로그입니다.
 *
 * @param title 다이얼로그 제목
 * @param message 다이얼로그 본문
 * @param confirmText 확인 버튼 텍스트
 * @param onConfirm 확인 클릭 콜백
 * @param onDismiss 취소/닫기 클릭 콜백
 */
@Composable
private fun ConfirmationDialog(
    title: String,
    message: String,
    confirmText: String,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = SurfaceContainerDark,
        titleContentColor = OnSurfaceDark,
        textContentColor = OnSurfaceVariantDark,
        title = { Text(text = title, style = MaterialTheme.typography.titleLarge) },
        text = { Text(text = message, style = MaterialTheme.typography.bodyMedium) },
        confirmButton = {
            TextButton(onClick = onConfirm) {
                Text(text = confirmText, color = ErrorRed, fontWeight = FontWeight.SemiBold)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text(text = stringResource(R.string.settings_cancel), color = OnSurfaceVariantDark)
            }
        },
    )
}

// ═════════════════════════════════════════════════════════
// Logout confirmation dialog
// ═════════════════════════════════════════════════════════

/**
 * 로그아웃 의사를 재확인하는 전용 다이얼로그입니다.
 *
 * @param onConfirm 로그아웃 확인 시 호출
 * @param onDismiss 로그아웃 취소 시 호출
 */
@Composable
private fun LogoutConfirmDialog(onConfirm: () -> Unit, onDismiss: () -> Unit) {
    ConfirmationDialog(
        title = stringResource(R.string.settings_logout_title),
        message = stringResource(R.string.settings_logout_message),
        confirmText = stringResource(R.string.settings_logout),
        onConfirm = onConfirm,
        onDismiss = onDismiss,
    )
}

// ═════════════════════════════════════════════════════════
// Delete account confirmation dialog
// ═════════════════════════════════════════════════════════

/**
 * 계정 삭제 의사를 재확인하는 전용 다이얼로그입니다.
 *
 * @param onConfirm 삭제 확인 시 호출
 * @param onDismiss 삭제 취소 시 호출
 */
@Composable
private fun DeleteAccountConfirmDialog(onConfirm: () -> Unit, onDismiss: () -> Unit) {
    ConfirmationDialog(
        title = stringResource(R.string.settings_delete_account_title),
        message = stringResource(R.string.settings_delete_account_message),
        confirmText = stringResource(R.string.settings_delete_account_confirm),
        onConfirm = onConfirm,
        onDismiss = onDismiss,
    )
}

@Preview(showBackground = true, showSystemUi = true, locale = "ko")
@Composable
private fun SettingsContentPreview() {
    ProgressEyeTheme {
        PreviewAppScaffold(selectedTab = PreviewNavTab.SETTINGS) { padding ->
            SettingsPreviewBody(modifier = Modifier.padding(padding))
        }
    }
}

/**
 * 설정 화면의 레이아웃 구성을 보여주기 위한 프리뷰용 바디 컴포저블입니다.
 *
 * @param modifier 컴포저블에 적용할 Modifier
 */
@Composable
private fun SettingsPreviewBody(modifier: Modifier = Modifier) {
    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .background(BackgroundDark),
        contentPadding = PaddingValues(top = 8.dp, bottom = 24.dp),
    ) {
        item { SectionHeader(stringResource(R.string.settings_section_account)) }
        item { Spacer(Modifier.height(8.dp)) }
        item {
            AccountCard(
                email = "reg13@example.com",
                photoUrl = null,
                isProPlan = false,
                planLabel = stringResource(R.string.settings_free_plan),
                subscriptionPrice = "\u20a93,000",
                isAdFreeMode = false,
                isPolicyLoaded = true,
                canStartSubscription = true,
                isPurchaseLoading = false,
                onStartSubscription = {},
                onLogout = {},
                onDeleteAccount = {},
            )
        }

        item { Spacer(Modifier.height(24.dp)) }
        item { SectionHeader(stringResource(R.string.settings_section_notifications)) }
        item { Spacer(Modifier.height(8.dp)) }
        item {
            NotificationsCard(
                completionAlerts = true,
                stallWarnings = true,
                onToggleCompletion = {},
                onToggleStall = {},
            )
        }

        item { Spacer(Modifier.height(24.dp)) }
        item { SectionHeader(stringResource(R.string.settings_section_about)) }
        item { Spacer(Modifier.height(8.dp)) }
        item { AboutCard() }
    }
}
