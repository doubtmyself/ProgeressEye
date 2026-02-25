package com.chg.progeresseye.ui.screen.alerts

import androidx.lifecycle.ViewModel
import com.chg.progeresseye.data.model.AlertItem
import com.chg.progeresseye.data.model.AlertType
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

// ═════════════════════════════════════════════════════════
// AlertsViewModel — in-memory alert list
// TODO: Replace with FCM + local Room DB storage
// ═════════════════════════════════════════════════════════

class AlertsViewModel : ViewModel() {

    private val _alerts = MutableStateFlow(
        if (USE_MOCK_DATA) mockAlerts() else emptyList()
    )
    val alerts: StateFlow<List<AlertItem>> = _alerts.asStateFlow()

    /** Mark a single alert as read. */
    fun markAsRead(alertId: String) {
        _alerts.update { list ->
            list.map { if (it.id == alertId) it.copy(isRead = true) else it }
        }
    }

    /** Clear all alerts. */
    fun clearAll() {
        _alerts.update { emptyList() }
    }

    companion object {
        /** Flip to `false` to start with an empty list. */
        const val USE_MOCK_DATA = true

        // TODO: Replace with FCM + local Room DB storage
        private fun mockAlerts(): List<AlertItem> {
            val now = System.currentTimeMillis()
            return listOf(
                AlertItem(
                    id = "alert_1",
                    type = AlertType.COMPLETION,
                    title = "Rendering Complete",
                    body = "Premiere Pro rendering finished — 100 %.",
                    deviceName = "DESKTOP-ABC",
                    timestamp = now - 12 * 60_000,  // 12 min ago
                    isRead = false,
                ),
                AlertItem(
                    id = "alert_2",
                    type = AlertType.STALL,
                    title = "Download Stalled",
                    body = "File download on WORKSTATION-2 hasn't progressed in 15 min.",
                    deviceName = "WORKSTATION-2",
                    timestamp = now - 3 * 3_600_000, // 3 hours ago
                    isRead = false,
                ),
                AlertItem(
                    id = "alert_3",
                    type = AlertType.OFFLINE,
                    title = "Device Offline",
                    body = "LAPTOP-HOME lost connection.",
                    deviceName = "LAPTOP-HOME",
                    timestamp = now - 26 * 3_600_000, // yesterday
                    isRead = true,
                ),
            )
        }
    }
}
