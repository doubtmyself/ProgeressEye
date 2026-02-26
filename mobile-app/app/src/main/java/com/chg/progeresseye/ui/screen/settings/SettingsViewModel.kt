package com.chg.progeresseye.ui.screen.settings

import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

// ═════════════════════════════════════════════════════════
// Settings UI state
// TODO: SharedPreferences / DataStore로 설정값 영속화
// ═════════════════════════════════════════════════════════

data class SettingsUiState(
    val completionAlerts: Boolean = true,
    val stallWarnings: Boolean = true,
    val offlineAlerts: Boolean = false,
)

// ═════════════════════════════════════════════════════════
// ViewModel — manages in-memory settings state
// ═════════════════════════════════════════════════════════

class SettingsViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    fun toggleCompletionAlerts() {
        _uiState.update { it.copy(completionAlerts = !it.completionAlerts) }
    }

    fun toggleStallWarnings() {
        _uiState.update { it.copy(stallWarnings = !it.stallWarnings) }
    }

    fun toggleOfflineAlerts() {
        _uiState.update { it.copy(offlineAlerts = !it.offlineAlerts) }
    }
}
