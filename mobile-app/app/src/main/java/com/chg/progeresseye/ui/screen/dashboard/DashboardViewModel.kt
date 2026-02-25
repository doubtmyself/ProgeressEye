package com.chg.progeresseye.ui.screen.dashboard

import android.util.Log
import androidx.lifecycle.ViewModel
import com.chg.progeresseye.data.model.DashboardUiState
import com.chg.progeresseye.data.model.DeviceData
import com.chg.progeresseye.data.model.TaskData
import com.google.firebase.auth.FirebaseAuth
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
// ═════════════════════════════════════════════════════════

class DashboardViewModel : ViewModel() {

    private val auth = FirebaseAuth.getInstance()
    private val db = FirebaseDatabase.getInstance()

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    // Listener + ref stored for cleanup
    private var devicesRef: DatabaseReference? = null
    private var devicesListener: ValueEventListener? = null

    // Lifecycle-driven: MainScreen calls startListening / stopListening

    // ── Listener setup ─────────────────────────────────────

    fun startListening() {
        if (devicesListener != null) return  // already listening
        val uid = auth.currentUser?.uid
        if (uid == null) {
            _uiState.value = DashboardUiState(
                isLoading = false,
                error = "Not signed in",
            )
            return
        }

        devicesRef = db.reference.child("users").child(uid).child("devices")

        devicesListener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                val devices = snapshot.children.mapNotNull { parseDevice(it) }
                val currentLoading = _uiState.value.screenshotLoadingDeviceId
                // Clear loading indicator if screenshot URL changed for that device
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

            override fun onCancelled(error: DatabaseError) {
                Log.e(TAG, "devices:onCancelled", error.toException())
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = error.message,
                )
            }
        }

        devicesRef?.addValueEventListener(devicesListener!!)
    }

    // ── Snapshot parsing ───────────────────────────────────

    private fun parseDevice(snapshot: DataSnapshot): DeviceData? {
        val id = snapshot.key ?: return null
        val name = snapshot.child("name").getValue(String::class.java) ?: id
        val platform = snapshot.child("platform").getValue(String::class.java) ?: ""
        val lastSeen = snapshot.child("lastSeen").getValue(Long::class.java) ?: 0L

        // Determine online: lastSeen within ONLINE_THRESHOLD_MS
        val isOnline = (System.currentTimeMillis() - lastSeen) < ONLINE_THRESHOLD_MS

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
            isOnline = isOnline,
            lastSeen = lastSeen,
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
        _uiState.value = _uiState.value.copy(isRefreshing = true)
        stopListening()
        startListening()
        // isRefreshing is cleared when onDataChange fires
    }

    // ── Lifecycle: pause / cleanup ──────────────────────

    fun stopListening() {
        devicesListener?.let { listener ->
            devicesRef?.removeEventListener(listener)
        }
        devicesListener = null
    }

    override fun onCleared() {
        super.onCleared()
        stopListening()
    }

    companion object {
        private const val TAG = "DashboardViewModel"
        /** Consider device offline if lastSeen > 2 minutes ago. */
        private const val ONLINE_THRESHOLD_MS = 2 * 60 * 1000L
    }
}
