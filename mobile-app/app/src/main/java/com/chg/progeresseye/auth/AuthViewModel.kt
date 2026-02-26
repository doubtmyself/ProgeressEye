package com.chg.progeresseye.auth

import android.content.Context
import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.chg.progeresseye.fcm.ProgressEyeMessagingService
import com.google.firebase.auth.FirebaseUser
import com.google.firebase.messaging.FirebaseMessaging
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

// ═════════════════════════════════════════════════════════
// Auth UI state
// ═════════════════════════════════════════════════════════

data class AuthUiState(
    val isLoading: Boolean = false,
    val user: FirebaseUser? = null,
    val error: String? = null,
)

// ═════════════════════════════════════════════════════════
// ViewModel — bridges UI ↔ GoogleAuthRepository
// ═════════════════════════════════════════════════════════

class AuthViewModel(
    private val repository: GoogleAuthRepository = GoogleAuthRepository(),
) : ViewModel() {

    private val _uiState = MutableStateFlow(
        AuthUiState(user = repository.getCurrentUser()),
    )
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    /** True when user already has a valid Firebase session. */
    val isSignedIn: Boolean
        get() = repository.getCurrentUser() != null

    init {
        // 이미 로그인 상태라면 FCM 토큰을 등록
        if (isSignedIn) {
            registerFcmToken()
        }
    }

    fun signInWithGoogle(context: Context, webClientId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            when (val result = repository.signInWithGoogle(context, webClientId)) {
                is GoogleSignInResult.Success -> {
                    _uiState.value = AuthUiState(user = result.user)
                    registerFcmToken()
                }

                is GoogleSignInResult.Cancelled -> {
                    _uiState.value = _uiState.value.copy(isLoading = false)
                }

                is GoogleSignInResult.Error -> {
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = result.message,
                    )
                }
            }
        }
    }

    fun signOut(context: Context) {
        viewModelScope.launch {
            unregisterFcmToken()
            repository.signOut(context)
            _uiState.value = AuthUiState()
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    // ── FCM token management ───────────────────────────────

    private fun registerFcmToken() {
        FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
            ProgressEyeMessagingService.registerToken(token)
        }.addOnFailureListener { e ->
            Log.e(TAG, "Failed to get FCM token", e)
        }
    }

    private fun unregisterFcmToken() {
        FirebaseMessaging.getInstance().token.addOnSuccessListener { token ->
            ProgressEyeMessagingService.unregisterToken(token)
        }
    }

    companion object {
        private const val TAG = "AuthViewModel"
    }
}
