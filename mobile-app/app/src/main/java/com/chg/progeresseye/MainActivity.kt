package com.chg.progeresseye

import android.content.Context
import android.os.Bundle
import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import timber.log.Timber
import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import androidx.activity.result.IntentSenderRequest
import com.google.android.play.core.appupdate.AppUpdateManagerFactory
import com.google.android.play.core.appupdate.AppUpdateOptions
import com.google.android.play.core.install.model.AppUpdateType
import com.google.android.play.core.install.model.UpdateAvailability
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.ListenerRegistration
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.chg.progeresseye.ui.screen.dashboard.DashboardViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.lifecycle.lifecycleScope
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.chg.progeresseye.data.util.FirebaseConstants
import com.chg.progeresseye.auth.AuthViewModel
import dagger.hilt.android.AndroidEntryPoint
import com.chg.progeresseye.auth.MobileSessionManager
import com.chg.progeresseye.service.FCMService
import com.chg.progeresseye.ui.screen.login.LoginScreen
import com.chg.progeresseye.ui.screen.main.MainScreen
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.google.android.gms.ads.MobileAds
import com.google.android.ump.ConsentDebugSettings
import com.google.android.ump.ConsentInformation
import com.google.android.ump.ConsentRequestParameters
import com.google.android.ump.UserMessagingPlatform
import com.google.firebase.database.DatabaseReference
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.DataSnapshot
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import javax.inject.Inject
import com.chg.progeresseye.domain.repository.AuthRepository

@AndroidEntryPoint
/**
 * 애플리케이션의 유일한 진입점 역할을 하는 단일 액티비티
 *
 * @constructor Create empty [MainActivity]
 */
class MainActivity : ComponentActivity() {
    @Inject lateinit var authRepository: AuthRepository
    private var mobileSessionRef: DatabaseReference? = null
    private var mobileSessionListener: ValueEventListener? = null
    private var isHandlingSessionConflict: Boolean = false
    private var forceLogoutRef: DatabaseReference? = null
    private var forceLogoutListener: ValueEventListener? = null
    private var handledForceLogoutCmdId: String? = null
    private var withdrawalStatusListener: ListenerRegistration? = null
    private var isHandlingWithdrawalLogout: Boolean = false
    private var adsInitialized = false
    private var consentObtained by mutableStateOf(false)
    private var isEeaUser by mutableStateOf(false)
    private var showPrivacyButton by mutableStateOf(false)
    private var isPersonalizedAds by mutableStateOf(true)

