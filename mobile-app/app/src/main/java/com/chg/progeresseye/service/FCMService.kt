package com.chg.progeresseye.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import com.chg.progeresseye.R
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ServerValue
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

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

        val prefs = applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val completionEnabled = prefs.getBoolean(KEY_COMPLETION_ALERTS, true)
        val stallEnabled = prefs.getBoolean(KEY_STALL_WARNINGS, true)

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
        val tokenId = token.takeLast(8)
        FirebaseDatabase.getInstance()
            .getReference("users/$uid/fcmTokens/$tokenId")
            .setValue(mapOf("token" to token, "updatedAt" to ServerValue.TIMESTAMP))
            .addOnFailureListener { error -> Log.e(TAG, "Failed to save FCM token", error) }
    }

    companion object {
        private const val TAG = "FCMService"
        private const val CHANNEL_ID = "progress_alerts"
        private const val PREFS_NAME = "settings"
        private const val KEY_COMPLETION_ALERTS = "completionAlerts"
        private const val KEY_STALL_WARNINGS = "stallWarnings"

        fun registerToken() {
            FirebaseMessaging.getInstance().token
                .addOnSuccessListener { token ->
                    val uid = FirebaseAuth.getInstance().currentUser?.uid ?: return@addOnSuccessListener
                    val tokenId = token.takeLast(8)
                    FirebaseDatabase.getInstance()
                        .getReference("users/$uid/fcmTokens/$tokenId")
                        .setValue(mapOf("token" to token, "updatedAt" to ServerValue.TIMESTAMP))
                        .addOnFailureListener { error -> Log.e(TAG, "Failed to register FCM token", error) }
                }
                .addOnFailureListener { error -> Log.e(TAG, "Failed to fetch FCM token", error) }
        }
    }
}
