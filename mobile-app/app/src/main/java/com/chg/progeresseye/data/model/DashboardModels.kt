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
    /** Status code: "r" = running, "f" = frozen/stalled, "c" = completed. */
    val status: String,
)

/** A registered PC device with its tasks. */
data class DeviceData(
    val id: String,
    val name: String,
    val platform: String,
    val isOnline: Boolean,
    val lastSeen: Long,
    val tasks: List<TaskData>,
)

/** Dashboard screen UI state. */
data class DashboardUiState(
    val isLoading: Boolean = true,
    val devices: List<DeviceData> = emptyList(),
    val error: String? = null,
)

// ── Status constants (match PC Agent codes) ──
object TaskStatus {
    const val RUNNING = "r"
    const val FROZEN = "f"
    const val COMPLETED = "c"
}
