package com.chg.progeresseye.ui.screen.alerts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chg.progeresseye.domain.model.AlertItem
import com.chg.progeresseye.domain.repository.AlertEvent
import com.chg.progeresseye.domain.usecase.ClearAlertsUseCase
import com.chg.progeresseye.domain.usecase.DeleteAlertUseCase
import com.chg.progeresseye.domain.usecase.ObserveAlertsUseCase
import com.google.firebase.auth.FirebaseAuth
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

// ═════════════════════════════════════════════════════════
// AlertsViewModel — observes user alerts via AlertRepository
// ═════════════════════════════════════════════════════════

@HiltViewModel
/**
 * 알림 화면의 비즈니스 로직과 UI 상태를 관리하는 ViewModel
 *
 * Firebase에서 실시간으로 알림 이벤트를 수신하고, 알림 읽음 처리 및 삭제 기능을 수행
 *
 * @property observeAlerts 특정 사용자의 알림을 구독하는 UseCase
 * @property deleteAlertUseCase 특정 알림을 삭제하는 UseCase
 * @property clearAlertsUseCase 전체 알림을 삭제하는 UseCase
 * @constructor Create empty [AlertsViewModel]
 */
class AlertsViewModel @Inject constructor(
    private val observeAlerts: ObserveAlertsUseCase,
    private val deleteAlertUseCase: DeleteAlertUseCase,
    private val clearAlertsUseCase: ClearAlertsUseCase,
) : ViewModel() {

    private val auth = FirebaseAuth.getInstance()

    private val _alerts = MutableStateFlow<List<AlertItem>>(emptyList())
    val alerts: StateFlow<List<AlertItem>> = _alerts.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val readAlertIds = mutableSetOf<String>()  // in-memory only; resets on process death
    private var uid: String? = null
    private var alertsJob: Job? = null
    private var authListener: FirebaseAuth.AuthStateListener? = null

    init {
        authListener = FirebaseAuth.AuthStateListener { firebaseAuth ->
            val user = firebaseAuth.currentUser
            if (user != null && uid == null) {
                uid = user.uid
                startObserving(user.uid)
            } else if (user == null) {
                uid = null
                stopObserving()
                _alerts.value = emptyList()
                _isLoading.value = false
            }
        }
        auth.addAuthStateListener(authListener!!)
    }

    private fun startObserving(uid: String) {
        alertsJob?.cancel()
        alertsJob = viewModelScope.launch {
            observeAlerts(uid).collect { event ->
                when (event) {
                    is AlertEvent.Added -> upsertAlert(event.alert)
                    is AlertEvent.Changed -> upsertAlert(event.alert)
                    is AlertEvent.Removed -> {
                        readAlertIds.remove(event.alertId)
                        _alerts.update { list -> list.filter { it.id != event.alertId } }
                    }
                    is AlertEvent.InitialLoadComplete -> _isLoading.value = false
                }
            }
        }
    }

    private fun stopObserving() {
        alertsJob?.cancel()
        alertsJob = null
    }

    private fun upsertAlert(alert: AlertItem) {
        _alerts.update { list ->
            val updated = list.toMutableList()
            val index = updated.indexOfFirst { it.id == alert.id }
            val patched = if (readAlertIds.contains(alert.id)) alert.copy(isRead = true) else alert
            if (index >= 0) updated[index] = patched else updated.add(patched)
            updated.sortedByDescending { it.timestamp }
        }
    }

    /**
     * 특정 알림을 클라이언트 메모리에서 읽음 처리
     *
     * @param alertId 읽은 알림의 ID 식별자
     */
    fun markAsRead(alertId: String) {
        readAlertIds.add(alertId)
        _alerts.update { list ->
            list.map { if (it.id == alertId) it.copy(isRead = true) else it }
        }
    }

    /**
     * 특정 알림을 RTDB 및 로컬 목록에서 완전히 삭제
     *
     * @param alertId 삭제할 알림의 ID 식별자
     */
    fun deleteAlert(alertId: String) {
        val currentUid = uid ?: return
        deleteAlertUseCase(currentUid, alertId)
        readAlertIds.remove(alertId)
        _alerts.update { list -> list.filter { it.id != alertId } }
    }

    /**
     * 현재 사용자의 모든 알림을 초기화하고 삭제
     */
    fun clearAll() {
        val currentUid = uid ?: return
        readAlertIds.clear()
        clearAlertsUseCase(currentUid)
        _alerts.value = emptyList()
    }

    override fun onCleared() {
        stopObserving()
        authListener?.let { auth.removeAuthStateListener(it) }
        authListener = null
        super.onCleared()
    }
}
