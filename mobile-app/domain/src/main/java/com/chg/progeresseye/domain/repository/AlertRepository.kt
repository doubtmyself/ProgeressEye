package com.chg.progeresseye.domain.repository

import com.chg.progeresseye.domain.model.AlertItem
import kotlinx.coroutines.flow.Flow

sealed interface AlertEvent {
    data class Added(val alert: AlertItem) : AlertEvent
    data class Changed(val alert: AlertItem) : AlertEvent
    data class Removed(val alertId: String) : AlertEvent
    data object InitialLoadComplete : AlertEvent
}

interface AlertRepository {
    fun observeAlerts(uid: String): Flow<AlertEvent>
    fun deleteAlert(uid: String, alertId: String)
    fun clearAlerts(uid: String)
}
