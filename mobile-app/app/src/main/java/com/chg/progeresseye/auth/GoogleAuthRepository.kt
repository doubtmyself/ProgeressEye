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
    data class Success(val user: FirebaseUser) : GoogleSignInResult()
    data object Cancelled : GoogleSignInResult()
    data class Error(val message: String) : GoogleSignInResult()
}

// ═════════════════════════════════════════════════════════
// Repository — Credential Manager + Firebase Auth
// ═════════════════════════════════════════════════════════

/**
 * Google Credential Manager 및 Firebase Auth를 이용한 인증 로직을 제공하는 Repository
 *
 * @param auth FirebaseAuth 인스턴스
 * @constructor Create empty [GoogleAuthRepository]
 */
class GoogleAuthRepository(
    private val auth: FirebaseAuth = FirebaseAuth.getInstance(),
) {

    /**
     * Credential Manager를 통해 Google 로그인을 시도하고 Firebase 인증을 수행
     *
     * @param context 로그인 화면을 띄울 Activity 컨텍스트
     * @param webClientId Google Cloud API 웹 클라이언트 ID
     * @return [GoogleSignInResult] 형태의 로그인 결과

     *
     * Uses [GetSignInWithGoogleOption] which shows the full branded
     * Google account picker — appropriate for explicit "Sign in" button taps.
     *
     * @param context **Must** be an Activity context. Credential Manager
     *                needs an Activity to display the bottom sheet.
     * @param webClientId The Web client ID from google-services.json
     *                    (auto-generated as R.string.default_web_client_id).
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
     * Sign out from both Firebase and clear Credential Manager state
     * so the bottom sheet won't auto-select the old account.
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

    fun getCurrentUser(): FirebaseUser? = auth.currentUser

    /** Credential Manager 정리 없이 Firebase만 즉시 로그아웃 (init 체크용) */
    fun signOutFirebaseOnly() {
        auth.signOut()
    }
}
