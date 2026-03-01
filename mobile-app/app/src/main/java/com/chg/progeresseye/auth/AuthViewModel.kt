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
    val requiresWithdrawalCancel: Boolean = false,
    val withdrawalGraceEndDate: String? = null,
)

// ═════════════════════════════════════════════════════════
// ViewModel — bridges UI ↔ GoogleAuthRepository
// ═════════════════════════════════════════════════════════

class AuthViewModel(
    private val repository: GoogleAuthRepository = GoogleAuthRepository(),
) : ViewModel() {
    private val db = FirebaseDatabase.getInstance()
    private val firestore = FirebaseFirestore.getInstance("progress")
    private var pendingUser: FirebaseUser? = null
    private var pendingUid: String? = null
    private var pendingWithdrawalUser: FirebaseUser? = null
    private var pendingWithdrawalUid: String? = null

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
                    val now = System.currentTimeMillis()
                    val withdrawalState = getWithdrawalState(uid)
                    val deleteAt = withdrawalState.deleteAt
                    val rejoinAllowedAt = withdrawalState.rejoinAllowedAt
                    if (withdrawalState.pending && deleteAt > now) {
                        pendingWithdrawalUser = result.user
                        pendingWithdrawalUid = uid
                        val dateText = java.text.SimpleDateFormat(
                            "yyyy-MM-dd",
                            java.util.Locale.getDefault(),
                        ).format(java.util.Date(deleteAt))
                        _uiState.value = AuthUiState(
                            isLoading = false,
                            requiresWithdrawalCancel = true,
                            withdrawalGraceEndDate = dateText,
                        )
                        return@launch
                    }
                    if (rejoinAllowedAt > now) {
                        repository.signOut(context)
                        MobileSessionManager.clearSession(context)
                        val dateText = java.text.SimpleDateFormat(
                            "yyyy-MM-dd",
                            java.util.Locale.getDefault(),
                        ).format(java.util.Date(rejoinAllowedAt))
                        _uiState.value = AuthUiState(
                            isLoading = false,
                            error = context.getString(
                                R.string.auth_withdrawal_rejoin_blocked,
                                dateText,
                            ),
                        )
                        return@launch
                    }
                    proceedSessionCheck(context, result.user, uid)
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
            pendingWithdrawalUser = null
            pendingWithdrawalUid = null
            _uiState.value = AuthUiState()
        }
    }

    fun confirmWithdrawalCancellation(context: Context) {
        viewModelScope.launch {
            val user = pendingWithdrawalUser ?: repository.getCurrentUser()
            val uid = pendingWithdrawalUid ?: user?.uid
            if (user == null || uid == null) {
                _uiState.value = AuthUiState(error = context.getString(R.string.auth_session_check_failed))
                return@launch
            }

            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                cancelWithdrawal(uid)
                pendingWithdrawalUser = null
                pendingWithdrawalUid = null
                proceedSessionCheck(context, user, uid)
            } catch (e: Exception) {
                repository.signOut(context)
                MobileSessionManager.clearSession(context)
                pendingWithdrawalUser = null
                pendingWithdrawalUid = null
                _uiState.value = AuthUiState(
                    isLoading = false,
                    error = context.getString(R.string.auth_withdrawal_cancel_failed, e.message ?: "unknown"),
                )
            }
        }
    }

    fun keepWithdrawalAndCancelLogin(context: Context) {
        viewModelScope.launch {
            val uid = pendingWithdrawalUid
            repository.signOut(context)
            MobileSessionManager.clearSession(context)
            pendingWithdrawalUser = null
            pendingWithdrawalUid = null

            val blockUntil = if (uid.isNullOrBlank()) 0L else getWithdrawalState(uid).rejoinAllowedAt
            val dateText = java.text.SimpleDateFormat(
                "yyyy-MM-dd",
                java.util.Locale.getDefault(),
            ).format(java.util.Date(blockUntil.takeIf { it > 0 } ?: System.currentTimeMillis()))
            _uiState.value = AuthUiState(
                isLoading = false,
                error = context.getString(R.string.auth_withdrawal_rejoin_blocked, dateText),
            )
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
                    .setValue(mapOf("ts" to (System.currentTimeMillis() / 1000), "cmdId" to java.util.UUID.randomUUID().toString()))
                    .await()

                // 2. Wait for PC to receive the command via SSE
                delay(2000)

                val now = System.currentTimeMillis()
                val deleteAt = now + 7L * 24 * 60 * 60 * 1000
                val rejoinAllowedAt = now + 30L * 24 * 60 * 60 * 1000

                // 3. Mark withdrawal policy in Firestore users/{uid}
                firestore.collection("users").document(uid)
                    .set(
                        mapOf(
                            "withdrawalStatus" to "pending",
                            "withdrawalRequestedAt" to now,
                            "deleteAt" to deleteAt,
                            "rejoinAllowedAt" to rejoinAllowedAt,
                            "updatedAt" to now,
                        ),
                        SetOptions.merge(),
                    )
                    .await()

                // 4. Keep tombstone for rejoin restriction (even after data purge)
                firestore.collection("withdrawnUsers").document(uid)
                    .set(
                        mapOf(
                            "uid" to uid,
                            "status" to "pending",
                            "requestedAt" to now,
                            "deleteAt" to deleteAt,
                            "rejoinAllowedAt" to rejoinAllowedAt,
                        ),
                        SetOptions.merge(),
                    )
                    .await()

            } catch (e: Exception) {
                // withdrawal mark failed — still sign out locally
            }

            // Always clear local state regardless of remote errors
            repository.signOut(context)
            MobileSessionManager.clearSession(context)
            pendingUser = null
            pendingUid = null
            _uiState.value = AuthUiState(error = context.getString(R.string.settings_delete_account_requested))
        }
    }

    private data class WithdrawalState(
        val pending: Boolean,
        val deleteAt: Long,
        val rejoinAllowedAt: Long,
    )

    private suspend fun getWithdrawalState(uid: String): WithdrawalState {
        var pending = false
        var deleteAt = 0L
        var rejoinAllowedAt = 0L
        try {
            val tomb = firestore.collection("withdrawnUsers").document(uid).get().await()
            val status = tomb.getString("status")
            if (status == "pending") {
                pending = true
            }
            val delete = tomb.getLong("deleteAt")
            if (delete != null) {
                deleteAt = maxOf(deleteAt, delete)
            }
            val rejoin = tomb.getLong("rejoinAllowedAt")
            if (rejoin != null) {
                rejoinAllowedAt = maxOf(rejoinAllowedAt, rejoin)
            }
        } catch (_: Exception) {
        }
        try {
            val userDoc = firestore.collection("users").document(uid).get().await()
            val status = userDoc.getString("withdrawalStatus")
            if (status == "pending") {
                pending = true
            }
            val delete = userDoc.getLong("deleteAt")
            if (delete != null) {
                deleteAt = maxOf(deleteAt, delete)
            }
            val rejoin = userDoc.getLong("rejoinAllowedAt")
            if (rejoin != null) {
                rejoinAllowedAt = maxOf(rejoinAllowedAt, rejoin)
            }
        } catch (_: Exception) {
        }
        return WithdrawalState(
            pending = pending,
            deleteAt = deleteAt,
            rejoinAllowedAt = rejoinAllowedAt,
        )
    }

    private suspend fun cancelWithdrawal(uid: String) {
        val now = System.currentTimeMillis()
        firestore.collection("users").document(uid)
            .set(
                mapOf(
                    "withdrawalStatus" to "active",
                    "withdrawalRequestedAt" to null,
                    "deleteAt" to null,
                    "rejoinAllowedAt" to null,
                    "updatedAt" to now,
                ),
                SetOptions.merge(),
            )
            .await()
        firestore.collection("withdrawnUsers").document(uid).delete().await()
    }

    private suspend fun proceedSessionCheck(context: Context, user: FirebaseUser, uid: String) {
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
                pendingUser = user
                pendingUid = uid
                _uiState.value = AuthUiState(
                    isLoading = false,
                    requiresSessionTakeover = true,
                    existingDeviceName = existingDeviceName,
                )
            } else {
                activateMobileSession(context, uid)
                _uiState.value = AuthUiState(user = user)
            }
        } catch (e: Exception) {
            _uiState.value = AuthUiState(
                isLoading = false,
                error = e.message ?: context.getString(R.string.auth_session_check_failed),
            )
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

    fun forceSignOutByWithdrawal(context: Context) {
        viewModelScope.launch {
            repository.signOut(context)
            MobileSessionManager.clearSession(context)
            pendingUser = null
            pendingUid = null
            pendingWithdrawalUser = null
            pendingWithdrawalUid = null
            _uiState.value = AuthUiState(error = context.getString(R.string.auth_logged_out_by_withdrawal))
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
