package com.chg.progeresseye.ui.screen.dashboard

import android.app.Activity
import android.content.Context
import android.util.Log
import androidx.lifecycle.ViewModel
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
import com.google.android.gms.ads.rewarded.RewardedAd
import com.google.android.gms.ads.rewarded.RewardedAdLoadCallback
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
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

class DashboardViewModel : ViewModel() {

    private val auth = FirebaseAuth.getInstance()
    private val db = FirebaseDatabase.getInstance()

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    private val _userPlan = MutableStateFlow("free")
    val userPlan: StateFlow<String> = _userPlan.asStateFlow()

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

    // Local caches
    private val deviceCache = mutableMapOf<String, DeviceData>()
    private val statusCache = mutableMapOf<String, String>() // deviceId -> "online"/"offline"
    private val heartbeatCache = mutableMapOf<String, Long>()

    // ── Listener setup ─────────────────────────────────────────

    fun startListening() {
        if (devicesChildListener != null) return // already listening
        val uid = auth.currentUser?.uid
        if (uid == null) {
            _uiState.value = DashboardUiState(
                isLoading = false,
                error = "Not signed in",
            )
            return
        }

        deviceCache.clear()
        statusCache.clear()
        heartbeatCache.clear()
        shouldPreloadRewardedAd = true

        // ── Listener A: devices (ChildEventListener) — 태스크/스크린샷 ──
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

            override fun onChildMoved(snapshot: DataSnapshot, previousChildName: String?) {
                // 순서 변경 — 무시
            }

            override fun onCancelled(error: DatabaseError) {
                Log.e(TAG, "devices:onCancelled", error.toException())
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = error.message,
                )
            }
        }
        devicesRef?.addChildEventListener(devicesChildListener!!)

        // ── Listener B: deviceStatus (ChildEventListener) — 증분 업데이트 ──
        statusRef = db.reference.child("users").child(uid).child("deviceStatus")

        statusChildListener = object : ChildEventListener {
            override fun onChildAdded(snapshot: DataSnapshot, previousChildName: String?) {
                val deviceId = snapshot.key ?: return
                val status = snapshot.getValue(String::class.java) ?: "offline"
                statusCache[deviceId] = status
                emitState()
            }

            override fun onChildChanged(snapshot: DataSnapshot, previousChildName: String?) {
                val deviceId = snapshot.key ?: return
                val status = snapshot.getValue(String::class.java) ?: "offline"
                statusCache[deviceId] = status
                emitState()
            }

            override fun onChildRemoved(snapshot: DataSnapshot) {
                val deviceId = snapshot.key ?: return
                statusCache.remove(deviceId)
                emitState()
            }

            override fun onChildMoved(snapshot: DataSnapshot, previousChildName: String?) {
                // No-op
            }

            override fun onCancelled(error: DatabaseError) {
                Log.e(TAG, "deviceStatus:child:onCancelled", error.toException())
            }
        }
        statusRef?.addChildEventListener(statusChildListener!!)

        // ── Listener C 최적화: user plan 1회 조회 ──
        db.reference.child("users").child(uid).child("plan")
            .get()
            .addOnSuccessListener { snapshot ->
                val plan = snapshot.getValue(String::class.java)?.lowercase() ?: "free"
                applyUserPlan(plan)
            }
            .addOnFailureListener { error ->
                Log.e(TAG, "plan:get:onFailure", error)
                applyUserPlan("free")
            }

        // ── Mobile heartbeat (60초 간격 RTDB 갱신) ──
        startMobileHeartbeat(uid)
    }

    fun loadRewardedAd(context: Context) {
        if (_userPlan.value != "free") return
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
                    Log.w(TAG, "rewarded:onAdFailedToLoad: ${loadAdError.message}")
                    rewardedAd = null
                    isRewardedAdLoading = false
                    _isRewardedAdReady.value = false
                }
            },
        )
    }

    private fun applyUserPlan(planRaw: String) {
        _userPlan.value = if (planRaw == "pro") "pro" else "free"

        if (_userPlan.value == "pro") {
            rewardedAd = null
            _isRewardedAdReady.value = false
            shouldPreloadRewardedAd = false
        } else if (shouldPreloadRewardedAd && rewardedAd == null && !isRewardedAdLoading) {
            loadRewardedAd(db.app.applicationContext)
        }
    }

    fun showRewardedAdThenScreenshot(activity: Activity, deviceId: String) {
        if (_userPlan.value != "free") {
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
                Log.w(TAG, "rewarded:onAdFailedToShow: ${adError.message}")
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
                delay(MOBILE_HEARTBEAT_INTERVAL_MS)
            }
        }
    }

    // ── Heartbeat check (pull-to-refresh 시만) ───────────────

    private fun checkHeartbeat(uid: String) {
        val deviceIds = deviceCache.keys.toList()
        if (deviceIds.isEmpty()) {
            _uiState.value = _uiState.value.copy(isRefreshing = false)
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
            }
            .addOnFailureListener { e ->
                Log.e(TAG, "heartbeat batch check failed", e)
                _uiState.value = _uiState.value.copy(isRefreshing = false)
            }
    }

    // ── State emission ─────────────────────────────────────

    private fun emitState() {
        val devices = deviceCache.values.map { device ->
            val rawStatus = statusCache[device.id] ?: "offline"
            val isOnline = rawStatus == "online" || rawStatus == "monitoring"
            val isMonitoring = rawStatus == "monitoring"
            val heartbeatTs = heartbeatCache[device.id] ?: 0L
            device.copy(isOnline = isOnline, isMonitoring = isMonitoring, lastSeen = heartbeatTs)
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
            isRefreshing = false,
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
        val screenshotUrl = screenshotLatest.child("url").getValue(String::class.java)
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
        val progressRaw = snapshot.child("p").getValue(Double::class.java)?.toFloat() ?: 0f
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
            Log.w(TAG, "[SCREENSHOT] uid is null, aborting")
            return
        }
        Log.d(TAG, "[SCREENSHOT] requesting screenshot for device=$deviceId uid=$uid")
        _uiState.value = _uiState.value.copy(screenshotLoadingDeviceId = deviceId)

        // Timeout: 30s
        screenshotTimeoutJob?.cancel()
        screenshotTimeoutJob = viewModelScope.launch {
            delay(SCREENSHOT_TIMEOUT_MS)
            if (_uiState.value.screenshotLoadingDeviceId == deviceId) {
                Log.w(TAG, "[SCREENSHOT] timeout after ${SCREENSHOT_TIMEOUT_MS / 1000}s")
                _uiState.value = _uiState.value.copy(
                    screenshotLoadingDeviceId = null,
                    screenshotError = "PC\uAC00 \uC751\uB2F5\uD558\uC9C0 \uC54A\uC2B5\uB2C8\uB2E4. PC\uAC00 \uCF1C\uC838 \uC788\uB294\uC9C0 \uD655\uC778\uD574\uC8FC\uC138\uC694."
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
            )
        )
            .addOnSuccessListener {
                Log.d(TAG, "[SCREENSHOT] command written to RTDB successfully")
            }
            .addOnFailureListener { e ->
                Log.e(TAG, "[SCREENSHOT] command write FAILED: ${e.message}")
                screenshotTimeoutJob?.cancel()
                _uiState.value = _uiState.value.copy(
                    screenshotLoadingDeviceId = null,
                    screenshotError = "\uBA85\uB839 \uC804\uC1A1 \uC2E4\uD328: ${e.message}"
                )
            }
    }

    fun clearScreenshotError() {
        _uiState.value = _uiState.value.copy(screenshotError = null)
    }

    // ── Pull-to-Refresh ────────────────────────────────

    fun refresh() {
        val uid = auth.currentUser?.uid ?: return
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
    }

    override fun onCleared() {
        super.onCleared()
        stopListening()
    }

    companion object {
        private const val TAG = "DashboardViewModel"
        /** Mobile heartbeat interval (60 seconds). */
        private const val MOBILE_HEARTBEAT_INTERVAL_MS = 60_000L
        /** Consider device offline if heartbeat > 2 minutes ago. */
        private const val OFFLINE_THRESHOLD_MS = 120_000L
        /** Screenshot request timeout. */
        private const val SCREENSHOT_TIMEOUT_MS = 30_000L
        private const val REWARDED_TEST_AD_UNIT_ID = "ca-app-pub-3940256099942544/5224354917"
    }
}
