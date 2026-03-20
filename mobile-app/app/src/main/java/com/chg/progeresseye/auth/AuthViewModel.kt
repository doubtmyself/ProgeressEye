package com.chg.progeresseye.auth

import android.app.Application
import android.content.Context
import com.chg.progeresseye.BuildConfig
import com.chg.progeresseye.R
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.google.firebase.auth.FirebaseUser
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.tasks.await
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject
import timber.log.Timber
import com.chg.progeresseye.domain.usecase.GetWithdrawalStateUseCase
import com.chg.progeresseye.domain.usecase.CallWithdrawalApiUseCase
import com.chg.progeresseye.domain.usecase.CheckExistingSessionUseCase
import com.chg.progeresseye.domain.usecase.ActivateMobileSessionUseCase
import com.chg.progeresseye.domain.usecase.ClearSessionIfOwnedUseCase
import com.chg.progeresseye.domain.usecase.UpdateUserDocumentUseCase

/**
 * 인증 및 세션 제어와 관련된 UI 상태 데이터를 보관하는 데이터 클래스
 */
data class AuthUiState(
    val isLoading: Boolean = false,
    val user: FirebaseUser? = null,
    val error: String? = null,
    val requiresSessionTakeover: Boolean = false,
    val existingDeviceName: String? = null,
    val requiresWithdrawalCancel: Boolean = false,
    val withdrawalGraceEndDate: String? = null,
)

@HiltViewModel
/**
 * 인증 화면 및 세션 유지 로직을 관리하는 ViewModel
 */
