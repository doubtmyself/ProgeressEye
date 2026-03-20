package com.chg.progeresseye.domain.model

/**
 * 모바일 앱으로 수신되는 알림의 종류를 정의하는 열거형입니다.
 */
enum class AlertType {
    COMPLETION, STALL, IMAGE_CHANGE, OFFLINE
}

/**
 * 모바일 앱에 표시될 개별 알림 항목을 나타내는 도메인 모델입니다.
 *
 * @property id 알림의 고유 식별자
 * @property isRead 사용자의 알림 읽음 여부
 * @property timestamp 알림이 생성된 시간 (Epoch milliseconds)
 * @property title 알림 제목
 * @property body 알림의 상세 내용
 * @property type 알림의 유형 ([AlertType])
 * @property deviceName 알림을 발생시킨 기기의 이름
 */
data class AlertItem(
    val id: String,
    val isRead: Boolean = false,
    val timestamp: Long = 0L,
    val title: String = "",
    val body: String = "",
    val type: AlertType = AlertType.IMAGE_CHANGE,
    val deviceName: String = ""
)
