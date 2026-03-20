package com.chg.progeresseye.data.repository

import com.chg.progeresseye.data.util.FirebaseConstants
import com.chg.progeresseye.data.util.FirebaseRefs
import com.chg.progeresseye.domain.repository.AuthRepository
import com.chg.progeresseye.domain.repository.WithdrawalState
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.database.ServerValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import kotlinx.coroutines.Dispatchers
import timber.log.Timber
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import javax.inject.Inject

/**
 * Firebase 인증 및 세션 데이터 관리를 수행하는 저장소 구현체
 */
class AuthRepositoryImpl @Inject constructor() : AuthRepository {

    private val firestore = FirebaseFirestore.getInstance(FirebaseConstants.FIRESTORE_DB)

    override suspend fun activateMobileSession(uid: String, deviceId: String, deviceName: String, sessionId: String) {
        FirebaseRefs.mobileSessionRef(uid).setValue(
            mapOf(
                "sessionId" to sessionId,
                "deviceId" to deviceId,
                "deviceName" to deviceName,
                "updatedAt" to ServerValue.TIMESTAMP
            )
        ).await()
    }

    override suspend fun checkExistingSession(uid: String, deviceId: String): String? {
        val snapshot = FirebaseRefs.mobileSessionRef(uid).get().await()
        val existingDeviceId = snapshot.child("deviceId").getValue(String::class.java)
        val existingDeviceName = snapshot.child("deviceName").getValue(String::class.java)
        return if (!existingDeviceId.isNullOrBlank() && existingDeviceId != deviceId) {
            existingDeviceName ?: "다른 기기"
        } else {
            null
        }
    }

    override suspend fun clearSessionIfOwned(uid: String, localSessionId: String) {
        val snapshot = FirebaseRefs.mobileSessionRef(uid).get().await()
        val remoteSessionId = snapshot.child("sessionId").getValue(String::class.java)
        if (remoteSessionId == localSessionId) {
            FirebaseRefs.mobileSessionRef(uid).removeValue().await()
        }
    }

    override suspend fun updateUserDocument(uid: String, email: String, displayName: String) {
        val data = mapOf(
            "email" to email,
            "displayName" to displayName,
            "lastLoginAt" to com.google.firebase.firestore.FieldValue.serverTimestamp()
        )
        firestore.collection("users").document(uid).set(data, SetOptions.merge()).await()
    }

    override suspend fun registerFcmToken(uid: String, token: String) {
        FirebaseRefs.fcmTokensRef(uid, token).setValue(
            mapOf("token" to token, "updatedAt" to ServerValue.TIMESTAMP)
        ).await()
    }

    override suspend fun getWithdrawalState(uid: String, email: String?): WithdrawalState {
        var pending = false
        var deleteAt = 0L
        var rejoinAllowedAt = 0L

        try {
            val userDoc = firestore.collection("users").document(uid).get().await()
            val status = userDoc.getString("withdrawalStatus")
            val delete = userDoc.getLong("deleteAt")
            val rejoin = userDoc.getLong("rejoinAllowedAt")
            Timber.d("[Withdrawal] users/{uid}: exists=${userDoc.exists()}, status=$status, deleteAt=$delete, rejoinAllowedAt=$rejoin")
            if (status == "pending") pending = true
            if (delete != null) deleteAt = maxOf(deleteAt, delete)
            if (rejoin != null) rejoinAllowedAt = maxOf(rejoinAllowedAt, rejoin)
        } catch (e: Exception) {
            Timber.e(e, "[Withdrawal] users/{uid} 조회 실패")
        }

        try {
            val tomb = firestore.collection("withdrawnUsers").document(uid).get().await()
            val rejoin = tomb.getLong("rejoinAllowedAt")
            Timber.d("[Withdrawal] withdrawnUsers/{uid}: exists=${tomb.exists()}, rejoinAllowedAt=$rejoin")
            if (rejoin != null) rejoinAllowedAt = maxOf(rejoinAllowedAt, rejoin)
        } catch (e: Exception) {
            Timber.e(e, "[Withdrawal] withdrawnUsers/{uid} 조회 실패")
        }

        if (email != null) {
            val emailKey = sha256(email.trim().lowercase())
            if (emailKey.isNotBlank()) {
                try {
                    val emailDoc = firestore.collection("withdrawnEmails").document(emailKey).get().await()
                    val rejoin = emailDoc.getLong("rejoinAllowedAt")
                    Timber.d("[Withdrawal] withdrawnEmails/{key}: exists=${emailDoc.exists()}, rejoinAllowedAt=$rejoin")
                    if (rejoin != null) rejoinAllowedAt = maxOf(rejoinAllowedAt, rejoin)
                } catch (e: Exception) {
                    Timber.e(e, "[Withdrawal] withdrawnEmails/{key} 조회 실패")
                }
            }
        }

        Timber.d("[Withdrawal] 최종 결과: pending=$pending, deleteAt=$deleteAt, rejoinAllowedAt=$rejoinAllowedAt")
        return WithdrawalState(pending, deleteAt, rejoinAllowedAt)
    }

    override suspend fun callWithdrawalApi(action: String, email: String?, idToken: String) {
        val baseUrl = "https://us-central1-progresseye-49244.cloudfunctions.net"
        val urlString = "$baseUrl/$action"
        withContext(Dispatchers.IO) {
            try {
                val url = URL(urlString)
                val connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.setRequestProperty("Authorization", "Bearer $idToken")
                connection.setRequestProperty("Content-Type", "application/json")
                connection.doOutput = true
                connection.connectTimeout = 10000
                connection.readTimeout = 10000

                val jsonPayLoad = if (email != null) {
                    """{"email":"${email.trim().lowercase()}"}"""
                } else {
                    "{}"
                }
                val writer = OutputStreamWriter(connection.outputStream)
                writer.write(jsonPayLoad)
                writer.flush()
                writer.close()

                val responseCode = connection.responseCode
                if (responseCode !in 200..299) {
                    val errorText = connection.errorStream?.bufferedReader()?.use { it.readText() } ?: "HTTP $responseCode"
                    throw Exception("$action failed: $responseCode $errorText")
                }
                connection.disconnect()
            } catch (e: Exception) {
                Timber.e(e, "Withdrawal API error")
                throw e
            }
        }
    }

    override fun getCurrentUserUid(): String? {
        return FirebaseAuth.getInstance().currentUser?.uid
    }

    private fun sha256(input: String): String {
        val digest = java.security.MessageDigest.getInstance("SHA-256").digest(input.toByteArray())
        return digest.joinToString("") { "%02x".format(it) }
    }
}
