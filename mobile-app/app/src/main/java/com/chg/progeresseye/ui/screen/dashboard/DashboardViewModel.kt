package com.chg.progeresseye.ui.screen.dashboard

import android.app.Application
import android.app.Activity
import android.content.Context
import timber.log.Timber
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.chg.progeresseye.ui.screen.dashboard.DashboardUiState
import com.chg.progeresseye.BuildConfig
import com.chg.progeresseye.domain.repository.AdPrefsRepository
import com.chg.progeresseye.domain.repository.PolicyRepository
import com.chg.progeresseye.domain.repository.UserPlanRepository
import com.chg.progeresseye.domain.usecase.CheckDeviceHeartbeatsUseCase
import com.chg.progeresseye.domain.usecase.DeleteDeviceUseCase
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
 * 대시보드 화면의 비즈니스 로직과 UI 상태를 관리하는 ViewModel입니다.
 *
 * 연동된 PC 기기들의 실시간 상태를 구독하며 전원 제어 및 화면 캡쳐 요청을 수행합니다.
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
    private val adPrefsRepository: AdPrefsRepository,
    private val deleteDeviceUseCase: DeleteDeviceUseCase,
) : AndroidViewModel(application) {

    private var cachedAdFreeUntilMs = 0L
    private var cachedAdsConsented = true
    private var cachedIsPersonalizedAds = true

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    private val _userPlan = MutableStateFlow("free")
    val userPlan: StateFlow<String> = _userPlan.asStateFlow()
    private val _isAdFreeModeEnabled = MutableStateFlow(false)
    val isAdFreeModeEnabled: StateFlow<Boolean> = _isAdFreeModeEnabled.asStateFlow()

    private val _showAllPcs = MutableStateFlow(false)
    val showAllPcs: StateFlow<Boolean> = _showAllPcs.asStateFlow()

    private val _defaultDeviceId = MutableStateFlow<String?>(null)
    val defaultDeviceId: StateFlow<String?> = _defaultDeviceId.asStateFlow()

    private val _selectedDeviceIndex = MutableStateFlow(0)
    val selectedDeviceIndex: StateFlow<Int> = _selectedDeviceIndex.asStateFlow()

    private var isAdFreeMode: Boolean = false

    private val _isRewardedAdReady = MutableStateFlow(false)

    private val _showSubscribeDialog = MutableStateFlow(false)
    val showSubscribeDialog: StateFlow<Boolean> = _showSubscribeDialog.asStateFlow()

    /**
     * 구독 권유 다이얼로그를 닫습니다.
     */
    fun dismissSubscribeDialog() { _showSubscribeDialog.value = false }

    /**
     * 선택된 기기를 기본 기기로 저장합니다.
     */
    fun selectDevice(index: Int, deviceId: String) {
        _selectedDeviceIndex.value = index
        _defaultDeviceId.value = deviceId
        viewModelScope.launch { adPrefsRepository.setDefaultDeviceId(deviceId) }
    }

    private val _adFreePassRemainingMs = MutableStateFlow(0L)
    val adFreePassRemainingMs: StateFlow<Long> = _adFreePassRemainingMs.asStateFlow()
    private var adFreePassJob: Job? = null

    private var devicesJob: Job? = null
    private var mobileHeartbeatJob: Job? = null
    private var planJob: Job? = null
    private var policyJob: Job? = null
    private var showAllPcsJob: Job? = null
    private var screenshotTimeoutJob: Job? = null
    private var refreshStartedAtMs: Long = 0L

    private var rewardedAd: RewardedAd? = null
    private val _isRewardedAdLoading = MutableStateFlow(false)
    val isRewardedAdLoading: StateFlow<Boolean> = _isRewardedAdLoading.asStateFlow()
    private var shouldPreloadRewardedAd = false
    private var pendingAdActivity: Activity? = null
    private var pendingAdAction: (() -> Unit)? = null

    /**
     * 기기 목록 및 사용자 플랜 정보를 구독하기 시작합니다.
     * 기기 및 작업 목록 데이터 구독을 시작하여 UI 상태를 초기화합니다.
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
        viewModelScope.launch {
            cachedAdsConsented = adPrefsRepository.getAdsConsented()
            cachedIsPersonalizedAds = adPrefsRepository.getIsPersonalizedAds()
            _defaultDeviceId.value = adPrefsRepository.getDefaultDeviceId()
        }
        showAllPcsJob?.cancel()
        showAllPcsJob = viewModelScope.launch {
            adPrefsRepository.observeShowAllPcs().collect { _showAllPcs.value = it }
        }

        devicesJob?.cancel()
        devicesJob = viewModelScope.launch {
            Timber.d("[Dashboard] observeDevices 구독 시작")
            observeDevicesUseCase(uid).collect { devices ->
                Timber.d("[Dashboard] observeDevices emit: devices.size=${devices.size}")
                val savedId = _defaultDeviceId.value
                if (savedId != null) {
                    val idx = devices.indexOfFirst { it.id == savedId }
                    if (idx >= 0) _selectedDeviceIndex.value = idx
                }
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

    /**
     * 보상형 광고를 로드합니다.
     *
     * @param context 광고 로드에 필요한 컨텍스트
     */
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

    /**
     * 사용자의 결제 플랜에 따른 권한을 적용합니다.
     *
     * @param planRaw 서버에서 받아온 가공되지 않은 플랜 문자열
     */
    private fun applyUserEntitlement(planRaw: String) {
        _userPlan.value = planRaw.toNormalizedPlan()
        syncAdGateState()
    }

    /**
     * 전역 광고 제거 모드 상태를 적용합니다.
     *
     * @param enabled 활성화 여부
     */
    private fun applyGlobalAdFreeMode(enabled: Boolean) {
        _isAdFreeModeEnabled.value = enabled
        isAdFreeMode = enabled
        syncAdGateState()
    }

    /**
     * 광고 로드 및 동의 상태를 동기화합니다. 필요 시 광고를 사전 로드합니다.
     */
    private fun syncAdGateState() {
        if (shouldSkipRewardedAds()) {
            rewardedAd = null
            _isRewardedAdReady.value = false
            shouldPreloadRewardedAd = false
        } else if (shouldPreloadRewardedAd && rewardedAd == null && !_isRewardedAdLoading.value) {
            loadRewardedAd(getApplication<Application>().applicationContext)
        }
    }

    /**
     * 현재 광고 표시를 건너뛸 수 있는 상태(Pro 플랜, 전역 광고 제거 등)인지 확인합니다.
     *
     * @return 광고를 건너뛰어야 하면 true
     */
    private fun shouldSkipRewardedAds(): Boolean {
        return _userPlan.value.isPro() || isAdFreeMode || _adFreePassRemainingMs.value > 0L
    }

    /**
     * 보상형 광고 시청 완료 후 광고 제거 패스를 지급합니다.
     *
     * @param rewardAmount 지급할 패스 단위 (보통 1)
     */
    private fun grantAdFreePass(rewardAmount: Int) {
        val durationMs = rewardAmount * AD_FREE_PASS_DURATION_MS
        val now = System.currentTimeMillis()
        val base = if (cachedAdFreeUntilMs > now) cachedAdFreeUntilMs else now
        val newExpiry = base + durationMs
        cachedAdFreeUntilMs = newExpiry
        viewModelScope.launch { adPrefsRepository.setAdFreeUntilMs(newExpiry) }
        startAdFreePassCountdown(newExpiry - now)
    }

    /**
     * 저장된 광고 제거 패스 정보를 복구하여 카운트다운을 시작합니다.
     */
    private fun restoreAdFreePass() {
        viewModelScope.launch {
            val storedMs = adPrefsRepository.getAdFreeUntilMs()
            cachedAdFreeUntilMs = storedMs
            val remaining = storedMs - System.currentTimeMillis()
            if (remaining > 0L) {
                startAdFreePassCountdown(remaining)
            }
        }
    }

    /**
     * 현재 활성화된 광고 제거 패스를 즉시 만료시킵니다.
     */
    fun clearAdFreePass() {
        adFreePassJob?.cancel()
        _adFreePassRemainingMs.value = 0L
        cachedAdFreeUntilMs = 0L
        viewModelScope.launch { adPrefsRepository.clearAdFreeUntil() }
        syncAdGateState()
    }

    /**
     * 광고 제거 패스의 남은 시간을 UI에 반영하기 위한 타이머를 시작합니다.
     *
     * @param remainingMs 남은 시간(밀리초)
     */
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

    /**
     * 보상형 광고를 표시하고, 시청 완료 시 지정된 동작을 수행합니다.
     * 광고 면제 상태이거나 동의가 부족한 경우 적절한 처리를 수행합니다.
     *
     * @param activity 광고를 표시할 Activity
     * @param action 광고 시청 후(또는 면제 시) 실행할 동작
     */
    fun showRewardedAdThen(activity: Activity, action: () -> Unit) {
        if (shouldSkipRewardedAds()) {
            action()
            return
        }

        val adsConsented = cachedAdsConsented
        val isPersonalized = cachedIsPersonalizedAds
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

    /**
     * 보상형 광고를 표시한 후 기기의 스크린샷을 요청합니다.
     *
     * @param activity 광고를 표시할 Activity
     * @param deviceId 스크린샷을 요청할 대상 기기 ID
     */
    fun showRewardedAdThenScreenshot(activity: Activity, deviceId: String) =
        showRewardedAdThen(activity) { requestScreenshot(deviceId) }

    /**
     * 모바일 기기의 활성 상태(Heartbeat)를 주기적으로 서버에 보고합니다.
     *
     * @param uid 사용자 ID
     */
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

    /**
     * 특정 기기에 스크린샷 캡처 명령을 전송합니다. 타임아웃 처리가 포함되어 있습니다.
     *
     * @param deviceId 대상 기기 ID
     */
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

    /**
     * 표시 중인 스크린샷 에러 메시지를 지웁니다.
     */
    fun clearScreenshotError() {
        _uiState.value = _uiState.value.copy(screenshotError = null)
    }

    /**
     * 특정 기기에 절전 모드 명령을 전송합니다.
     *
     * @param deviceId 대상 기기 ID
     */
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

    /**
     * 특정 기기에 시스템 종료 명령을 전송합니다.
     *
     * @param deviceId 대상 기기 ID
     */
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

    /**
     * 연동된 기기를 서버에서 삭제합니다.
     *
     * @param deviceId 삭제할 기기 ID
     */
    fun deleteDevice(deviceId: String) {
        val uid = getCurrentUserUidUseCase() ?: return
        viewModelScope.launch {
            try {
                deleteDeviceUseCase(uid, deviceId)
                Timber.d("[CMD] device deleted: $deviceId")
            } catch (e: Exception) {
                Timber.w(e, "[CMD] delete device failed")
            }
        }
    }

    /**
     * 강제 로그아웃 플래그를 소비(초기화)합니다.
     */
    fun consumeForcedSignOut() {
        _uiState.value = _uiState.value.copy(requiresForcedSignOut = false)
    }

    /**
     * 대시보드 데이터를 수동으로 새로고침합니다.
     */
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

    /**
     * 모든 데이터 구독 및 백그라운드 작업을 중단합니다.
     */
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

        showAllPcsJob?.cancel()
        showAllPcsJob = null
    }

    /**
     * ViewModel이 소멸될 때 리소스를 해제합니다.
     */
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
    }
}
