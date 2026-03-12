package com.chg.progeresseye.ui.screen.dashboard

import android.app.Application
import android.app.Activity
import android.content.Context
import timber.log.Timber
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.chg.progeresseye.data.model.DashboardUiState
import com.chg.progeresseye.data.model.DeviceData
import com.chg.progeresseye.data.model.TaskData
import com.google.android.gms.ads.AdRequest
import com.google.android.gms.ads.FullScreenContentCallback
import com.google.android.gms.ads.LoadAdError
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.database.ChildEventListener
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.DatabaseReference
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import com.chg.progeresseye.data.repository.PolicyRepository
import com.chg.progeresseye.data.repository.UserPlanRepository
import com.google.android.gms.ads.rewarded.RewardedAd
import com.google.android.gms.ads.rewarded.RewardedAdLoadCallback
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.UUID

// ═════════════════════════════════════════════════════════
// DashboardViewModel — RTDB listener for devices + tasks
//
// 데이터 경로 분리:
//   users/{uid}/devices/{id}/...      → ChildEventListener (태스크/스크린샷 변경)
//   users/{uid}/deviceStatus/{id}     → ValueEventListener (접속 상태, 실시간)
//   users/{uid}/heartbeat/{id}        → pull-to-refresh 시 읽기 (크래시 감지, 2분 threshold)
//   users/{uid}/mobileHeartbeat       → 30초마다 모바일 하트비트 갱신
// ═════════════════════════════════════════════════════════

class DashboardViewModel(application: Application) : AndroidViewModel(application) {

    private val auth = FirebaseAuth.getInstance()
    private val db = FirebaseDatabase.getInstance()

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    private val _userPlan = MutableStateFlow("free")
    val userPlan: StateFlow<String> = _userPlan.asStateFlow()
    private val _isAdFreeModeEnabled = MutableStateFlow(false)
    val isAdFreeModeEnabled: StateFlow<Boolean> = _isAdFreeModeEnabled.asStateFlow()
    private var isAdFreeMode: Boolean = false

    private val _isRewardedAdReady = MutableStateFlow(false)
    val isRewardedAdReady: StateFlow<Boolean> = _isRewardedAdReady.asStateFlow()

    // Listener A: devices (ChildEventListener — 태스크/스크린샷 변경)
    private var devicesRef: DatabaseReference? = null
    private var devicesChildListener: ChildEventListener? = null

    // Listener B: deviceStatus (ValueEventListener — 접속 상태 실시간)
    private var statusRef: DatabaseReference? = null
    private var statusChildListener: ChildEventListener? = null

    // Rewarded ad state
    private var rewardedAd: RewardedAd? = null
    private var isRewardedAdLoading = false
    private var shouldPreloadRewardedAd = false

    // Mobile heartbeat job (60초 간격 RTDB 갱신)
    private var mobileHeartbeatJob: Job? = null
    private var screenshotTimeoutJob: Job? = null
    private var planJob: Job? = null
    private var policyJob: Job? = null
    private var refreshStartedAtMs: Long = 0L

    // Local caches
    private val deviceCache = mutableMapOf<String, DeviceData>()
    private val statusCache = mutableMapOf<String, String>() // deviceId -> "online"/"offline"
    private val heartbeatCache = mutableMapOf<String, Long>()

    // ── Listener setup ─────────────────────────────────────────

    fun startListening() {
        if (devicesChildListener != null) return // already listening
        val uid = auth.currentUser?.uid
        if (uid == null) {
            _uiState.value = DashboardUiState(isLoading = false, error = "Not signed in")
            return
        }

        deviceCache.clear()
        statusCache.clear()
        heartbeatCache.clear()
        shouldPreloadRewardedAd = true

        setupDevicesListener(uid)
        setupStatusListener(uid)

        // ChildEventListener만 사용하면 노드가 비어 있을 때 콜백이 오지 않아
        // 로딩이 끝나지 않을 수 있으므로 초기 1회 스냅샷으로 상태를 보정한다.
        bootstrapInitialState(uid)

        // 앱 진입 시 heartbeat 체크 → 크래시 감지 → deviceStatus "offline" 전환
        checkHeartbeat(uid)

        UserPlanRepository.startListening(uid)
        planJob = viewModelScope.launch {
            UserPlanRepository.userPlan.collect { applyUserEntitlement(it) }
        }
        PolicyRepository.startListening()
        policyJob = viewModelScope.launch {
            PolicyRepository.adFreeModeGlobal.collect { applyGlobalAdFreeMode(it) }
        }

        // ── Mobile heartbeat (60초 간격 RTDB 갱신) ──
        startMobileHeartbeat(uid)
    }

