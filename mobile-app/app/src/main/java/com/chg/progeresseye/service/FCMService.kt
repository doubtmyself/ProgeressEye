package com.chg.progeresseye.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import timber.log.Timber
import androidx.core.app.NotificationCompat
import com.chg.progeresseye.NotificationPrefs
import com.chg.progeresseye.R
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ServerValue
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import java.security.MessageDigest

class FCMService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        saveTokenToRtdb(token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)

        val data = message.data
        val type = data["type"] ?: return
        val title = data["title"] ?: "ProgressEye"
        val body = data["body"] ?: return

        val prefs = applicationContext.getSharedPreferences(NotificationPrefs.PREFS_NAME, Context.MODE_PRIVATE)
        val completionEnabled = prefs.getBoolean(NotificationPrefs.KEY_COMPLETION_ALERTS, true)
        val stallEnabled = prefs.getBoolean(NotificationPrefs.KEY_STALL_WARNINGS, true)

        val shouldNotify = when (type) {
            "completion", "image_change" -> completionEnabled
            "stall" -> stallEnabled
            else -> false
        }

        if (shouldNotify) {
            showNotification(title, body)
        }
    }

    private fun showNotification(title: String, body: String) {
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.notification_channel_name),
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply {
                description = getString(R.string.notification_channel_description)
            }
            notificationManager.createNotificationChannel(channel)
        }

        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()

        notificationManager.notify(System.currentTimeMillis().toInt(), notification)
    }

    private fun saveTokenToRtdb(token: String) {
        val uid = FirebaseAuth.getInstance().currentUser?.uid ?: return
        val tokenId = sha256Short(token)
        FirebaseDatabase.getInstance()
            .getReference("users/$uid/fcmTokens/$tokenId")
            .setValue(mapOf("token" to token, "updatedAt" to ServerValue.TIMESTAMP))
            .addOnFailureListener { error -> Timber.e(error, "Failed to save FCM token") }
    }

    companion object {
        private const val CHANNEL_ID = "progress_alerts"

        fun registerToken() {
            FirebaseMessaging.getInstance().token
                .addOnSuccessListener { token ->
                    val uid = FirebaseAuth.getInstance().currentUser?.uid ?: return@addOnSuccessListener
                    val tokenId = sha256Short(token)
                    FirebaseDatabase.getInstance()
                        .getReference("users/$uid/fcmTokens/$tokenId")
                        .setValue(mapOf("token" to token, "updatedAt" to ServerValue.TIMESTAMP))
                        .addOnFailureListener { error -> Timber.e(error, "Failed to register FCM token") }
                }
                .addOnFailureListener { error -> Timber.e(error, "Failed to fetch FCM token") }
        }

        private fun sha256Short(input: String): String {
            val digest = MessageDigest.getInstance("SHA-256")
            val hash = digest.digest(input.toByteArray())
            return hash.take(8).joinToString("") { "%02x".format(it) }
        }
    }
}
