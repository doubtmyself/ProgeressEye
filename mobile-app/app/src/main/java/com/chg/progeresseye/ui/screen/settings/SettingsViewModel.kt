package com.chg.progeresseye.ui.screen.settings

import android.app.Application
import android.content.Context
import androidx.lifecycle.AndroidViewModel
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
// ViewModel — manages persisted settings state
// ═════════════════════════════════════════════════════════

class SettingsViewModel(application: Application) : AndroidViewModel(application) {

    private val prefs = application.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    private val _uiState = MutableStateFlow(
        SettingsUiState(
            completionAlerts = prefs.getBoolean(KEY_COMPLETION_ALERTS, true),
            stallWarnings = prefs.getBoolean(KEY_STALL_WARNINGS, true),
            offlineAlerts = prefs.getBoolean(KEY_OFFLINE_ALERTS, false),
        )
    )
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    fun toggleCompletionAlerts() {
        _uiState.update { current ->
            val updated = current.copy(completionAlerts = !current.completionAlerts)
            prefs.edit().putBoolean(KEY_COMPLETION_ALERTS, updated.completionAlerts).apply()
            updated
        }
    }

    fun toggleStallWarnings() {
        _uiState.update { current ->
            val updated = current.copy(stallWarnings = !current.stallWarnings)
            prefs.edit().putBoolean(KEY_STALL_WARNINGS, updated.stallWarnings).apply()
            updated
        }
    }

    fun toggleOfflineAlerts() {
        _uiState.update { current ->
            val updated = current.copy(offlineAlerts = !current.offlineAlerts)
            prefs.edit().putBoolean(KEY_OFFLINE_ALERTS, updated.offlineAlerts).apply()
            updated
        }
    }

    companion object {
        private const val PREFS_NAME = "settings"
        private const val KEY_COMPLETION_ALERTS = "completionAlerts"
        private const val KEY_STALL_WARNINGS = "stallWarnings"
        private const val KEY_OFFLINE_ALERTS = "offlineAlerts"
    }
}