    private fun setupDevicesListener(uid: String) {
        devicesRef = db.reference.child("users").child(uid).child("devices")
        devicesChildListener = object : ChildEventListener {
            override fun onChildAdded(snapshot: DataSnapshot, previousChildName: String?) {
                val device = parseDevice(snapshot) ?: return
                deviceCache[device.id] = device
                emitState()
            }

            override fun onChildChanged(snapshot: DataSnapshot, previousChildName: String?) {
                val device = parseDevice(snapshot) ?: return
                deviceCache[device.id] = device
                emitState()
            }

            override fun onChildRemoved(snapshot: DataSnapshot) {
                val id = snapshot.key ?: return
                deviceCache.remove(id)
                emitState()
            }

            override fun onChildMoved(snapshot: DataSnapshot, previousChildName: String?) = Unit

            override fun onCancelled(error: DatabaseError) {
                handleListenerCancelled(error, tag = "devices", updateError = true)
            }
        }
        devicesRef?.addChildEventListener(devicesChildListener!!)
    }

    private fun setupStatusListener(uid: String) {
        statusRef = db.reference.child("users").child(uid).child("deviceStatus")
        statusChildListener = object : ChildEventListener {
            override fun onChildAdded(snapshot: DataSnapshot, previousChildName: String?) {
                val deviceId = snapshot.key ?: return
                statusCache[deviceId] = snapshot.getValue(String::class.java) ?: "offline"
                emitState()
            }

            override fun onChildChanged(snapshot: DataSnapshot, previousChildName: String?) {
                val deviceId = snapshot.key ?: return
                statusCache[deviceId] = snapshot.getValue(String::class.java) ?: "offline"
                emitState()
            }

            override fun onChildRemoved(snapshot: DataSnapshot) {
                val deviceId = snapshot.key ?: return
                statusCache.remove(deviceId)
                emitState()
            }

            override fun onChildMoved(snapshot: DataSnapshot, previousChildName: String?) = Unit

            override fun onCancelled(error: DatabaseError) {
                handleListenerCancelled(error, tag = "deviceStatus", updateError = false)
            }
        }
        statusRef?.addChildEventListener(statusChildListener!!)
    }

    private fun handleListenerCancelled(error: DatabaseError, tag: String, updateError: Boolean) {
        if (error.code == DatabaseError.PERMISSION_DENIED) {
            Timber.w(error.toException(), "$tag:onCancelled permission denied -> force sign-out")
            _uiState.value = _uiState.value.copy(isLoading = false, requiresForcedSignOut = true, error = null)
        } else {
            Timber.e(error.toException(), "$tag:onCancelled")
            if (updateError) {
                _uiState.value = _uiState.value.copy(isLoading = false, error = error.message)
            }
        }
    }

    fun loadRewardedAd(context: Context) {
        if (shouldSkipRewardedAds()) return
        if (isRewardedAdLoading || rewardedAd != null) return

        isRewardedAdLoading = true
        RewardedAd.load(
            context,
            REWARDED_TEST_AD_UNIT_ID,
            AdRequest.Builder().build(),
            object : RewardedAdLoadCallback() {
                override fun onAdLoaded(ad: RewardedAd) {
                    rewardedAd = ad
                    isRewardedAdLoading = false
                    shouldPreloadRewardedAd = false
                    _isRewardedAdReady.value = true
                }

                override fun onAdFailedToLoad(loadAdError: LoadAdError) {
                    Timber.w("rewarded:onAdFailedToLoad: ${loadAdError.message}")
                    rewardedAd = null
                    isRewardedAdLoading = false
                    _isRewardedAdReady.value = false
                }
            },
        )
    }

