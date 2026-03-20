package com.chg.progeresseye.auth

import android.content.Context
import androidx.credentials.ClearCredentialStateRequest
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.NoCredentialException
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential.Companion.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.FirebaseUser
import com.google.firebase.auth.GoogleAuthProvider
import kotlinx.coroutines.tasks.await

// ═════════════════════════════════════════════════════════
// Google Sign-In result — sealed hierarchy
// ═════════════════════════════════════════════════════════

/**
 * 구글 로그인 시도의 결과를 나타내는 클래스 계층구조
 */
sealed class GoogleSignInResult {
    /**
     * 로그인 성공 상태
     * @property user 성공적으로 인증된 Firebase 사용자 객체
     */
    data class Success(val user: FirebaseUser) : GoogleSignInResult()

    /**
     * 사용자에 의해 로그인이 취소된 상태
     */
    data object Cancelled : GoogleSignInResult()

    /**
     * 로그인 중 에러가 발생한 상태
     * @property message 에러 상세 메시지
     */
    data class Error(val message: String) : GoogleSignInResult()
}

// ═════════════════════════════════════════════════════════
// Repository — Credential Manager + Firebase Auth
// ═════════════════════════════════════════════════════════

/**
 * Google Credential Manager 및 Firebase Auth를 이용한 인증 로직을 제공하는 Repository
 *
 * @property auth FirebaseAuth 인스턴스 (기본값은 getInstance())
 */
class GoogleAuthRepository(
    private val auth: FirebaseAuth = FirebaseAuth.getInstance(),
) {

    /**
     * Credential Manager를 통해 Google 로그인을 시도하고 Firebase 인증을 수행합니다.
     * 브랜드화된 Google 계정 선택기를 표시합니다 (명시적인 "로그인" 버튼 클릭 시 적합).
     *
     * @param context Activity 컨텍스트 (Credential Manager가 하단 시트를 표시하기 위해 필요함)
     * @param webClientId google-services.json에서 획득한 웹 클라이언트 ID
     * @return [GoogleSignInResult] 형태의 로그인 결과
     */
    suspend fun signInWithGoogle(
        context: Context,
        webClientId: String,
    ): GoogleSignInResult {
        val credentialManager = CredentialManager.create(context)

        val signInOption = GetSignInWithGoogleOption.Builder(webClientId)
            .build()

        val request = GetCredentialRequest.Builder()
            .addCredentialOption(signInOption)
            .build()

        return try {
            val response = credentialManager.getCredential(
                context = context,
                request = request,
            )

            val credential = response.credential
            if (credential is CustomCredential &&
                credential.type == TYPE_GOOGLE_ID_TOKEN_CREDENTIAL
            ) {
                val googleIdToken = GoogleIdTokenCredential.createFrom(credential.data)
                val firebaseCredential =
                    GoogleAuthProvider.getCredential(googleIdToken.idToken, null)
                val result = auth.signInWithCredential(firebaseCredential).await()

                val user = result.user
                    ?: return GoogleSignInResult.Error("Firebase sign-in returned null user")
                GoogleSignInResult.Success(user)
            } else {
                GoogleSignInResult.Error("Unexpected credential type: ${credential.type}")
            }
        } catch (_: GetCredentialCancellationException) {
            GoogleSignInResult.Cancelled
        } catch (_: NoCredentialException) {
            GoogleSignInResult.Error("No Google account available on this device")
        } catch (e: GetCredentialException) {
            GoogleSignInResult.Error(e.message ?: "Credential Manager error")
        } catch (e: Exception) {
            GoogleSignInResult.Error(e.message ?: "Unknown error")
        }
    }

    /**
     * Firebase에서 로그아웃하고 Credential Manager의 상태를 정리합니다.
     * 다음 로그인 시 계정이 자동 선택되는 것을 방지합니다.
     *
     * @param context Credential Manager 접근을 위한 컨텍스트
     */
    suspend fun signOut(context: Context) {
        auth.signOut()
        try {
            val credentialManager = CredentialManager.create(context)
            credentialManager.clearCredentialState(ClearCredentialStateRequest())
        } catch (_: Exception) {
            // Best-effort — sign-out from Firebase already succeeded
        }
    }

    /**
     * 현재 로그인된 Firebase 사용자를 반환합니다.
     *
     * @return 현재 사용자 객체, 로그인되어 있지 않으면 null
     */
    fun getCurrentUser(): FirebaseUser? = auth.currentUser

    /**
     * Credential Manager 정리 없이 Firebase만 즉시 로그아웃합니다 (초기화 체크용).
     */
    fun signOutFirebaseOnly() {
        auth.signOut()
    }
}
