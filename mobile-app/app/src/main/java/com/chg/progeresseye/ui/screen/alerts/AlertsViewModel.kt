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

    /** Mark a single alert as read. */
    fun markAsRead(alertId: String) {
        readAlertIds.add(alertId)
        _alerts.update { list ->
            list.map { if (it.id == alertId) it.copy(isRead = true) else it }
        }
    }

    /** Delete a single alert from RTDB + local list. */
    fun deleteAlert(alertId: String) {
        val currentUid = uid ?: return
        deleteAlertUseCase(currentUid, alertId)
        readAlertIds.remove(alertId)
        _alerts.update { list -> list.filter { it.id != alertId } }
    }

    /** Clear all alerts. */
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
