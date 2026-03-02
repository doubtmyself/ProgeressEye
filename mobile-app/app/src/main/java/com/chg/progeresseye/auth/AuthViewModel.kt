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
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.UUID
import java.security.MessageDigest
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

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
    private companion object {
        private const val FUNCTIONS_BASE_URL = "https://us-central1-progresseye-49244.cloudfunctions.net"
    }

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

            val signInResult = try {
                withTimeout(20000L) {
                    repository.signInWithGoogle(context, webClientId)
                }
            } catch (_: TimeoutCancellationException) {
                GoogleSignInResult.Error(context.getString(R.string.auth_sign_in_timeout))
            }

            when (val result = signInResult) {
                is GoogleSignInResult.Success -> {
                    val uid = result.user.uid
                    val now = System.currentTimeMillis()
                    val withdrawalState = getWithdrawalState(uid, result.user.email)
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
                cancelWithdrawal(user.email)
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
            val email = pendingWithdrawalUser?.email
            repository.signOut(context)
            MobileSessionManager.clearSession(context)
            pendingWithdrawalUser = null
            pendingWithdrawalUid = null

            val blockUntil = if (uid.isNullOrBlank()) 0L else getWithdrawalState(uid, email).rejoinAllowedAt
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
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            try {
                callWithdrawalApi(action = "requestWithdrawal", email = user.email)

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

    private suspend fun getWithdrawalState(uid: String, email: String?): WithdrawalState {
        var pending = false
        var deleteAt = 0L
        var rejoinAllowedAt = 0L
        try {
            val tomb = firestore.collection("withdrawnUsers").document(uid).get().await()
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
        val emailKey = emailKey(email)
        if (emailKey.isNotBlank()) {
            try {
                val emailDoc = firestore.collection("withdrawnEmails").document(emailKey).get().await()
                val rejoin = emailDoc.getLong("rejoinAllowedAt")
                if (rejoin != null) {
                    rejoinAllowedAt = maxOf(rejoinAllowedAt, rejoin)
                }
            } catch (_: Exception) {
            }
        }
        return WithdrawalState(
            pending = pending,
            deleteAt = deleteAt,
            rejoinAllowedAt = rejoinAllowedAt,
        )
    }

    private suspend fun cancelWithdrawal(email: String?) {
        callWithdrawalApi(action = "cancelWithdrawal", email = email)
    }

    private suspend fun callWithdrawalApi(action: String, email: String?) {
        val user = repository.getCurrentUser() ?: throw IllegalStateException("Not signed in")
        val idToken = user.getIdToken(true).await().token ?: throw IllegalStateException("idToken unavailable")
        val url = URL("$FUNCTIONS_BASE_URL/$action")

        withContext(Dispatchers.IO) {
            val conn = (url.openConnection() as HttpURLConnection)
            try {
                conn.requestMethod = "POST"
                conn.connectTimeout = 10000
                conn.readTimeout = 10000
                conn.doOutput = true
                conn.setRequestProperty("Authorization", "Bearer $idToken")
                conn.setRequestProperty("Content-Type", "application/json")

                val payload = JSONObject()
                    .put("email", email?.trim()?.lowercase().orEmpty())
                    .toString()

                conn.outputStream.use { output ->
                    output.write(payload.toByteArray(Charsets.UTF_8))
                }

                val code = conn.responseCode
                if (code !in 200..299) {
                    val errorText = conn.errorStream?.bufferedReader()?.use { it.readText() }
                        ?: "HTTP $code"
                    throw IllegalStateException("$action failed: $code $errorText")
                }
            } finally {
                conn.disconnect()
            }
        }
    }

    private fun emailKey(email: String?): String {
        val normalized = email?.trim()?.lowercase().orEmpty()
        if (normalized.isBlank()) return ""
        val digest = MessageDigest.getInstance("SHA-256").digest(normalized.toByteArray())
        return digest.joinToString("") { "%02x".format(it) }
    }

    private suspend fun proceedSessionCheck(context: Context, user: FirebaseUser, uid: String) {
        val myDeviceId = MobileSessionManager.getOrCreateDeviceId(context)
        val sessionRef = db.reference
            .child("users")
            .child(uid)
            .child("mobileSession")

        try {
            val snapshot = withTimeout(10000L) { sessionRef.get().await() }
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
