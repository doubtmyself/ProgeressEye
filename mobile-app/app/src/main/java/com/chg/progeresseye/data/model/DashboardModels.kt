package com.chg.progeresseye.data.model

// ═════════════════════════════════════════════════════════
// Firebase RTDB data models
// Path: users/{uid}/devices/{deviceId}/
// ═════════════════════════════════════════════════════════

/** Single monitored task (= one capture region on PC). */
data class TaskData(
    val id: String,
    val label: String,
    /** Progress fraction 0f..1f (RTDB stores 0-100, converted on parse). */
    val progress: Float,
    /** Status code: "r" = running, "f" = frozen/stalled, "c" = completed, "i" = idle (unchecked). */
    val status: String,
)

/** A registered PC device with its tasks. */
data class DeviceData(
    val id: String,
    val name: String,
    val platform: String,
    val isOnline: Boolean,
    val lastSeen: Long,
    /** True when PC is actively monitoring (deviceStatus == "monitoring"). */
    val isMonitoring: Boolean = false,
    val tasks: List<TaskData>,
    /** Latest screenshot download URL from Firebase Storage. */
    val screenshotUrl: String? = null,
    /** Latest screenshot epoch seconds. */
    val screenshotTs: Long = 0L,
    /** CPU usage 0-100 (from PC agent). Null if unavailable. */
    val cpuUsage: Float? = null,
    /** GPU usage 0-100 (from PC agent). Null if unavailable. */
    val gpuUsage: Float? = null,
    /** RAM usage 0-100 (from PC agent). Null if unavailable. */
    val ramUsage: Float? = null,
)

/** Dashboard screen UI state. */
data class DashboardUiState(
    val isLoading: Boolean = true,
    val devices: List<DeviceData> = emptyList(),
    val error: String? = null,
    /** Device ID currently waiting for screenshot response. */
    val screenshotLoadingDeviceId: String? = null,
    /** Screenshot error message to display (timeout, failure). */
    val screenshotError: String? = null,
    /** True during pull-to-refresh. */
    val isRefreshing: Boolean = false,
)

// ── Status constants (match PC Agent codes) ──
object TaskStatus {
    const val RUNNING = "r"
    const val FROZEN = "f"
    const val COMPLETED = "c"
    const val IDLE = "i"
}