    private val notificationPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* granted or denied — no action needed */ }

    /** 인앱 업데이트가 필요한 상태인지 (onResume 재트리거용) */
    private var updateRequired = false

    private val updateLauncher = registerForActivityResult(
        ActivityResultContracts.StartIntentSenderForResult()
    ) { result ->
        if (result.resultCode != RESULT_OK) {
            // 사용자가 업데이트를 취소/실패 → 앱 종료 (강제 업데이트이므로)
            Timber.w("In-app update cancelled or failed (code=%d)", result.resultCode)
            finish()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        val t0 = System.currentTimeMillis()
        Timber.d("[Startup] MainActivity.onCreate start")
        super.onCreate(savedInstanceState)
        Timber.d("[Startup] super.onCreate: +${System.currentTimeMillis() - t0}ms")
        enableEdgeToEdge()

        // 강제 버전 체크 (Firestore progress DB — 인증 불필요)
        checkMinVersion()
        Timber.d("[Startup] checkMinVersion dispatched: +${System.currentTimeMillis() - t0}ms")

        setContent {
            Timber.d("[Startup] setContent lambda entered: +${System.currentTimeMillis() - t0}ms")
            ProgressEyeTheme {
                val authViewModel: AuthViewModel = viewModel()
                val authState by authViewModel.uiState.collectAsStateWithLifecycle()
                val navController = rememberNavController()

                // Target destination driven by AuthUiState.
                // This prevents auto-navigation to main while takeover confirmation is pending.
                val authTarget = if (
                    authState.user != null &&
                        !authState.requiresSessionTakeover &&
                        !authState.requiresWithdrawalCancel
                ) {
                    "main"
                } else {
                    "login"
                }

                LaunchedEffect(
                    authState.user,
                    authState.requiresSessionTakeover,
                    authState.requiresWithdrawalCancel,
                ) {
                    val currentRoute = navController.currentDestination?.route
                    if (
                        authState.user != null &&
                            !authState.requiresSessionTakeover &&
                            !authState.requiresWithdrawalCancel &&
                            currentRoute != "main"
                    ) {
                        navController.navigate("main") {
                            popUpTo("login") { inclusive = true }
                        }
                    } else if (authState.user == null && currentRoute == "main") {
                        navController.navigate("login") {
                            popUpTo("main") { inclusive = true }
                        }
                    }
                }

                LaunchedEffect(authState.user?.uid) {
                    val uid = authState.user?.uid
                    if (uid != null) {
                        startSessionConflictListener(uid, authViewModel)
                        startForceLogoutCommandListener(uid, authViewModel)
                        startWithdrawalStatusListener(uid, authViewModel)
                    } else {
                        stopSessionConflictListener()
                        stopForceLogoutCommandListener()
                        stopWithdrawalStatusListener()
                    }
                }

                NavHost(
                    navController = navController,
                    startDestination = authTarget,
                ) {
                    composable("login") {
                        val webClientId = getString(R.string.default_web_client_id)

                        LoginScreen(
                            onSignInClick = {
                                authViewModel.signInWithGoogle(
                                    context = this@MainActivity,
                                    webClientId = webClientId,
                                )
                            },
                            onConfirmSessionTakeover = {
                                authViewModel.confirmSessionTakeover(this@MainActivity)
                            },
                            onCancelSessionTakeover = {
                                authViewModel.cancelSessionTakeover(this@MainActivity)
                            },
                            onConfirmWithdrawalCancel = {
                                authViewModel.confirmWithdrawalCancellation(this@MainActivity)
                            },
                            onKeepWithdrawal = {
                                authViewModel.keepWithdrawalAndCancelLogin(this@MainActivity)
                            },
                            isLoading = authState.isLoading,
                            error = authState.error,
                            requiresSessionTakeover = authState.requiresSessionTakeover,
                            existingDeviceName = authState.existingDeviceName,
                            requiresWithdrawalCancel = authState.requiresWithdrawalCancel,
                            withdrawalGraceEndDate = authState.withdrawalGraceEndDate,
                            consentObtained = consentObtained,
                            isEeaUser = isEeaUser,
                            onChangeConsent = { onChangeAdConsent() },
                        )
                    }
                    composable("main") {
                        LaunchedEffect(Unit) {
                            requestNotificationPermission()
                            FCMService.registerToken(authRepository)
                        }
                        MainScreen(
                            onSignOut = {
                                authViewModel.signOut(this@MainActivity)
                            },
                            onDeleteAccount = {
                                authViewModel.deleteAccount(this@MainActivity)
                            },
                            showPrivacyButton = showPrivacyButton,
                            onShowPrivacyOptions = { onShowPrivacyOptions() },
                        )
                    }
                }
            }
        }

        Timber.d("[Startup] setContent done: +${System.currentTimeMillis() - t0}ms")
        requestConsentAndInitAds()
        Timber.d("[Startup] requestConsentAndInitAds dispatched: +${System.currentTimeMillis() - t0}ms")
    }

    private fun requestConsentAndInitAds() {
        val consentInformation = UserMessagingPlatform.getConsentInformation(this)

        val params = if (BuildConfig.DEBUG) {
            // ── 디버그 지역 선택 ──────────────────────────────────────────
            // EEA 테스트:  DEBUG_GEOGRAPHY_EEA
            // 미국 테스트: DEBUG_GEOGRAPHY_REGULATED_US_STATE
            // 기타(광고):  DEBUG_GEOGRAPHY_OTHER
            val debugGeography = ConsentDebugSettings.DebugGeography.DEBUG_GEOGRAPHY_OTHER
            // ─────────────────────────────────────────────────────────────
            val debugSettings = ConsentDebugSettings.Builder(this)
                .setDebugGeography(debugGeography)
                .addTestDeviceHashedId("83FD2E2863804C0E51D7CB9BEFB41759")
                .build()
            // consentInformation.reset() // 동의 폼 강제 재표시 (테스트 시에만 주석 해제)
            ConsentRequestParameters.Builder()
                .setConsentDebugSettings(debugSettings)
                .build()
        } else {
            ConsentRequestParameters.Builder().build()
        }

        // For returning users who already have consent, init immediately.
        if (consentInformation.canRequestAds() && isPersonalizedAdsConsented()) {
            initMobileAds()
        }

        consentInformation.requestConsentInfoUpdate(
            this,
            params,
            {
                UserMessagingPlatform.loadAndShowConsentFormIfRequired(this) { formError ->
                    if (formError != null) {
                        Timber.w("UMP form error: %s", formError.message)
                    }
                    handleConsentResult(consentInformation)
                }
            },
            { requestError ->
                // Network error — init ads anyway (graceful degradation).
                Timber.w("UMP consent request error: %s", requestError.message)
                initMobileAds()
            },
        )
    }

    private fun handleConsentResult(consentInformation: ConsentInformation) {
        if (consentInformation.canRequestAds() && isPersonalizedAdsConsented()) {
            // 맞춤형 광고 동의 → 정상 초기화
            initMobileAds()
        } else {
            // X 닫기(EEA), 비맞춤형 선택, 미국 판매 거부, 완전 거부 모두 → Pro 구독 유도
            showConsentRequiredDialog()
        }
    }

    private fun showConsentRequiredDialog() {
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.consent_required_title))
            .setMessage(getString(R.string.consent_required_message))
            .setCancelable(false)
            .setPositiveButton(getString(R.string.consent_required_reconsent)) { _, _ ->
                if (isEeaRegion()) {
                    // EEA: GDPR 폼 재표시 (OBTAINED 상태에서 건너뛰지 않도록 리셋)
                    UserMessagingPlatform.getConsentInformation(this).reset()
                    requestConsentAndInitAds()
                } else {
                    // US: 개인정보 설정 폼 재표시
                    onShowPrivacyOptions()
                }
            }
            .setNegativeButton(getString(R.string.consent_required_subscribe)) { _, _ ->
                // 광고 동의 없이 Pro 구독으로 진행 — 광고 미초기화, 로그인 허용
                getSharedPreferences("dashboard_prefs", Context.MODE_PRIVATE)
                    .edit().putBoolean(DashboardViewModel.KEY_ADS_CONSENTED, false).apply()
                isEeaUser = isEeaRegion()
                consentObtained = true
            }
            .show()
    }

    /** 설정 화면 개인정보 버튼 탭 시 미국 규정 폼 표시 */
    fun onShowPrivacyOptions() {
        UserMessagingPlatform.showPrivacyOptionsForm(this) { formError ->
            if (formError != null) Timber.w("Privacy options form error: %s", formError.message)
            updatePrivacyButtonVisibility()

            val personalized = isPersonalizedAdsConsented()
            isPersonalizedAds = personalized
            getSharedPreferences("dashboard_prefs", Context.MODE_PRIVATE)
                .edit().putBoolean(DashboardViewModel.KEY_IS_PERSONALIZED_ADS, personalized).apply()
            // EEA에서 비맞춤형으로 변경 시 Pro 구독 유도
            // US는 Manage options 개별 조정 시 오발동 문제로 제외
            if (!personalized && isEeaRegion()) {
                showConsentRequiredDialog()
            }
        }
    }

    private fun updatePrivacyButtonVisibility() {
        val ci = UserMessagingPlatform.getConsentInformation(this)
        // US states: privacyOptionsRequirementStatus == REQUIRED
        // EEA: 로그인 후에도 설정에서 변경 가능하도록 표시
        showPrivacyButton = ci.privacyOptionsRequirementStatus ==
            ConsentInformation.PrivacyOptionsRequirementStatus.REQUIRED || isEeaRegion()
    }

    private fun initMobileAds() {
        if (adsInitialized) return
        adsInitialized = true
        isEeaUser = isEeaRegion()
        consentObtained = true
        updatePrivacyButtonVisibility()
        val personalized = isPersonalizedAdsConsented()
        isPersonalizedAds = personalized
        getSharedPreferences("dashboard_prefs", Context.MODE_PRIVATE)
            .edit()
            .putBoolean(DashboardViewModel.KEY_ADS_CONSENTED, true)
            .putBoolean(DashboardViewModel.KEY_IS_PERSONALIZED_ADS, personalized)
            .apply()
        lifecycleScope.launch(Dispatchers.IO) {
            MobileAds.initialize(this@MainActivity) {}
        }
    }

    /** 맞춤형 광고 동의 여부
     *  - EEA (GDPR)  : TCF v2 Purpose 4 체크
     *  - US (GPP)    : IABGPP_HDR_GppString 섹션 문자열 SaleOptOut 비트(18-19) 체크
     *  - US (구 CCPA): IABUSPrivacy_String[2] == 'Y' 이면 판매 거부 → 비맞춤형
     *  - 기타         : 항상 맞춤형
     */
    private fun isPersonalizedAdsConsented(): Boolean {
        val prefs = getSharedPreferences("${packageName}_preferences", Context.MODE_PRIVATE)
        // EEA
        if (prefs.getInt("IABTCF_gdprApplies", 0) == 1) {
            val purposeConsents = prefs.getString("IABTCF_PurposeConsents", "") ?: ""
            return purposeConsents.length > 3 && purposeConsents[3] == '1'
        }
        // US states — GPP 문자열 (UMP 3.x)
        val gppString = prefs.getString("IABGPP_HDR_GppString", "") ?: ""
        if (gppString.contains("~")) {
            val sectionStr = gppString.substringAfter("~").substringBefore("~")
            if (sectionStr.isNotEmpty() && isGppUsSectionOptedOut(sectionStr)) return false
        }
        // US states — 구 CCPA 문자열 (폴백)
        val usPrivacy = prefs.getString("IABUSPrivacy_String", "") ?: ""
        if (usPrivacy.length >= 3 && usPrivacy[2] == 'Y') return false
        return true
    }

    /**
     * GPP US 섹션 문자열(Base64URL)에서 완전 거부 여부 반환.
     * US National (Section 7): bits 18-19=SaleOptOut, 20-21=SharingOptOut, 22-23=TargetedAdvertisingOptOut
     * 세 필드 모두 1(거부)일 때만 완전 거부로 판단.
     * Manage options에서 일부만 끈 경우(부분 거부)는 허용으로 처리.
     */
    private fun isGppUsSectionOptedOut(base64String: String): Boolean {
        return try {
            val bytes = android.util.Base64.decode(
                base64String,
                android.util.Base64.URL_SAFE or android.util.Base64.NO_PADDING,
            )
            if (bytes.size < 3) return false
            val b = bytes[2].toInt() and 0xFF
            val saleOptOut     = ((b ushr 5) and 0x1 shl 1) or ((b ushr 4) and 0x1)
            val sharingOptOut  = ((b ushr 3) and 0x1 shl 1) or ((b ushr 2) and 0x1)
            val targetedOptOut = ((b ushr 1) and 0x1 shl 1) or (b and 0x1)
            saleOptOut == 1 && sharingOptOut == 1 && targetedOptOut == 1
        } catch (e: Exception) {
            Timber.w(e, "GPP US section decode failed: %s", base64String)
            false
        }
    }

    private fun isEeaRegion(): Boolean {
        val prefs = getSharedPreferences("${packageName}_preferences", Context.MODE_PRIVATE)
        return prefs.getInt("IABTCF_gdprApplies", 0) == 1
    }

    /** "변경" 클릭 시 동의 폼 재표시 */
    private fun onChangeAdConsent() {
        consentObtained = false
        adsInitialized = false
        UserMessagingPlatform.getConsentInformation(this).reset()
        requestConsentAndInitAds()
    }

    override fun onDestroy() {
        stopSessionConflictListener()
        stopForceLogoutCommandListener()
        stopWithdrawalStatusListener()
        super.onDestroy()
    }

    private fun startSessionConflictListener(uid: String, authViewModel: AuthViewModel) {
        stopSessionConflictListener()
        isHandlingSessionConflict = false

        val localSessionId = MobileSessionManager.getSessionId(this) ?: return
        val ref = FirebaseDatabase.getInstance()
            .getReference("users")
            .child(uid)
            .child("mobileSession")
            .child("sessionId")

        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                val remoteSessionId = snapshot.getValue(String::class.java) ?: return
                if (!isHandlingSessionConflict && remoteSessionId != localSessionId) {
                    isHandlingSessionConflict = true
                    authViewModel.forceSignOutBySessionConflict(this@MainActivity)
                }
            }

            override fun onCancelled(error: DatabaseError) {
                Timber.w(error.toException(), "mobileSession listener cancelled")
            }
        }

        ref.addValueEventListener(listener)
        mobileSessionRef = ref
        mobileSessionListener = listener
    }

    private fun stopSessionConflictListener() {
        mobileSessionListener?.let { listener ->
            mobileSessionRef?.removeEventListener(listener)
        }
        mobileSessionListener = null
        mobileSessionRef = null
        isHandlingSessionConflict = false
    }

    private fun startForceLogoutCommandListener(uid: String, authViewModel: AuthViewModel) {
        stopForceLogoutCommandListener()
        handledForceLogoutCmdId = null

        val ref = FirebaseDatabase.getInstance()
            .getReference("users")
            .child(uid)
            .child("commands")
            .child("forceLogout")

        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                if (!snapshot.exists()) return

                val cmdId = snapshot.child("cmdId").getValue(String::class.java).orEmpty()
                if (cmdId.isNotBlank() && cmdId == handledForceLogoutCmdId) return
                handledForceLogoutCmdId = cmdId

                if (!isHandlingWithdrawalLogout) {
                    isHandlingWithdrawalLogout = true
                    authViewModel.forceSignOutByWithdrawal(this@MainActivity)
                }

                ref.removeValue()
            }

            override fun onCancelled(error: DatabaseError) {
                Timber.w(error.toException(), "forceLogout listener cancelled")
            }
        }

        ref.addValueEventListener(listener)
        forceLogoutRef = ref
        forceLogoutListener = listener
    }

    private fun stopForceLogoutCommandListener() {
        forceLogoutListener?.let { listener ->
            forceLogoutRef?.removeEventListener(listener)
        }
        forceLogoutListener = null
        forceLogoutRef = null
        handledForceLogoutCmdId = null
    }

    private fun startWithdrawalStatusListener(uid: String, authViewModel: AuthViewModel) {
        stopWithdrawalStatusListener()
        isHandlingWithdrawalLogout = false

        val listener = FirebaseFirestore.getInstance(FirebaseConstants.FIRESTORE_DB)
            .collection("users")
            .document(uid)
            .addSnapshotListener { snapshot, error ->
                if (error != null) {
                    Timber.w(error, "withdrawal status listener cancelled")
                    return@addSnapshotListener
                }

                val status = snapshot?.getString("withdrawalStatus") ?: return@addSnapshotListener
                if (!isHandlingWithdrawalLogout && status == "pending") {
                    isHandlingWithdrawalLogout = true
                    authViewModel.forceSignOutByWithdrawal(this@MainActivity)
                }
            }
        withdrawalStatusListener = listener
    }

    private fun stopWithdrawalStatusListener() {
        withdrawalStatusListener?.remove()
        withdrawalStatusListener = null
        isHandlingWithdrawalLogout = false
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(
                    this, Manifest.permission.POST_NOTIFICATIONS
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    private fun checkMinVersion() {
        FirebaseFirestore.getInstance(FirebaseConstants.FIRESTORE_DB)
            .collection("appConfig").document("android").get()
            .addOnSuccessListener { document ->
                val minVersion = document.getString("minVersion") ?: return@addOnSuccessListener
                val currentVersion = packageManager.getPackageInfo(packageName, 0).versionName
                    ?: return@addOnSuccessListener
                if (isOutdated(currentVersion, minVersion)) {
                    updateRequired = true
                    startImmediateUpdate(currentVersion, minVersion)
                }
            }
            .addOnFailureListener { error ->
                Timber.d(error, "Version check failed")
            }
    }

    private fun isOutdated(current: String, minimum: String): Boolean {
        fun parse(v: String): List<Int> = v.split(".").mapNotNull { it.toIntOrNull() }
        val c = parse(current)
        val m = parse(minimum)
        for (i in 0 until maxOf(c.size, m.size)) {
            val cv = c.getOrElse(i) { 0 }
            val mv = m.getOrElse(i) { 0 }
            if (cv < mv) return true
            if (cv > mv) return false
        }
        return false
    }

    private fun startImmediateUpdate(currentVersion: String, minVersion: String) {
        val appUpdateManager = AppUpdateManagerFactory.create(this)
        appUpdateManager.appUpdateInfo.addOnSuccessListener { info ->
            if (info.updateAvailability() == UpdateAvailability.UPDATE_AVAILABLE
                && info.isUpdateTypeAllowed(AppUpdateType.IMMEDIATE)
            ) {
                appUpdateManager.startUpdateFlowForResult(
                    info,
                    updateLauncher,
                    AppUpdateOptions.newBuilder(AppUpdateType.IMMEDIATE).build(),
                )
            } else {
                // Play Store에 업데이트가 아직 없거나 사이드로드 → 폴백
                showFallbackUpdateDialog(currentVersion, minVersion)
            }
        }.addOnFailureListener {
            Timber.w(it, "AppUpdateManager check failed")
            showFallbackUpdateDialog(currentVersion, minVersion)
        }
    }

    /** 인앱 업데이트 불가 시 Play Store 링크로 안내 */
    private fun showFallbackUpdateDialog(currentVersion: String, minVersion: String) {
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.update_required_title))
            .setMessage(
                getString(R.string.update_required_message) + "\n\n" +
                getString(R.string.update_required_current, currentVersion) + "\n" +
                getString(R.string.update_required_minimum, minVersion)
            )
            .setCancelable(false)
            .setPositiveButton(getString(R.string.update_required_button)) { _, _ ->
                startActivity(Intent(
                    Intent.ACTION_VIEW,
                    Uri.parse("https://play.google.com/store/apps/details?id=$packageName"),
                ))
                finish()
            }
            .show()
    }

    override fun onResume() {
        super.onResume()
        // IMMEDIATE 업데이트 중 앱으로 돌아왔을 때 완료되지 않았으면 재트리거
        if (!updateRequired) return
        val appUpdateManager = AppUpdateManagerFactory.create(this)
        appUpdateManager.appUpdateInfo.addOnSuccessListener { info ->
            if (info.updateAvailability() == UpdateAvailability.DEVELOPER_TRIGGERED_UPDATE_IN_PROGRESS) {
                appUpdateManager.startUpdateFlowForResult(
                    info,
                    updateLauncher,
                    AppUpdateOptions.newBuilder(AppUpdateType.IMMEDIATE).build(),
                )
            }
        }
    }
}
