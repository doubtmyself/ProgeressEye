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
import androidx.hilt.lifecycle.viewmodel.compose.hiltViewModel
import com.chg.progeresseye.domain.repository.AdPrefsRepository
import com.chg.progeresseye.domain.repository.LocalSessionRepository
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.chg.progeresseye.data.util.FirebaseConstants
import com.chg.progeresseye.auth.AuthViewModel
import dagger.hilt.android.AndroidEntryPoint
import com.chg.progeresseye.service.FCMService
import com.chg.progeresseye.ui.screen.login.LoginScreen
import com.chg.progeresseye.ui.screen.main.MainScreen
import com.chg.progeresseye.ui.theme.ProgressEyeTheme
import com.chg.progeresseye.ui.screen.settings.SettingsViewModel
import com.chg.progeresseye.ui.screen.settings.SettingsUiState
import com.chg.progeresseye.util.isPro
import androidx.activity.viewModels
import com.google.android.ump.ConsentDebugSettings
import com.google.android.ump.ConsentInformation
import com.google.android.ump.ConsentRequestParameters
import com.google.android.ump.UserMessagingPlatform
import com.google.android.gms.ads.MobileAds
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.DatabaseReference
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import com.chg.progeresseye.domain.repository.AuthRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import javax.inject.Inject
@AndroidEntryPoint
/**
 * 애플리케이션의 유일한 진입점 역할을 하는 단일 액티비티
 *
 * @constructor Create empty [MainActivity]
 */
class MainActivity : ComponentActivity() {
    @Inject lateinit var authRepository: AuthRepository
    @Inject lateinit var adPrefsRepository: AdPrefsRepository
    @Inject lateinit var localSessionRepository: LocalSessionRepository
    private val settingsViewModel: SettingsViewModel by viewModels()
    private var mobileSessionRef: DatabaseReference? = null
    private var mobileSessionListener: ValueEventListener? = null
    private var isHandlingSessionConflict: Boolean = false
    private var forceLogoutRef: DatabaseReference? = null
    private var forceLogoutListener: ValueEventListener? = null
    private var handledForceLogoutCmdId: String? = null
    private var withdrawalStatusListener: ListenerRegistration? = null
    private var isHandlingWithdrawalLogout: Boolean = false
    private var adsInitialized = false
    private var prevIsPurchaseLoading = false
    private var consentObtained by mutableStateOf(false)
    private var isEeaUser by mutableStateOf(false)
    private var showPrivacyButton by mutableStateOf(false)
    private var isPersonalizedAds by mutableStateOf(true)
    private var consentDialog: AlertDialog? = null

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

