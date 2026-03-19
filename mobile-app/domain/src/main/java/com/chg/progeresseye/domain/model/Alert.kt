package com.chg.progeresseye.domain.model

enum class AlertType {
    COMPLETION, STALL, IMAGE_CHANGE, OFFLINE
}

data class AlertItem(
    val id: String,
    val isRead: Boolean = false,
    val timestamp: Long = 0L,
    val title: String = "",
    val body: String = "",
    val type: AlertType = AlertType.IMAGE_CHANGE,
    val deviceName: String = ""
)
