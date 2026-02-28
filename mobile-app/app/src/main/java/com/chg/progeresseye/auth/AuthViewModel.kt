package com.chg.progeresseye.auth

import android.content.Context
import com.chg.progeresseye.R
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ServerValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.google.firebase.auth.FirebaseUser
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.delay
import java.util.UUID

// ═════════════════════════════════════════════════════════
// Auth UI state
// ═════════════════════════════════════════════════════════

data class AuthUiState(
    val isLoading: Boolean = false,
    val user: FirebaseUser? = null,
    val error: String? = null,
    val requiresSessionTakeover: Boolean = false,
    val existingDeviceName: String? = null,
)

// ═════════════════════════════════════════════════════════
// ViewModel — bridges UI ↔ GoogleAuthRepository
// ═════════════════════════════════════════════════════════

class AuthViewModel(
    private val repository: GoogleAuthRepository = GoogleAuthRepository(),
) : ViewModel() {
    private val db = FirebaseDatabase.getInstance()
    private var pendingUser: FirebaseUser? = null
    private var pendingUid: String? = null

    private val _uiState = MutableStateFlow(
        AuthUiState(user = repository.getCurrentUser()),
    )
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    /** True when user already has a valid Firebase session. */
    val isSignedIn: Boolean
        get() = repository.getCurrentUser() != null

    fun signInWithGoogle(context: Context, webClientId: String) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            when (val result = repository.signInWithGoogle(context, webClientId)) {
                is GoogleSignInResult.Success -> {
                    val uid = result.user.uid
                    val myDeviceId = MobileSessionManager.getOrCreateDeviceId(context)
                    val sessionRef = db.reference
                        .child("users")
                        .child(uid)
                        .child("mobileSession")

                    try {
                        val snapshot = sessionRef.get().await()
                        val existingDeviceId = snapshot.child("deviceId").getValue(String::class.java)
                        val existingDeviceName = snapshot.child("deviceName").getValue(String::class.java)

                        if (!existingDeviceId.isNullOrBlank() && existingDeviceId != myDeviceId) {
                            pendingUser = result.user
                            pendingUid = uid
                            _uiState.value = AuthUiState(
                                isLoading = false,
                                requiresSessionTakeover = true,
                                existingDeviceName = existingDeviceName,
                            )
                        } else {
                            activateMobileSession(context, uid)
                            _uiState.value = AuthUiState(user = result.user)
                        }
                    } catch (e: Exception) {
                        _uiState.value = _uiState.value.copy(
                            isLoading = false,
                        error = e.message ?: context.getString(R.string.auth_session_check_failed),
                        )
                    }
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

    fun confirmSessionTakeover(context: Context) {
        viewModelScope.launch {
            val user = pendingUser ?: repository.getCurrentUser()
            val uid = pendingUid ?: user?.uid
            if (user == null || uid == null) {
                _uiState.value = AuthUiState(error = context.getString(R.string.auth_session_takeover_failed))
                return@launch
            }

            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                activateMobileSession(context, uid)
                pendingUser = null
                pendingUid = null
                _uiState.value = AuthUiState(user = user)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    error = e.message ?: context.getString(R.string.auth_session_takeover_failed),
                )
            }
        }
    }

    fun cancelSessionTakeover(context: Context) {
        viewModelScope.launch {
            pendingUser = null
            pendingUid = null
            repository.signOut(context)
            MobileSessionManager.clearSession(context)
            _uiState.value = AuthUiState(error = context.getString(R.string.auth_session_takeover_cancelled))
        }
    }

    fun signOut(context: Context) {
        viewModelScope.launch {
            clearMobileSessionIfOwned(context)
            repository.signOut(context)
            MobileSessionManager.clearSession(context)
            pendingUser = null
            pendingUid = null
            _uiState.value = AuthUiState()
        }
    }

    fun deleteAccount(context: Context) {
        viewModelScope.launch {
            val user = repository.getCurrentUser() ?: return@launch
            val uid = user.uid
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                // 1. Send forceLogout command to all connected PCs
                db.reference.child("users").child(uid).child("commands")
                    .child("forceLogout")
                    .setValue(mapOf("ts" to ServerValue.TIMESTAMP))
                    .await()

                // 2. Wait for PC to receive the command via SSE
                delay(2000)

                // 3. Delete all user data from RTDB
                db.reference.child("users").child(uid).removeValue().await()

                // 4. Delete Firebase Auth account (may fail if re-auth required)
                try {
                    user.delete().await()
                } catch (_: Exception) {
                    // Auth deletion failed — continue with local sign-out
                }
            } catch (e: Exception) {
                // forceLogout or RTDB deletion failed — still sign out locally
            }

            // Always clear local state regardless of remote errors
            repository.signOut(context)
            MobileSessionManager.clearSession(context)
            pendingUser = null
            pendingUid = null
            _uiState.value = AuthUiState()
        }
    }

    fun forceSignOutBySessionConflict(context: Context) {
        viewModelScope.launch {
            repository.signOut(context)
            MobileSessionManager.clearSession(context)
            pendingUser = null
            pendingUid = null
            _uiState.value = AuthUiState(error = context.getString(R.string.auth_logged_out_by_other_device))
        }
    }

    fun clearError() {
        _uiState.value = _uiState.value.copy(error = null)
    }

    private suspend fun activateMobileSession(context: Context, uid: String) {
        val sessionId = UUID.randomUUID().toString()
        val deviceId = MobileSessionManager.getOrCreateDeviceId(context)
        val deviceName = MobileSessionManager.getDeviceName()
        db.reference
            .child("users")
            .child(uid)
            .child("mobileSession")
            .setValue(
                mapOf(
                    "sessionId" to sessionId,
                    "deviceId" to deviceId,
                    "deviceName" to deviceName,
                    "updatedAt" to ServerValue.TIMESTAMP,
                ),
            )
            .await()
        MobileSessionManager.saveSessionId(context, sessionId)

        // Firestore users/{uid} 문서 자동 생성/갱신 (plan 필드 보존)
        val user = repository.getCurrentUser()
        val userData = mapOf(
            "email" to (user?.email ?: ""),
            "displayName" to (user?.displayName ?: ""),
            "lastLoginAt" to System.currentTimeMillis(),
        )
        try {
            FirebaseFirestore.getInstance("progress")
                .collection("users").document(uid)
                .set(userData, SetOptions.merge())
                .await()
        } catch (e: Exception) {
            timber.log.Timber.d(e, "Firestore user doc upsert failed")
        }
    }

    private suspend fun clearMobileSessionIfOwned(context: Context) {
        val user = repository.getCurrentUser() ?: return
        val localSessionId = MobileSessionManager.getSessionId(context) ?: return
        val sessionRef = db.reference
            .child("users")
            .child(user.uid)
            .child("mobileSession")
        val snapshot = sessionRef.get().await()
        val remoteSessionId = snapshot.child("sessionId").getValue(String::class.java)
        if (remoteSessionId == localSessionId) {
            sessionRef.removeValue().await()
        }
    }
}
