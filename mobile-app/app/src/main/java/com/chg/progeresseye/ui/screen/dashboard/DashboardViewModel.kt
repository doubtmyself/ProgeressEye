package com.chg.progeresseye.ui.screen.dashboard

import android.app.Application
import android.app.Activity
import android.content.Context
import timber.log.Timber
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.chg.progeresseye.ui.screen.dashboard.DashboardUiState
import com.chg.progeresseye.BuildConfig
import com.chg.progeresseye.domain.repository.PolicyRepository
import com.chg.progeresseye.domain.repository.UserPlanRepository
import com.chg.progeresseye.domain.usecase.CheckDeviceHeartbeatsUseCase
import com.chg.progeresseye.domain.usecase.GetCurrentUserUidUseCase
import com.chg.progeresseye.domain.usecase.ObserveDevicesUseCase
import com.chg.progeresseye.domain.usecase.SendShutdownCommandUseCase
import com.chg.progeresseye.domain.usecase.SendSleepCommandUseCase
import com.chg.progeresseye.domain.usecase.SendScreenshotCommandUseCase
import com.chg.progeresseye.domain.usecase.UpdateMobileHeartbeatUseCase
import com.chg.progeresseye.util.isPro
import com.chg.progeresseye.util.toNormalizedPlan
import com.google.android.gms.ads.AdRequest
import com.google.android.gms.ads.FullScreenContentCallback
import com.google.android.gms.ads.LoadAdError
import com.google.android.gms.ads.rewarded.RewardedAd
import com.google.android.gms.ads.rewarded.RewardedAdLoadCallback
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * 대시보드 화면의 비즈니스 로직과 UI 상태를 관리하는 ViewModel
 *
 * 연동된 PC 기기들의 실시간 상태를 구독하며 전원 제어 및 화면 캡쳐 요청을 수행
 *
 * @param application 리소스 및 SharedPreference 접근 컨텍스트
 * @param observeDevicesUseCase 기기 목록 관찰 UseCase
 * @param checkDeviceHeartbeatsUseCase 기기 오프라인 판별 UseCase
 * @param updateMobileHeartbeatUseCase 모바일 활성 상태 보고 UseCase
 * @param sendScreenshotCommandUseCase 스크린샷 캡처 요청 UseCase
 * @param sendSleepCommandUseCase 절전 모드 요청 UseCase
 * @param sendShutdownCommandUseCase 시스템 종료 요청 UseCase
 * @param getCurrentUserUidUseCase 현재 사용자 ID 반환 UseCase
 * @param userPlanRepository 사용자 결제 플랜 상태 관찰 저장소
 * @param policyRepository 전역 보안/광고 정책 관찰 저장소
 * @constructor Create empty [DashboardViewModel]
 */
