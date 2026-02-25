package com.chg.progeresseye.data.model

// ═════════════════════════════════════════════════════════
// Alert data models
// TODO: Replace with FCM + local Room DB storage
// ═════════════════════════════════════════════════════════

/** Alert category — drives icon & color in the UI. */
enum class AlertType { COMPLETION, STALL, OFFLINE }

/** Single alert/notification entry. */
data class AlertItem(
    val id: String,
    val type: AlertType,
    val title: String,
    val body: String,
    val deviceName: String,
    val timestamp: Long, // epoch millis
    val isRead: Boolean = false,
)
