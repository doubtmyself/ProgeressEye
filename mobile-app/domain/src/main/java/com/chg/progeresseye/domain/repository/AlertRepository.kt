package com.chg.progeresseye.domain.repository

import com.chg.progeresseye.domain.model.AlertItem
import kotlinx.coroutines.flow.Flow

/**
 * 실시간 알림 데이터의 상태 변화 이벤트를 정의하는 Sealed Interface
 */
sealed interface AlertEvent {
    data class Added(val alert: AlertItem) : AlertEvent
    data class Changed(val alert: AlertItem) : AlertEvent
    data class Removed(val alertId: String) : AlertEvent
    data object InitialLoadComplete : AlertEvent
}

/**
 * 알림 데이터 처리를 위한 도메인 계층의 레포지토리 인터페이스
 */
interface AlertRepository {
    fun observeAlerts(uid: String): Flow<AlertEvent>
    fun deleteAlert(uid: String, alertId: String)
    fun clearAlerts(uid: String)
}
