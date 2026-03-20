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
 * 알림 화면의 비즈니스 로직과 UI 상태를 관리하는 ViewModel입니다.
 * Firebase에서 실시간으로 알림 이벤트를 수신하고, 알림 읽음 처리 및 삭제 기능을 수행합니다.
 *
 * @property observeAlerts 특정 사용자의 알림을 구독하는 UseCase
 * @property deleteAlertUseCase 특정 알림을 삭제하는 UseCase
 * @property clearAlertsUseCase 전체 알림을 삭제하는 UseCase
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

    /**
     * 특정 사용자의 알림 데이터를 실시간으로 구독하기 시작합니다.
     *
     * @param uid 구독할 사용자의 ID
     */
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

    /**
     * 알림 데이터 구독을 중단합니다.
     */
    private fun stopObserving() {
        alertsJob?.cancel()
        alertsJob = null
    }

    /**
     * 새로운 알림을 목록에 추가하거나 기존 알림의 내용을 업데이트합니다.
     *
     * @param alert 추가 또는 업데이트할 알림 항목
     */
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
     * 특정 알림을 클라이언트 메모리에서 읽음 처리합니다.
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
     * 특정 알림을 서버(RTDB) 및 로컬 목록에서 완전히 삭제합니다.
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
     * 현재 사용자의 모든 알림을 서버에서 삭제하고 로컬 상태를 초기화합니다.
     */
    fun clearAll() {
        val currentUid = uid ?: return
        readAlertIds.clear()
        clearAlertsUseCase(currentUid)
        _alerts.value = emptyList()
    }

    /**
     * ViewModel이 소멸될 때 구독을 해제하고 인증 리스너를 제거합니다.
     */
    override fun onCleared() {
        stopObserving()
        authListener?.let { auth.removeAuthStateListener(it) }
        authListener = null
        super.onCleared()
    }
}