    private fun applyUserEntitlement(planRaw: String) {
        _userPlan.value = if (planRaw == "pro") "pro" else "free"

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
        } else if (shouldPreloadRewardedAd && rewardedAd == null && !isRewardedAdLoading) {
            loadRewardedAd(db.app.applicationContext)
        }
    }

    private fun shouldSkipRewardedAds(): Boolean {
        return _userPlan.value == "pro" || isAdFreeMode
    }

    fun showRewardedAdThenScreenshot(activity: Activity, deviceId: String) {
        if (shouldSkipRewardedAds()) {
            requestScreenshot(deviceId)
            return
        }

        val ad = rewardedAd
        if (ad == null) {
            loadRewardedAd(activity.applicationContext)
            requestScreenshot(deviceId)
            return
        }

        rewardedAd = null
        _isRewardedAdReady.value = false

        var rewardEarned = false
        ad.fullScreenContentCallback = object : FullScreenContentCallback() {
            override fun onAdDismissedFullScreenContent() {
                if (rewardEarned) {
                    requestScreenshot(deviceId)
                }
                loadRewardedAd(activity.applicationContext)
            }

            override fun onAdFailedToShowFullScreenContent(adError: com.google.android.gms.ads.AdError) {
                Timber.w("rewarded:onAdFailedToShow: ${adError.message}")
                requestScreenshot(deviceId)
                loadRewardedAd(activity.applicationContext)
            }
        }

        ad.show(activity) {
            rewardEarned = true
        }
    }

        // ── Mobile heartbeat (60초 간격) ─────────────────────────

    private fun startMobileHeartbeat(uid: String) {
        mobileHeartbeatJob?.cancel()
        mobileHeartbeatJob = viewModelScope.launch {
            while (true) {
                db.reference.child("users").child(uid)
                    .child("mobileHeartbeat")
                    .setValue(com.google.firebase.database.ServerValue.TIMESTAMP)
                    .addOnFailureListener { e -> Timber.w(e, "[HEARTBEAT] mobile heartbeat write failed") }
                delay(MOBILE_HEARTBEAT_INTERVAL_MS)
            }
        }
    }

    // ── Heartbeat check (pull-to-refresh 시만) ───────────────

    private fun bootstrapInitialState(uid: String) {
        var pendingReads = 2

        fun finishRead() {
            pendingReads -= 1
            if (
                pendingReads == 0 &&
                _uiState.value.isLoading &&
                !_uiState.value.requiresForcedSignOut
            ) {
                emitState()
            }
        }

        db.reference.child("users").child(uid).child("devices")
            .addListenerForSingleValueEvent(object : ValueEventListener {
                override fun onDataChange(snapshot: DataSnapshot) {
                    if (deviceCache.isEmpty()) {
                        snapshot.children.forEach { child ->
                            parseDevice(child)?.let { device ->
                                deviceCache[device.id] = device
                            }
                        }
                    }
                    finishRead()
                }

                override fun onCancelled(error: DatabaseError) {
                    if (error.code == DatabaseError.PERMISSION_DENIED) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            requiresForcedSignOut = true,
                            error = null,
                        )
                    } else {
                        Timber.w(error.toException(), "devices bootstrap cancelled")
                    }
                    finishRead()
                }
            })

        db.reference.child("users").child(uid).child("deviceStatus")
            .addListenerForSingleValueEvent(object : ValueEventListener {
                override fun onDataChange(snapshot: DataSnapshot) {
                    if (statusCache.isEmpty()) {
                        snapshot.children.forEach { child ->
                            val deviceId = child.key ?: return@forEach
                            val status = child.getValue(String::class.java) ?: "offline"
                            statusCache[deviceId] = status
                        }
                    }
                    finishRead()
                }

                override fun onCancelled(error: DatabaseError) {
                    if (error.code == DatabaseError.PERMISSION_DENIED) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                            requiresForcedSignOut = true,
                            error = null,
                        )
                    } else {
                        Timber.w(error.toException(), "deviceStatus bootstrap cancelled")
                    }
                    finishRead()
                }
            })
    }

    private fun checkHeartbeat(uid: String) {
        val deviceIds = deviceCache.keys.toList()
        if (deviceIds.isEmpty()) {
            finishRefreshIfNeeded()
            return
        }

        val now = System.currentTimeMillis()
        db.reference.child("users").child(uid)
            .child("heartbeat")
            .get()
            .addOnSuccessListener { snapshot ->
                val offlineUpdates = mutableMapOf<String, Any>()
                for (deviceId in deviceIds) {
                    val ts = snapshot.child(deviceId).getValue(Long::class.java) ?: 0L
                    heartbeatCache[deviceId] = ts

                    // 크래시 감지: heartbeat 2분 이상 만료 + 아직 online 상태인 기기만 offline 처리
                    val isExpired = ts <= 0L || (now - ts) >= OFFLINE_THRESHOLD_MS
                    val currentStatus = statusCache[deviceId]
                    if (isExpired && currentStatus != "offline") {
                        offlineUpdates[deviceId] = "offline"
                    }
                }

                if (offlineUpdates.isNotEmpty()) {
                    db.reference.child("users").child(uid)
                        .child("deviceStatus")
                        .updateChildren(offlineUpdates)
                }
                emitState()
                finishRefreshIfNeeded()
            }
            .addOnFailureListener { e ->
                Timber.e(e, "heartbeat batch check failed")
                finishRefreshIfNeeded()
            }
    }

    private fun finishRefreshIfNeeded() {
        if (!_uiState.value.isRefreshing) return

        val elapsed = System.currentTimeMillis() - refreshStartedAtMs
        val remaining = (MIN_REFRESH_DISPLAY_MS - elapsed).coerceAtLeast(0L)

        viewModelScope.launch {
            if (remaining > 0L) delay(remaining)
            _uiState.value = _uiState.value.copy(isRefreshing = false)
        }
    }

    // ── State emission ─────────────────────────────────────

    private fun emitState() {
        val devices = deviceCache.values.map { device ->
            val rawStatus = statusCache[device.id] ?: "offline"
            val isOnline = rawStatus == "online" || rawStatus == "monitoring" || rawStatus == "sleep"
            val isMonitoring = rawStatus == "monitoring"
            val isSleeping = rawStatus == "sleep"
            val heartbeatTs = heartbeatCache[device.id] ?: 0L
            device.copy(isOnline = isOnline, isMonitoring = isMonitoring, isSleeping = isSleeping, lastSeen = heartbeatTs)
        }

        val currentLoading = _uiState.value.screenshotLoadingDeviceId
        val stillLoading = if (currentLoading != null) {
            val dev = devices.find { it.id == currentLoading }
            val prevDev = _uiState.value.devices.find { it.id == currentLoading }
            dev != null && dev.screenshotTs == prevDev?.screenshotTs
        } else false

        // 스크린샷 성공 시 timeout 취소 + 에러 초기화
        val screenshotError = if (!stillLoading && currentLoading != null) {
            screenshotTimeoutJob?.cancel()
            null
        } else {
            _uiState.value.screenshotError
        }

        _uiState.value = DashboardUiState(
            isLoading = false,
            devices = devices,
            screenshotLoadingDeviceId = if (stillLoading) currentLoading else null,
            screenshotError = screenshotError,
            isRefreshing = _uiState.value.isRefreshing,
        )
    }

    // ── Snapshot parsing ───────────────────────────────────

    private fun parseDevice(snapshot: DataSnapshot): DeviceData? {
        val id = snapshot.key ?: return null
        val name = snapshot.child("name").getValue(String::class.java) ?: id
        val platform = snapshot.child("platform").getValue(String::class.java) ?: ""

        val tasks = snapshot.child("tasks").children.mapNotNull { taskSnap ->
            parseTask(taskSnap)
        }

        // Screenshot latest
        val screenshotLatest = snapshot.child("screenshots").child("latest")
        val rawScreenshotUrl = screenshotLatest.child("url").getValue(String::class.java)
        val screenshotUrl = rawScreenshotUrl?.takeIf {
            it.startsWith("https://firebasestorage.googleapis.com/") ||
            it.startsWith("https://progresseye-49244.firebasestorage.app/")
        }
        val screenshotTs = screenshotLatest.child("ts").getValue(Long::class.java) ?: 0L

        // Hardware stats
        val statsSnap = snapshot.child("stats")
        val cpuUsage = statsSnap.child("cpu").getValue(Double::class.java)?.toFloat()
        val gpuUsage = statsSnap.child("gpu").getValue(Double::class.java)?.toFloat()
        val ramUsage = statsSnap.child("ram").getValue(Double::class.java)?.toFloat()

        return DeviceData(
            id = id,
            name = name,
            platform = platform,
            isOnline = false, // statusCache에서 emitState()가 덮어씄
            lastSeen = 0L, // heartbeatCache에서 emitState()가 덮어씄
            tasks = tasks,
            screenshotUrl = screenshotUrl,
            screenshotTs = screenshotTs,
            cpuUsage = cpuUsage,
            gpuUsage = gpuUsage,
            ramUsage = ramUsage,
        )
    }

    private fun parseTask(snapshot: DataSnapshot): TaskData? {
        val id = snapshot.key ?: return null
        val progressRaw = (snapshot.child("p").value as? Number)?.toFloat() ?: 0f
        val status = snapshot.child("s").getValue(String::class.java) ?: "r"
        val label = snapshot.child("l").getValue(String::class.java) ?: id

        return TaskData(
            id = id,
            label = label,
            progress = progressRaw / 100f, // RTDB 0-100 → UI 0f..1f
            status = status,
        )
    }

    // ── Screenshot command ─────────────────────────────────

    fun requestScreenshot(deviceId: String) {
        val uid = auth.currentUser?.uid
        if (uid == null) {
            Timber.w("[SCREENSHOT] uid is null, aborting")
            return
        }
        Timber.d("[SCREENSHOT] requesting screenshot for device=$deviceId uid=$uid")
        _uiState.value = _uiState.value.copy(screenshotLoadingDeviceId = deviceId)

        // Timeout: 30s
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

        val commandRef = db.reference
            .child("users").child(uid)
            .child("commands").child("screenshot")
        commandRef.setValue(
            mapOf(
                "ts" to System.currentTimeMillis() / 1000,
                "cmdId" to UUID.randomUUID().toString(),
                "targetDeviceId" to deviceId,
            )
        )
            .addOnSuccessListener {
                Timber.d("[SCREENSHOT] command written to RTDB successfully")
            }
            .addOnFailureListener { e ->
                Timber.e(e, "[SCREENSHOT] command write FAILED: ${e.message}")
                screenshotTimeoutJob?.cancel()
                _uiState.value = _uiState.value.copy(
                    screenshotLoadingDeviceId = null,
                    screenshotError = getApplication<Application>().getString(com.chg.progeresseye.R.string.screenshot_command_failed, e.message ?: "")
                )
            }
    }

    fun clearScreenshotError() {
        _uiState.value = _uiState.value.copy(screenshotError = null)
    }

    fun sendSleepCommand(deviceId: String) {
        val uid = auth.currentUser?.uid ?: return
        db.reference.child("users").child(uid).child("commands").child("sleep")
            .setValue(mapOf(
                "ts" to System.currentTimeMillis() / 1000,
                "cmdId" to UUID.randomUUID().toString(),
                "targetDeviceId" to deviceId,
            ))
            .addOnSuccessListener { Timber.d("[CMD] sleep command sent: $deviceId") }
            .addOnFailureListener { e -> Timber.w(e, "[CMD] sleep command failed") }
    }

    fun sendShutdownCommand(deviceId: String) {
        val uid = auth.currentUser?.uid ?: return
        db.reference.child("users").child(uid).child("commands").child("shutdown")
            .setValue(mapOf(
                "ts" to System.currentTimeMillis() / 1000,
                "cmdId" to UUID.randomUUID().toString(),
                "targetDeviceId" to deviceId,
            ))
            .addOnSuccessListener { Timber.d("[CMD] shutdown command sent: $deviceId") }
            .addOnFailureListener { e -> Timber.w(e, "[CMD] shutdown command failed") }
    }

    fun consumeForcedSignOut() {
        _uiState.value = _uiState.value.copy(requiresForcedSignOut = false)
    }

    // ── Pull-to-Refresh ────────────────────────────────

    fun refresh() {
        val uid = auth.currentUser?.uid ?: return
        if (_uiState.value.isRefreshing) return
        refreshStartedAtMs = System.currentTimeMillis()
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        // pull-to-refresh 시에만 heartbeat 확인 → 크래시 감지
        checkHeartbeat(uid)
    }

    // ── Lifecycle: pause / cleanup ──────────────────────

    fun stopListening() {
        devicesChildListener?.let { listener: ChildEventListener ->
            devicesRef?.removeEventListener(listener)
        }
        devicesChildListener = null

        statusChildListener?.let { listener ->
            statusRef?.removeEventListener(listener)
        }
        statusChildListener = null

        mobileHeartbeatJob?.cancel()
        mobileHeartbeatJob = null
        screenshotTimeoutJob?.cancel()
        screenshotTimeoutJob = null

        rewardedAd = null
        _isRewardedAdReady.value = false
        isRewardedAdLoading = false
        shouldPreloadRewardedAd = false
        _isAdFreeModeEnabled.value = false
        isAdFreeMode = false

        planJob?.cancel()
        planJob = null
        UserPlanRepository.reset()

        policyJob?.cancel()
        policyJob = null
        PolicyRepository.reset()
    }

    override fun onCleared() {
        super.onCleared()
        stopListening()
    }

    companion object {
        /** Mobile heartbeat interval (60 seconds). */
        private const val MOBILE_HEARTBEAT_INTERVAL_MS = 60_000L
        /** Consider device offline if heartbeat > 2 minutes ago. */
        private const val OFFLINE_THRESHOLD_MS = 120_000L
        /** Keep pull-to-refresh indicator visible long enough for smooth animation. */
        private const val MIN_REFRESH_DISPLAY_MS = 900L
        /** Screenshot request timeout. */
        private const val SCREENSHOT_TIMEOUT_MS = 30_000L
        private const val REWARDED_TEST_AD_UNIT_ID = "ca-app-pub-3940256099942544/5224354917"
    }
}