class AuthViewModel @Inject constructor(
    application: Application,
    private val getWithdrawalStateUseCase: GetWithdrawalStateUseCase,
    private val callWithdrawalApiUseCase: CallWithdrawalApiUseCase,
    private val checkExistingSessionUseCase: CheckExistingSessionUseCase,
    private val activateMobileSessionUseCase: ActivateMobileSessionUseCase,
    private val clearSessionIfOwnedUseCase: ClearSessionIfOwnedUseCase,
    private val updateUserDocumentUseCase: UpdateUserDocumentUseCase
) : AndroidViewModel(application) {
    
    private val repository = GoogleAuthRepository()
    private var pendingUser: FirebaseUser? = null
    private var pendingUid: String? = null
    private var pendingWithdrawalUser: FirebaseUser? = null
    private var pendingWithdrawalUid: String? = null

    private val _uiState: MutableStateFlow<AuthUiState>
    val uiState: StateFlow<AuthUiState>

    init {
        val firebaseUser = repository.getCurrentUser()
        val hasSession = MobileSessionManager.getSessionId(application) != null
        if (firebaseUser != null && !hasSession) {
            repository.signOutFirebaseOnly()
            MobileSessionManager.clearSession(application)
            _uiState = MutableStateFlow(AuthUiState())
        } else {
            _uiState = MutableStateFlow(AuthUiState(user = firebaseUser))
        }
        uiState = _uiState.asStateFlow()
    }

    val isSignedIn: Boolean
        get() = repository.getCurrentUser() != null

    fun signInWithGoogle(context: Context, webClientId: String) {
        viewModelScope.launch {
            Timber.d("[Auth] signInWithGoogle: 시작")
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            val signInResult = try {
                withTimeout(20000L) {
                    repository.signInWithGoogle(context, webClientId)
                }
            } catch (_: TimeoutCancellationException) {
                Timber.w("[Auth] signInWithGoogle: Google 로그인 타임아웃(20s)")
                GoogleSignInResult.Error(context.getString(R.string.auth_sign_in_timeout))
            }

            when (val result = signInResult) {
                is GoogleSignInResult.Success -> {
                    val uid = result.user.uid
                    Timber.d("[Auth] Google 로그인 성공: uid=$uid")
                    val now = System.currentTimeMillis()
                    Timber.d("[Auth] getWithdrawalStateUseCase 호출 중...")
                    val withdrawalState = getWithdrawalStateUseCase(uid, result.user.email)
                    Timber.d("[Auth] getWithdrawalStateUseCase 완료: pending=${withdrawalState.pending}")
                    val deleteAt = withdrawalState.deleteAt
                    val rejoinAllowedAt = withdrawalState.rejoinAllowedAt
                    if (withdrawalState.pending && deleteAt > now) {
                        pendingWithdrawalUser = result.user
                        pendingWithdrawalUid = uid
                        _uiState.value = AuthUiState(
                            isLoading = false,
                            requiresWithdrawalCancel = true,
                            withdrawalGraceEndDate = deleteAt.toYmdString(),
                        )
                        return@launch
                    }
                    if (rejoinAllowedAt > now) {
                        repository.signOut(context)
                        MobileSessionManager.clearSession(context)
                        _uiState.value = AuthUiState(
                            isLoading = false,
                            error = context.getString(
                                R.string.auth_withdrawal_rejoin_blocked,
                                rejoinAllowedAt.toYmdString(),
                            ),
                        )
                        return@launch
                    }
                    proceedSessionCheck(context, result.user, uid)
                }
                is GoogleSignInResult.Cancelled -> {
                    Timber.d("[Auth] Google 로그인 취소됨")
                    _uiState.value = _uiState.value.copy(
                        isLoading = false,
                        error = if (BuildConfig.DEBUG) {
                            context.getString(R.string.auth_session_takeover_cancelled)
                        } else {
                            context.getString(R.string.auth_google_sign_in_release_hint)
                        },
                    )
                }
                is GoogleSignInResult.Error -> {
                    Timber.w("[Auth] Google 로그인 에러: ${result.message}")
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
            if (user == null) {
                _uiState.value = AuthUiState(error = context.getString(R.string.auth_session_takeover_failed))
                return@launch
            }
            val uid = pendingUid ?: user.uid

            _uiState.value = _uiState.value.copy(isLoading = true, error = null)
            try {
                doActivateSession(context, uid)
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
            Timber.d("[Auth] signOut: 시작")
            clearMobileSessionIfOwnedUseCase(context)
            repository.signOut(context)
            MobileSessionManager.clearSession(context)
            pendingUser = null
            pendingUid = null
            pendingWithdrawalUser = null
            pendingWithdrawalUid = null
            _uiState.value = AuthUiState()
            Timber.d("[Auth] signOut: 완료")
        }
    }

    private suspend fun clearMobileSessionIfOwnedUseCase(context: Context) {
        val user = repository.getCurrentUser() ?: return
        val localSessionId = MobileSessionManager.getSessionId(context) ?: return
        try { clearSessionIfOwnedUseCase(user.uid, localSessionId) } catch (e: Exception) { }
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
                callWithdrawalApi("cancelWithdrawal", user.email, user)
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

            val blockUntil = if (uid.isNullOrBlank()) 0L else getWithdrawalStateUseCase(uid, email).rejoinAllowedAt
            val blockDate = (blockUntil.takeIf { it > 0 } ?: System.currentTimeMillis()).toYmdString()
            _uiState.value = AuthUiState(
                isLoading = false,
                error = context.getString(R.string.auth_withdrawal_rejoin_blocked, blockDate),
            )
        }
    }

    fun deleteAccount(context: Context) {
        viewModelScope.launch {
            val user = repository.getCurrentUser() ?: return@launch
            _uiState.value = _uiState.value.copy(isLoading = true, error = null)

            Timber.d("[Auth] deleteAccount: requestWithdrawal API 호출 중...")
            try {
                callWithdrawalApi("requestWithdrawal", user.email, user)
                Timber.d("[Auth] deleteAccount: requestWithdrawal API 성공")
            } catch (e: Exception) {
                Timber.e(e, "[Auth] deleteAccount: requestWithdrawal API 실패")
            }

            repository.signOut(context)
            MobileSessionManager.clearSession(context)
            pendingUser = null
            pendingUid = null
            _uiState.value = AuthUiState(error = context.getString(R.string.settings_delete_account_requested))
        }
    }

    private suspend fun callWithdrawalApi(action: String, email: String?, user: FirebaseUser) {
        val idTokenResult = user.getIdToken(true).await()
        val idToken = idTokenResult.token ?: throw IllegalStateException("idToken unavailable")
        callWithdrawalApiUseCase(action, email, idToken)
    }

    private fun Long.toYmdString(): String =
        java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.getDefault())
            .format(java.util.Date(this))

    private suspend fun proceedSessionCheck(context: Context, user: FirebaseUser, uid: String) {
        val myDeviceId = MobileSessionManager.getOrCreateDeviceId(context)
        Timber.d("[Auth] proceedSessionCheck: 시작 (uid=$uid, deviceId=$myDeviceId)")

        try {
            Timber.d("[Auth] checkExistingSessionUseCase 호출 중...")
            val existingDeviceName = checkExistingSessionUseCase(uid, myDeviceId)
            Timber.d("[Auth] checkExistingSessionUseCase 완료: existingDevice=$existingDeviceName")
            if (existingDeviceName != null) {
                Timber.d("[Auth] 세션 충돌 감지 → 세션 인수 UI 표시")
                MobileSessionManager.clearSession(context)
                pendingUser = user
                pendingUid = uid
                _uiState.value = AuthUiState(
                    isLoading = false,
                    requiresSessionTakeover = true,
                    existingDeviceName = existingDeviceName,
                )
            } else {
                Timber.d("[Auth] 기존 세션 없음 → doActivateSession 호출 중...")
                doActivateSession(context, uid)
                Timber.d("[Auth] doActivateSession 완료 → 로그인 성공")
                _uiState.value = AuthUiState(user = user)
            }
        } catch (e: Exception) {
            Timber.e(e, "[Auth] proceedSessionCheck 예외 발생")
            _uiState.value = AuthUiState(
                isLoading = false,
                error = e.message ?: context.getString(R.string.auth_session_check_failed),
            )
        }
    }
    
    private suspend fun doActivateSession(context: Context, uid: String) {
       val deviceId = MobileSessionManager.getOrCreateDeviceId(context)
       val deviceName = MobileSessionManager.getDeviceName()
       val sessionId = java.util.UUID.randomUUID().toString()
       Timber.d("[Auth] doActivateSession: deviceId=$deviceId, deviceName=$deviceName, sessionId=$sessionId")

       Timber.d("[Auth] activateMobileSessionUseCase 호출 중...")
       activateMobileSessionUseCase(uid, deviceId, deviceName, sessionId)
       Timber.d("[Auth] activateMobileSessionUseCase 완료 → 세션 저장 중...")
       MobileSessionManager.saveSessionId(context, sessionId)
       Timber.d("[Auth] 세션 저장 완료")

       val user = repository.getCurrentUser()
       // Also updates firestore users collection in the background
       try { updateUserDocumentUseCase(uid, user?.email ?: "", user?.displayName ?: "") } catch (_: Exception) {}
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
}
