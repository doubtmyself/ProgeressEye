package com.chg.progeresseye.ui.screen.dashboard

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chg.progeresseye.data.model.DashboardUiState
import com.chg.progeresseye.data.model.DeviceData
import com.chg.progeresseye.data.model.TaskData
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.database.ChildEventListener
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.DatabaseReference
import com.google.firebase.database.FirebaseDatabase
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

// ═════════════════════════════════════════════════════════
// DashboardViewModel — RTDB listener for devices + tasks
//
// 대역폭 최적화:
//   Listener: users/{uid}/devices → ChildEventListener
//     - 디바이스/태스크/스크린샷 변경 시에만 해당 기기 데이터 수신
//   Heartbeat: 5분 폴링으로 온라인/오프라인 판정
//     - 실시간 리스너 대신 주기적 읽기로 대역폭 절감
//     - 오프라인 감지 시 RTDB에 status write
// ═════════════════════════════════════════════════════════

class DashboardViewModel : ViewModel() {

    private val auth = FirebaseAuth.getInstance()
    private val db = FirebaseDatabase.getInstance()

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    // Devices listener (ChildEventListener — only changed device data sent)
    private var devicesRef: DatabaseReference? = null
    private var devicesChildListener: ChildEventListener? = null

    // Heartbeat polling job (실시간 리스너 대신 5분 폴링)
    private var heartbeatPollingJob: Job? = null

    // Local device cache — ChildEventListener gives deltas, we merge locally
    private val deviceCache = mutableMapOf<String, DeviceData>()
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
        heartbeatCache.clear()

        // ── Listener: devices (ChildEventListener) ──
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

        // ── Heartbeat polling (5분 주기) ──
        startHeartbeatPolling(uid)
    }

    // ── Heartbeat polling ───────────────────────────────────

    private fun startHeartbeatPolling(uid: String) {
        heartbeatPollingJob?.cancel()
        heartbeatPollingJob = viewModelScope.launch {
            // 최초 1회는 즉시 실행, 이후 5분 간격
            while (true) {
                pollHeartbeat(uid)
                delay(HEARTBEAT_POLL_INTERVAL_MS)
            }
        }
    }

    private fun pollHeartbeat(uid: String) {
        val heartbeatRef = db.reference.child("users").child(uid).child("heartbeat")
        heartbeatRef.get().addOnSuccessListener { snapshot ->
            heartbeatCache.clear()
            val now = System.currentTimeMillis()

            for (child in snapshot.children) {
                val deviceId = child.key ?: continue
                val ts = child.getValue(Long::class.java) ?: 0L
                heartbeatCache[deviceId] = ts

                // 오프라인 감지: heartbeat가 5분 초과면 status를 offline으로 갱신
                val isExpired = ts <= 0L || (now - ts) >= OFFLINE_THRESHOLD_MS
                if (isExpired) {
                    db.reference
                        .child("users").child(uid)
                        .child("devices").child(deviceId)
                        .child("status").setValue("offline")
                }
            }
            emitState()
        }.addOnFailureListener { e ->
            Log.e(TAG, "heartbeat poll failed", e)
        }
    }

    // ── State emission ─────────────────────────────────────

    private fun emitState() {
        val now = System.currentTimeMillis()
        val devices = deviceCache.values.map { device ->
            val heartbeatTs = heartbeatCache[device.id] ?: 0L
            val isOnline = heartbeatTs > 0L &&
                (now - heartbeatTs) < OFFLINE_THRESHOLD_MS
            device.copy(isOnline = isOnline, lastSeen = heartbeatTs)
        }

        val currentLoading = _uiState.value.screenshotLoadingDeviceId
        val stillLoading = if (currentLoading != null) {
            val dev = devices.find { it.id == currentLoading }
            val prevDev = _uiState.value.devices.find { it.id == currentLoading }
            dev != null && dev.screenshotUrl == prevDev?.screenshotUrl
        } else false

        _uiState.value = DashboardUiState(
            isLoading = false,
            devices = devices,
            screenshotLoadingDeviceId = if (stillLoading) currentLoading else null,
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

        return DeviceData(
            id = id,
            name = name,
            platform = platform,
            isOnline = false, // heartbeat 폴링에서 emitState()가 덮어씀
            lastSeen = 0L,
            tasks = tasks,
            screenshotUrl = screenshotUrl,
            screenshotTs = screenshotTs,
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
        val uid = auth.currentUser?.uid ?: return
        _uiState.value = _uiState.value.copy(screenshotLoadingDeviceId = deviceId)
        val commandRef = db.reference
            .child("users").child(uid)
            .child("commands").child("screenshot")
        commandRef.setValue(mapOf("ts" to System.currentTimeMillis() / 1000))
    }

    // ── Pull-to-Refresh ────────────────────────────────

    fun refresh() {
        val uid = auth.currentUser?.uid ?: return
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        // 즈시 heartbeat 폴링 + UI 재방출
        pollHeartbeat(uid)
    }

    // ── Lifecycle: pause / cleanup ──────────────────────

    fun stopListening() {
        devicesChildListener?.let { listener: ChildEventListener ->
            devicesRef?.removeEventListener(listener)
        }
        devicesChildListener = null

        heartbeatPollingJob?.cancel()
        heartbeatPollingJob = null
    }

    override fun onCleared() {
        super.onCleared()
        stopListening()
    }

    companion object {
        private const val TAG = "DashboardViewModel"
        /** Heartbeat polling interval (5 minutes). */
        private const val HEARTBEAT_POLL_INTERVAL_MS = 5 * 60 * 1000L
        /** Consider device offline if heartbeat > 5 minutes ago. */
        private const val OFFLINE_THRESHOLD_MS = 5 * 60 * 1000L
    }
}
