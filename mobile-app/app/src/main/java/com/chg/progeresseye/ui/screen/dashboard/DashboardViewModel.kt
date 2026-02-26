package com.chg.progeresseye.ui.screen.dashboard

import android.util.Log
import androidx.lifecycle.ViewModel
import com.chg.progeresseye.data.model.DashboardUiState
import com.chg.progeresseye.data.model.DeviceData
import com.chg.progeresseye.data.model.TaskData
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.database.ChildEventListener
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.DatabaseReference
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

// ═════════════════════════════════════════════════════════
// DashboardViewModel — RTDB listener for devices + tasks
//
// 대역폭 최적화:
//   Listener A: users/{uid}/devices  → ChildEventListener
//     - 디바이스/태스크/스크린샷 변경 시에만 해당 기기 데이터 수신
//     - 하트비트(lastSeen) 변경으로는 트리거되지 않음
//   Listener B: users/{uid}/heartbeat → ValueEventListener
//     - {deviceId: timestamp_ms} 형태, 페이로드 ~20바이트
//     - 온라인/오프라인 판정용
// ═════════════════════════════════════════════════════════

class DashboardViewModel : ViewModel() {

    private val auth = FirebaseAuth.getInstance()
    private val db = FirebaseDatabase.getInstance()

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    // Devices listener (ChildEventListener — only changed device data sent)
    private var devicesRef: DatabaseReference? = null
    private var devicesChildListener: ChildEventListener? = null

    // Heartbeat listener (ValueEventListener — tiny payload)
    private var heartbeatRef: DatabaseReference? = null
    private var heartbeatListener: ValueEventListener? = null

    // Local device cache — ChildEventListener gives deltas, we merge locally
    private val deviceCache = mutableMapOf<String, DeviceData>()
    private val heartbeatCache = mutableMapOf<String, Long>()

    // ── Listener setup ─────────────────────────────────────

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

        // ── Listener A: devices (ChildEventListener) ──
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

        // ── Listener B: heartbeat (ValueEventListener, ~20 bytes) ──
        heartbeatRef = db.reference.child("users").child(uid).child("heartbeat")

        heartbeatListener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                heartbeatCache.clear()
                for (child in snapshot.children) {
                    val deviceId = child.key ?: continue
                    val ts = child.getValue(Long::class.java) ?: 0L
                    heartbeatCache[deviceId] = ts
                }
                emitState()
            }

            override fun onCancelled(error: DatabaseError) {
                Log.e(TAG, "heartbeat:onCancelled", error.toException())
            }
        }
        heartbeatRef?.addValueEventListener(heartbeatListener!!)
    }

    // ── State emission ─────────────────────────────────────

    private fun emitState() {
        val devices = deviceCache.values.map { device ->
            // Online status from heartbeat path (not from device lastSeen)
            val heartbeatTs = heartbeatCache[device.id] ?: 0L
            val isOnline = heartbeatTs > 0L &&
                (System.currentTimeMillis() - heartbeatTs) < ONLINE_THRESHOLD_MS
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
            isOnline = false, // will be overridden by heartbeat in emitState()
            lastSeen = 0L, // heartbeat 경로에서 emitState()가 덮어씀
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
        // 리스너를 재연결하지 않음 — 이미 실시간이므로 UI 상태만 리셋
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        // 캐시 기반으로 즉시 재방출 → isRefreshing 해제
        emitState()
    }

    // ── Lifecycle: pause / cleanup ──────────────────────

    fun stopListening() {
        devicesChildListener?.let { listener: ChildEventListener ->
            devicesRef?.removeEventListener(listener)
        }
        devicesChildListener = null

        heartbeatListener?.let { listener ->
            heartbeatRef?.removeEventListener(listener)
        }
        heartbeatListener = null
    }

    override fun onCleared() {
        super.onCleared()
        stopListening()
    }

    companion object {
        private const val TAG = "DashboardViewModel"
        /** Consider device offline if heartbeat > 2 minutes ago. */
        private const val ONLINE_THRESHOLD_MS = 2 * 60 * 1000L
    }
}