@HiltViewModel
class DashboardViewModel @Inject constructor(
    application: Application,
    private val observeDevicesUseCase: ObserveDevicesUseCase,
    private val checkDeviceHeartbeatsUseCase: CheckDeviceHeartbeatsUseCase,
    private val updateMobileHeartbeatUseCase: UpdateMobileHeartbeatUseCase,
    private val sendScreenshotCommandUseCase: SendScreenshotCommandUseCase,
    private val sendSleepCommandUseCase: SendSleepCommandUseCase,
    private val sendShutdownCommandUseCase: SendShutdownCommandUseCase,
    private val getCurrentUserUidUseCase: GetCurrentUserUidUseCase,
    private val userPlanRepository: UserPlanRepository,
    private val policyRepository: PolicyRepository,
) : AndroidViewModel(application) {

    private val prefs = getApplication<Application>().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    private val _userPlan = MutableStateFlow("free")
    val userPlan: StateFlow<String> = _userPlan.asStateFlow()
    private val _isAdFreeModeEnabled = MutableStateFlow(false)
    val isAdFreeModeEnabled: StateFlow<Boolean> = _isAdFreeModeEnabled.asStateFlow()
    private var isAdFreeMode: Boolean = false

    private val _isRewardedAdReady = MutableStateFlow(false)

    private val _showSubscribeDialog = MutableStateFlow(false)
    val showSubscribeDialog: StateFlow<Boolean> = _showSubscribeDialog.asStateFlow()

    fun dismissSubscribeDialog() { _showSubscribeDialog.value = false }

    private val _adFreePassRemainingMs = MutableStateFlow(0L)
    val adFreePassRemainingMs: StateFlow<Long> = _adFreePassRemainingMs.asStateFlow()
    private var adFreePassJob: Job? = null

    private var devicesJob: Job? = null
    private var mobileHeartbeatJob: Job? = null
    private var planJob: Job? = null
    private var policyJob: Job? = null
    private var screenshotTimeoutJob: Job? = null
    private var refreshStartedAtMs: Long = 0L

    private var rewardedAd: RewardedAd? = null
    private val _isRewardedAdLoading = MutableStateFlow(false)
    val isRewardedAdLoading: StateFlow<Boolean> = _isRewardedAdLoading.asStateFlow()
    private var shouldPreloadRewardedAd = false
    private var pendingAdActivity: Activity? = null
    private var pendingAdAction: (() -> Unit)? = null

    /**
     * 기기 및 작업 목록 데이터 구독을 시작하여 UI 상태를 초기화
     */
    fun startListening() {
        val uid = getCurrentUserUidUseCase()
        Timber.d("[Dashboard] startListening: uid=$uid")
        if (uid == null) {
            _uiState.value = DashboardUiState(isLoading = false, error = "Not signed in")
            return
        }

        shouldPreloadRewardedAd = true
        restoreAdFreePass()

        devicesJob?.cancel()
        devicesJob = viewModelScope.launch {
            Timber.d("[Dashboard] observeDevices 구독 시작")
            observeDevicesUseCase(uid).collect { devices ->
                Timber.d("[Dashboard] observeDevices emit: devices.size=${devices.size}")
                val currentLoading = _uiState.value.screenshotLoadingDeviceId
                val stillLoading = if (currentLoading != null) {
                    val dev = devices.find { it.id == currentLoading }
                    val prevDev = _uiState.value.devices.find { it.id == currentLoading }
                    dev != null && dev.screenshotTs == prevDev?.screenshotTs
                } else false

                val screenshotError = if (!stillLoading && currentLoading != null) {
                    screenshotTimeoutJob?.cancel()
                    null
                } else {
                    _uiState.value.screenshotError
                }

                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    devices = devices,
                    screenshotLoadingDeviceId = if (stillLoading) currentLoading else null,
                    screenshotError = screenshotError
                )
            }
        }

        viewModelScope.launch {
            try {
                checkDeviceHeartbeatsUseCase(uid)
            } catch (e: Exception) {
                Timber.w(e, "Check heartbeats failed")
            }
        }

        planJob = viewModelScope.launch {
            Timber.d("[Dashboard] observeUserPlan 구독 시작")
            userPlanRepository.observeUserPlan(uid).collect {
                Timber.d("[Dashboard] observeUserPlan emit: plan=$it")
                applyUserEntitlement(it)
            }
        }
        policyJob = viewModelScope.launch {
            Timber.d("[Dashboard] observePolicy 구독 시작")
            policyRepository.observePolicy().collect {
                Timber.d("[Dashboard] observePolicy emit: adFreeMode=$it")
                applyGlobalAdFreeMode(it)
            }
        }

        startMobileHeartbeat(uid)
    }

    fun loadRewardedAd(context: Context) {
        if (shouldSkipRewardedAds()) return
        if (_isRewardedAdLoading.value || rewardedAd != null) return

        _isRewardedAdLoading.value = true
        val adUnitId = if (BuildConfig.DEBUG) REWARDED_AD_UNIT_ID_TEST else REWARDED_AD_UNIT_ID
        RewardedAd.load(
            context,
            adUnitId,
            AdRequest.Builder().build(),
            object : RewardedAdLoadCallback() {
                override fun onAdLoaded(ad: RewardedAd) {
                    rewardedAd = ad
                    _isRewardedAdLoading.value = false
                    shouldPreloadRewardedAd = false
                    _isRewardedAdReady.value = true
                    val activity = pendingAdActivity
                    val action = pendingAdAction
                    if (activity != null && action != null) {
                        pendingAdActivity = null
                        pendingAdAction = null
                        showRewardedAdThen(activity, action)
                    }
                }

                override fun onAdFailedToLoad(loadAdError: LoadAdError) {
                    Timber.w("rewarded:onAdFailedToLoad: ${loadAdError.message}")
                    rewardedAd = null
                    _isRewardedAdLoading.value = false
                    _isRewardedAdReady.value = false
                    pendingAdActivity = null
                    pendingAdAction = null
                }
            },
        )
    }

    private fun applyUserEntitlement(planRaw: String) {
        _userPlan.value = planRaw.toNormalizedPlan()
        syncAdGateState()
    }

    private fun applyGlobalAdFreeMode(enabled: Boolean) {
        _isAdFreeModeEnabled.value = enabled
        isAdFreeMode = enabled
        syncAdGateState()
    }

    private fun syncAdGateState() {
        if (shouldSkipRewardedAds()) {
            rewardedAd = null
            _isRewardedAdReady.value = false
            shouldPreloadRewardedAd = false
        } else if (shouldPreloadRewardedAd && rewardedAd == null && !_isRewardedAdLoading.value) {
            loadRewardedAd(getApplication<Application>().applicationContext)
        }
    }

    private fun shouldSkipRewardedAds(): Boolean {
        return _userPlan.value.isPro() || isAdFreeMode || _adFreePassRemainingMs.value > 0L
    }

    private fun grantAdFreePass(rewardAmount: Int) {
        val durationMs = rewardAmount * AD_FREE_PASS_DURATION_MS
        val now = System.currentTimeMillis()
        val existing = prefs.getLong(KEY_AD_FREE_UNTIL, 0L)
        val base = if (existing > now) existing else now
        val newExpiry = base + durationMs
        prefs.edit().putLong(KEY_AD_FREE_UNTIL, newExpiry).apply()
        startAdFreePassCountdown(newExpiry - now)
    }

    private fun restoreAdFreePass() {
        val remaining = prefs.getLong(KEY_AD_FREE_UNTIL, 0L) - System.currentTimeMillis()
        if (remaining > 0L) {
            startAdFreePassCountdown(remaining)
        }
    }

    fun clearAdFreePass() {
        adFreePassJob?.cancel()
        _adFreePassRemainingMs.value = 0L
        prefs.edit().remove(KEY_AD_FREE_UNTIL).apply()
        syncAdGateState()
    }

    private fun startAdFreePassCountdown(remainingMs: Long) {
        adFreePassJob?.cancel()
        _adFreePassRemainingMs.value = remainingMs
        adFreePassJob = viewModelScope.launch {
            var left = remainingMs
            while (left > 0L) {
                delay(1_000L)
                left -= 1_000L
                _adFreePassRemainingMs.value = maxOf(0L, left)
            }
            syncAdGateState()
        }
    }

    fun showRewardedAdThen(activity: Activity, action: () -> Unit) {
        if (shouldSkipRewardedAds()) {
            action()
            return
        }

        val adsConsented = prefs.getBoolean(KEY_ADS_CONSENTED, true)
        val isPersonalized = prefs.getBoolean(KEY_IS_PERSONALIZED_ADS, true)
        if (!adsConsented || !isPersonalized) {
            _showSubscribeDialog.value = true
            return
        }

        val ad = rewardedAd
        if (ad == null) {
            pendingAdActivity = activity
            pendingAdAction = action
            loadRewardedAd(activity.applicationContext)
            return
        }

        rewardedAd = null
        _isRewardedAdReady.value = false

        var rewardEarned = false
        ad.fullScreenContentCallback = object : FullScreenContentCallback() {
            override fun onAdDismissedFullScreenContent() {
                if (rewardEarned) {
                    grantAdFreePass(1)
                    action()
                }
                loadRewardedAd(activity.applicationContext)
            }
            override fun onAdFailedToShowFullScreenContent(adError: com.google.android.gms.ads.AdError) {
                Timber.w("rewarded:onAdFailedToShow: ${adError.message}")
                action()
                loadRewardedAd(activity.applicationContext)
            }
        }

        ad.show(activity) { rewardEarned = true }
    }

    fun showRewardedAdThenScreenshot(activity: Activity, deviceId: String) =
        showRewardedAdThen(activity) { requestScreenshot(deviceId) }

    private fun startMobileHeartbeat(uid: String) {
        mobileHeartbeatJob?.cancel()
        mobileHeartbeatJob = viewModelScope.launch {
            while (true) {
                try {
                    updateMobileHeartbeatUseCase(uid)
                } catch (e: Exception) {
                    Timber.w(e, "[HEARTBEAT] update mobile heartbeat failed")
                }
                delay(MOBILE_HEARTBEAT_INTERVAL_MS)
            }
        }
    }

    fun requestScreenshot(deviceId: String) {
        val uid = getCurrentUserUidUseCase() ?: return
        Timber.d("[SCREENSHOT] requesting screenshot for device=$deviceId uid=$uid")
        _uiState.value = _uiState.value.copy(screenshotLoadingDeviceId = deviceId)

        screenshotTimeoutJob?.cancel()
        screenshotTimeoutJob = viewModelScope.launch {
            delay(SCREENSHOT_TIMEOUT_MS)
            if (_uiState.value.screenshotLoadingDeviceId == deviceId) {
                Timber.w("[SCREENSHOT] timeout after ${SCREENSHOT_TIMEOUT_MS / 1000}s")
                _uiState.value = _uiState.value.copy(
                    screenshotLoadingDeviceId = null,
                    screenshotError = getApplication<Application>().getString(com.chg.progeresseye.R.string.screenshot_timeout)
                )
            }
        }

        viewModelScope.launch {
            try {
                sendScreenshotCommandUseCase(uid, deviceId)
            } catch (e: Exception) {
                Timber.e(e, "[SCREENSHOT] command write FAILED")
                screenshotTimeoutJob?.cancel()
                _uiState.value = _uiState.value.copy(
                    screenshotLoadingDeviceId = null,
                    screenshotError = getApplication<Application>().getString(com.chg.progeresseye.R.string.screenshot_command_failed, e.message ?: "")
                )
            }
        }
    }

    fun clearScreenshotError() {
        _uiState.value = _uiState.value.copy(screenshotError = null)
    }

    fun sendSleepCommand(deviceId: String) {
        val uid = getCurrentUserUidUseCase() ?: return
        viewModelScope.launch {
            try {
                sendSleepCommandUseCase(uid, deviceId)
                Timber.d("[CMD] sleep command sent: $deviceId")
            } catch (e: Exception) {
                Timber.w(e, "[CMD] sleep command failed")
            }
        }
    }

    fun sendShutdownCommand(deviceId: String) {
        val uid = getCurrentUserUidUseCase() ?: return
        viewModelScope.launch {
            try {
                sendShutdownCommandUseCase(uid, deviceId)
                Timber.d("[CMD] shutdown command sent: $deviceId")
            } catch (e: Exception) {
                Timber.w(e, "[CMD] shutdown command failed")
            }
        }
    }

    fun consumeForcedSignOut() {
        _uiState.value = _uiState.value.copy(requiresForcedSignOut = false)
    }

    fun refresh() {
        val uid = getCurrentUserUidUseCase() ?: return
        if (_uiState.value.isRefreshing) return
        refreshStartedAtMs = System.currentTimeMillis()
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        
        viewModelScope.launch {
            try {
                checkDeviceHeartbeatsUseCase(uid)
            } catch (e: Exception) {
                Timber.w(e, "Check heartbeats failed during refresh")
            }
            
            val elapsed = System.currentTimeMillis() - refreshStartedAtMs
            val remaining = (MIN_REFRESH_DISPLAY_MS - elapsed).coerceAtLeast(0L)
            if (remaining > 0L) delay(remaining)
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }

    fun stopListening() {
        devicesJob?.cancel()
        devicesJob = null
        mobileHeartbeatJob?.cancel()
        mobileHeartbeatJob = null
        screenshotTimeoutJob?.cancel()
        screenshotTimeoutJob = null

        rewardedAd = null
        _isRewardedAdReady.value = false
        _isRewardedAdLoading.value = false
        shouldPreloadRewardedAd = false
        _isAdFreeModeEnabled.value = false
        isAdFreeMode = false

        planJob?.cancel()
        planJob = null
        userPlanRepository.reset()

        policyJob?.cancel()
        policyJob = null
        policyRepository.reset()
    }

    override fun onCleared() {
        super.onCleared()
        stopListening()
    }

    companion object {
        private const val MOBILE_HEARTBEAT_INTERVAL_MS = 60_000L
        private const val MIN_REFRESH_DISPLAY_MS = 900L
        private const val SCREENSHOT_TIMEOUT_MS = 30_000L
        private const val REWARDED_AD_UNIT_ID = "ca-app-pub-6572076936506117/7864871780"
        private const val REWARDED_AD_UNIT_ID_TEST = "ca-app-pub-3940256099942544/5224354917"
        private const val AD_FREE_PASS_DURATION_MS = 3_600_000L
        private const val PREFS_NAME = "dashboard_prefs"
        private const val KEY_AD_FREE_UNTIL = "ad_free_until_ms"
        const val KEY_ADS_CONSENTED = "ads_consented"
        const val KEY_IS_PERSONALIZED_ADS = "is_personalized_ads"
    }
}