    /**
     * 액티비티 생성 시 호출되며, UI 초기화, 권한 체크, 버전 확인 및 세션 리스너 설정을 수행합니다.
     *
     * @param savedInstanceState 이전에 저장된 상태가 있는 경우 해당 데이터가 포함된 Bundle
     */
    override fun onCreate(savedInstanceState: Bundle?) {
        val t0 = System.currentTimeMillis()
        Timber.d("[Startup] MainActivity.onCreate start")
        super.onCreate(savedInstanceState)
        Timber.d("[Startup] super.onCreate: +${System.currentTimeMillis() - t0}ms")
        enableEdgeToEdge()

        // 강제 버전 체크 (Firestore progress DB — 인증 불필요)
        checkMinVersion()
        Timber.d("[Startup] checkMinVersion dispatched: +${System.currentTimeMillis() - t0}ms")

        // 구독 상태 및 결제 결과 관찰
        lifecycleScope.launch {
            settingsViewModel.uiState.collect { state ->
                handleSettingsStateChange(state)
            }
        }

        setContent {
            Timber.d("[Startup] setContent lambda entered: +${System.currentTimeMillis() - t0}ms")
            ProgressEyeTheme {
                val authViewModel: AuthViewModel = hiltViewModel()
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

    /**
     * SettingsViewModel의 상태 변화를 처리합니다.
     * 구독 성공 시 광고 동의 단계를 건너뛰고, 결제 실패 시 동의 다이얼로그를 다시 표시합니다.
     */
    private fun handleSettingsStateChange(state: SettingsUiState) {
        // 결제 흐름 종료 감지 (true → false 전환)
        val justFinishedBilling = prevIsPurchaseLoading && !state.isPurchaseLoading
        prevIsPurchaseLoading = state.isPurchaseLoading

        // 1. Pro 구독 성공 또는 전역 광고 제거 모드 시
        if (state.currentPlan.isPro() || state.isAdFreeMode) {
            if (!consentObtained) {
                Timber.d("Skipping ad consent: pro=${state.currentPlan.isPro()}, adFreeMode=${state.isAdFreeMode}")
                consentObtained = true
                consentDialog?.dismiss()
                consentDialog = null
            }
            return
        }

        // 2. 결제 흐름 종료 (성공하지 못한 경우)
        if (!state.isPurchaseLoading && !consentObtained) {
            // 결제 흐름이 끝났거나 결제 오류 메시지가 있는 경우 동의 다이얼로그 재표시
            if (justFinishedBilling || state.billingMessage != null) {
                Timber.d("Billing ended without Pro: justFinished=$justFinishedBilling msg=${state.billingMessage}")
                showConsentRequiredDialog()
            }
            if (state.billingMessage != null) {
                settingsViewModel.clearBillingMessage()
            }
        }
    }

    /**
     * UMP(User Messaging Platform)를 사용하여 광고 동의를 요청하고 광고를 초기화합니다.
     * 디버그 모드에서는 테스트 설정을 적용할 수 있습니다.
     */
    private fun requestConsentAndInitAds() {
        // 이미 Pro이거나 전역 광고 제거 모드인 경우 광고 동의 절차 생략
        val state = settingsViewModel.uiState.value
        if (state.currentPlan.isPro() || state.isAdFreeMode) {
            consentObtained = true
            return
        }

        val consentInformation = UserMessagingPlatform.getConsentInformation(this)

        val params = if (BuildConfig.DEBUG) {
            // ── 디버그 지역 선택 ──────────────────────────────────────────
            // EEA 테스트:  DEBUG_GEOGRAPHY_EEA
            // 미국 테스트: DEBUG_GEOGRAPHY_REGULATED_US_STATE
            // 기타(광고):  DEBUG_GEOGRAPHY_OTHER
            val debugGeography = ConsentDebugSettings.DebugGeography.DEBUG_GEOGRAPHY_EEA
            // ─────────────────────────────────────────────────────────────
            val debugSettings = ConsentDebugSettings.Builder(this)
                .setDebugGeography(debugGeography)
//                .addTestDeviceHashedId("83FD2E2863804C0E51D7CB9BEFB41759")
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

    /**
     * 광고 동의 요청 결과를 처리합니다. 맞춤형 광고 동의 여부에 따라 광고를 초기화하거나 동의 유도 다이얼로그를 표시합니다.
     *
     * @param consentInformation 업데이트된 동의 정보 객체
     */
    private fun handleConsentResult(consentInformation: ConsentInformation) {
        if (consentInformation.canRequestAds() && isPersonalizedAdsConsented()) {
            // 맞춤형 광고 동의 → 정상 초기화
            initMobileAds()
        } else {
            // X 닫기(EEA), 비맞춤형 선택, 미국 판매 거부, 완전 거부 모두 → Pro 구독 유도
            showConsentRequiredDialog()
        }
    }

    /**
     * 광고 동의가 필요함을 알리는 다이얼로그를 표시합니다.
     * 재동의를 시도하거나 광고 없이 서비스를 이용하기 위한 구독 안내를 포함합니다.
     */
    private fun showConsentRequiredDialog() {
        if (consentDialog?.isShowing == true) return

        consentDialog = AlertDialog.Builder(this)
            .setTitle(getString(R.string.consent_required_title))
            .setMessage(getString(R.string.consent_required_message))
            .setCancelable(false)
            .setPositiveButton(getString(R.string.consent_required_reconsent)) { _, _ ->
                consentDialog = null
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
                consentDialog = null
                // Pro 구독 흐름 시작
                settingsViewModel.startProSubscription(this)
            }
            .show()
    }

    /**
     * 설정 화면에서 개인정보 보호 옵션 버튼을 탭했을 때 호출되며, 개인정보 설정 폼(미국 규정 등)을 표시합니다.
     */
    fun onShowPrivacyOptions() {
        UserMessagingPlatform.showPrivacyOptionsForm(this) { formError ->
            if (formError != null) Timber.w("Privacy options form error: %s", formError.message)
            updatePrivacyButtonVisibility()

            val personalized = isPersonalizedAdsConsented()
            isPersonalizedAds = personalized
            lifecycleScope.launch { adPrefsRepository.setIsPersonalizedAds(personalized) }
            // 비맞춤형으로 변경 시 Pro 구독 유도 (EEA 및 US 공통)
            if (!personalized) {
                showConsentRequiredDialog()
            }
        }
    }

    /**
     * 지역 규제(US, EEA)에 따라 설정 화면의 개인정보 보호 버튼 노출 여부를 업데이트합니다.
     */
    private fun updatePrivacyButtonVisibility() {
        val ci = UserMessagingPlatform.getConsentInformation(this)
        // US states: privacyOptionsRequirementStatus == REQUIRED
        // EEA: 로그인 후에도 설정에서 변경 가능하도록 표시
        showPrivacyButton = ci.privacyOptionsRequirementStatus ==
            ConsentInformation.PrivacyOptionsRequirementStatus.REQUIRED || isEeaRegion()
    }

    /**
     * Google Mobile Ads SDK를 초기화하고 관련 설정을 저장합니다.
     */
    private fun initMobileAds() {
        if (adsInitialized) return
        adsInitialized = true
        isEeaUser = isEeaRegion()
        consentObtained = true
        updatePrivacyButtonVisibility()
        val personalized = isPersonalizedAdsConsented()
        isPersonalizedAds = personalized
        lifecycleScope.launch {
            adPrefsRepository.setAdsConsented(true)
            adPrefsRepository.setIsPersonalizedAds(personalized)
            kotlinx.coroutines.withContext(Dispatchers.IO) {
                MobileAds.initialize(this@MainActivity) {}
            }
        }
    }

    /**
     * 현재 사용자의 지역 규제(EEA, US 등)에 따른 맞춤형 광고 동의 여부를 반환합니다.
     * - EEA (GDPR)  : TCF v2 Purpose 4 체크
     * - US (GPP)    : IABGPP_HDR_GppString 섹션 문자열 SaleOptOut 비트(18-19) 체크
     * - US (구 CCPA): IABUSPrivacy_String[2] == 'Y' 이면 판매 거부 → 비맞춤형
     * - 기타         : 항상 맞춤형
     *
     * @return 맞춤형 광고가 허용된 경우 true, 그렇지 않으면 false
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
     * GPP(Global Privacy Platform) US 섹션 문자열(Base64URL)을 디코딩하여 판매/공유 거부 여부를 판단합니다.
     * US National (Section 7): bits 18-19=SaleOptOut, 20-21=SharingOptOut, 22-23=TargetedAdvertisingOptOut
     * "Don't Sell or Share My Data"는 SaleOptOut 또는 SharingOptOut 중 하나라도 거부(1)이면 비동의로 처리.
     *
     * @param base64String GPP 섹션의 Base64URL 인코딩 문자열
     * @return 판매 또는 공유 항목이 거부된 경우 true
     */
    private fun isGppUsSectionOptedOut(base64String: String): Boolean {
        return try {
            val bytes = android.util.Base64.decode(
                base64String,
                android.util.Base64.URL_SAFE or android.util.Base64.NO_PADDING,
            )
            if (bytes.size < 3) return false
            val b = bytes[2].toInt() and 0xFF
            val saleOptOut    = ((b ushr 5) and 0x1 shl 1) or ((b ushr 4) and 0x1)
            val sharingOptOut = ((b ushr 3) and 0x1 shl 1) or ((b ushr 2) and 0x1)
            saleOptOut == 1 || sharingOptOut == 1
        } catch (e: Exception) {
            Timber.w(e, "GPP US section decode failed: %s", base64String)
            false
        }
    }

    /**
     * 사용자가 EEA(유럽 경제 지역) 규정(GDPR) 적용 대상인지 확인합니다.
     *
     * @return GDPR 적용 대상인 경우 true
     */
    private fun isEeaRegion(): Boolean {
        val prefs = getSharedPreferences("${packageName}_preferences", Context.MODE_PRIVATE)
        return prefs.getInt("IABTCF_gdprApplies", 0) == 1
    }

    /**
     * 광고 동의 상태를 변경하고자 할 때 호출되며, 동의 정보를 초기화하고 다시 요청합니다.
     * "변경" 클릭 시 동의 폼 재표시
     */
    private fun onChangeAdConsent() {
        consentObtained = false
        adsInitialized = false
        UserMessagingPlatform.getConsentInformation(this).reset()
        requestConsentAndInitAds()
    }

    /**
     * 액티비티가 소멸될 때 모든 리얼타임 리스너를 해제합니다.
     */
    override fun onDestroy() {
        stopSessionConflictListener()
        stopForceLogoutCommandListener()
        stopWithdrawalStatusListener()
        super.onDestroy()
    }

    /**
     * 실시간 데이터베이스를 통해 다른 기기에서의 중복 로그인을 감시합니다.
     *
     * @param uid 현재 로그인한 사용자의 ID
     * @param authViewModel 인증 관련 처리를 위한 ViewModel
     */
    private fun startSessionConflictListener(uid: String, authViewModel: AuthViewModel) {
        stopSessionConflictListener()
        isHandlingSessionConflict = false

        lifecycleScope.launch {
            val localSessionId = localSessionRepository.getSessionId() ?: return@launch
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
    }

    /**
     * 중복 로그인 감시 리스너를 제거합니다.
     */
    private fun stopSessionConflictListener() {
        mobileSessionListener?.let { listener ->
            mobileSessionRef?.removeEventListener(listener)
        }
        mobileSessionListener = null
        mobileSessionRef = null
        isHandlingSessionConflict = false
    }

    /**
     * 서버로부터의 강제 로그아웃 명령을 감시합니다.
     *
     * @param uid 현재 로그인한 사용자의 ID
     * @param authViewModel 인증 관련 처리를 위한 ViewModel
     */
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

    /**
     * 강제 로그아웃 명령 감시 리스너를 제거합니다.
     */
    private fun stopForceLogoutCommandListener() {
        forceLogoutListener?.let { listener ->
            forceLogoutRef?.removeEventListener(listener)
        }
        forceLogoutListener = null
        forceLogoutRef = null
        handledForceLogoutCmdId = null
    }

    /**
     * Firestore를 통해 사용자의 계정 탈퇴 진행 상태를 감시합니다.
     *
     * @param uid 현재 로그인한 사용자의 ID
     * @param authViewModel 인증 관련 처리를 위한 ViewModel
     */
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

    /**
     * 계정 탈퇴 상태 감시 리스너를 제거합니다.
     */
    private fun stopWithdrawalStatusListener() {
        withdrawalStatusListener?.remove()
        withdrawalStatusListener = null
        isHandlingWithdrawalLogout = false
    }

    /**
     * Android 13(Tiramisu) 이상 기기에서 알림 권한을 요청합니다.
     */
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

    /**
     * Firestore에 설정된 최소 지원 버전과 현재 앱 버전을 비교하여 업데이트 필요 여부를 체크합니다.
     */
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

    /**
     * 현재 버전이 최소 요구 버전보다 낮은지 비교합니다.
     *
     * @param current 현재 앱 버전 코드
     * @param minimum 최소 요구 버전 코드
     * @return 업데이트가 필요한 경우 true
     */
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

    /**
     * Play Store 인앱 업데이트(IMMEDIATE) 흐름을 시작합니다.
     *
     * @param currentVersion 현재 앱 버전
     * @param minVersion 최소 요구 버전
     */
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

    /**
     * 인앱 업데이트를 사용할 수 없는 경우 Play Store 페이지로 이동을 안내하는 다이얼로그를 표시합니다.
     * 인앱 업데이트 불가 시 Play Store 링크로 안내
     *
     * @param currentVersion 현재 앱 버전
     * @param minVersion 최소 요구 버전
     */
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

    /**
     * 액티비티가 재개될 때 진행 중이던 강제 업데이트가 있다면 다시 트리거합니다.
     * IMMEDIATE 업데이트 중 앱으로 돌아왔을 때 완료되지 않았으면 재트리거
     */
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
