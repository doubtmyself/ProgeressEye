package com.chg.progeresseye.data.model

// ═════════════════════════════════════════════════════════
// Firebase RTDB data models
// Path: users/{uid}/devices/{deviceId}/
// ═════════════════════════════════════════════════════════

/**
 * 모니터링 대상인 개별 작업(예: 렌더링, 다운로드 등)의 상태를 나타내는 데이터 모델
 *
 * @property id 작업 식별자
 * @property label 작업의 화면 표시 이름
 * @property progress 작업 진행률 (0.0 ~ 1.0)
 * @property status 현재 상태 코드
 * @constructor Create empty [TaskData]
 */
data class TaskData(
    val id: String,
    val label: String,
    /** Progress fraction 0f..1f (RTDB stores 0-100, converted on parse). */
    val progress: Float,
    /** Status code: "r" = running, "f" = frozen/stalled, "c" = completed, "s" = stopped, "i" = idle (unchecked). */
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
    /** True when PC is in sleep mode (deviceStatus == "sleep"). */
    val isSleeping: Boolean = false,
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
    val requiresForcedSignOut: Boolean = false,
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
    const val STOPPED = "s"
    const val IDLE = "i"
}
