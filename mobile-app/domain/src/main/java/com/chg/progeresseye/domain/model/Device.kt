package com.chg.progeresseye.domain.model

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

/**
 * 데스크탑 에이전트가 설치된 제어 대상 PC의 상태 및 하드웨어 점유율 정보를 담은 모델
 *
 * @property id 디바이스 식별자
 * @property name 화면에 표시할 디바이스 이름
 * @property platform OS 플랫폼
 * @property isOnline 현재 실시간 통신 연결 상태
 * @property lastSeen 마지막으로 하트비트가 확인된 시간
 * @property isMonitoring 작업 모니터링이 활성화된 상태인지 여부
 * @property isSleeping 기기가 절전 상태인지 여부
 * @property tasks 모니터링 중인 작업 데이터 목록
 * @property screenshotUrl 가장 최근에 캡처된 화면의 스토리지 URL
 * @property screenshotTs 스크린샷이 캡처된 시간
 * @property cpuUsage PC CPU 점유율
 * @property gpuUsage PC GPU 점유율
 * @property ramUsage PC RAM 점유율
 * @constructor Create empty [DeviceData]
 */
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

// ── Status constants (match PC Agent codes) ──
object TaskStatus {
    const val RUNNING = "r"
    const val FROZEN = "f"
    const val COMPLETED = "c"
    const val STOPPED = "s"
    const val IDLE = "i"
}
