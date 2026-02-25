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

sealed class GoogleSignInResult {
    data class Success(val user: FirebaseUser) : GoogleSignInResult()
    data object Cancelled : GoogleSignInResult()
    data class Error(val message: String) : GoogleSignInResult()
}

// ═════════════════════════════════════════════════════════
// Repository — Credential Manager + Firebase Auth
// ═════════════════════════════════════════════════════════

class GoogleAuthRepository(
    private val auth: FirebaseAuth = FirebaseAuth.getInstance(),
) {

    /**
     * Launch Google Sign-In via Credential Manager.
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
}
