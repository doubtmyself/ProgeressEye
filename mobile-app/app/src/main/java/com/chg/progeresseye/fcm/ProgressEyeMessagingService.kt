package com.chg.progeresseye.fcm

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat
import com.chg.progeresseye.R
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage

// ═════════════════════════════════════════════════════════
// FCM 수신 서비스 — data-only 메시지 처리
//
// Cloud Functions에서 전송하는 data 메시지 타입:
//   - device_offline  → 조용히 로컬 상태 업데이트 (알림 없음)
//   - task_completed  → Notification 표시
//   - task_frozen     → Notification 표시
// ═════════════════════════════════════════════════════════

class ProgressEyeMessagingService : FirebaseMessagingService() {

    companion object {
        private const val TAG = "FCMService"
        private const val CHANNEL_ID = "progress_eye_alerts"
        private var notificationIdCounter = 0

        /**
         * 현재 유저의 FCM 토큰을 RTDB에 저장한다.
         * 로그인 직후 또는 앱 시작 시 호출.
         */
        fun registerToken(token: String) {
            val uid = FirebaseAuth.getInstance().currentUser?.uid ?: return
            FirebaseDatabase.getInstance().reference
                .child("users").child(uid)
                .child("fcmTokens").child(token)
                .setValue(true)
                .addOnFailureListener { e ->
                    Log.e(TAG, "Failed to register FCM token", e)
                }
        }

        /**
         * RTDB에서 FCM 토큰을 제거한다.
         * 로그아웃 시 호출.
         */
        fun unregisterToken(token: String) {
            val uid = FirebaseAuth.getInstance().currentUser?.uid ?: return
            FirebaseDatabase.getInstance().reference
                .child("users").child(uid)
                .child("fcmTokens").child(token)
                .removeValue()
                .addOnFailureListener { e ->
                    Log.e(TAG, "Failed to unregister FCM token", e)
                }
        }
    }

    // ── Token refresh ──────────────────────────────────────

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.d(TAG, "FCM token refreshed")
        registerToken(token)
    }

    // ── Data message handling ──────────────────────────────

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)

        val data = message.data
        val type = data["type"] ?: return

        Log.d(TAG, "FCM received: type=$type")

        when (type) {
            "device_offline" -> {
                // 조용히 처리 — 알림 없음
                // DashboardViewModel의 heartbeat 리스너가 자동으로 UI 반영
                Log.d(TAG, "Device offline: ${data["deviceId"]}")
            }

            "task_completed" -> {
                val label = data["label"] ?: "Task"
                showNotification(
                    title = getString(R.string.fcm_task_completed_title),
                    body = getString(R.string.fcm_task_completed_body, label),
                )
            }

            "task_frozen" -> {
                val label = data["label"] ?: "Task"
                showNotification(
                    title = getString(R.string.fcm_task_frozen_title),
                    body = getString(R.string.fcm_task_frozen_body, label),
                )
            }

            else -> Log.w(TAG, "Unknown FCM type: $type")
        }
    }

    // ── Notification display ───────────────────────────────

    private fun showNotification(title: String, body: String) {
        val notificationManager =
            getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        // Create channel (Android 8+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.fcm_channel_name),
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = getString(R.string.fcm_channel_description)
            }
            notificationManager.createNotificationChannel(channel)
        }

        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle(title)
            .setContentText(body)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .build()

        notificationManager.notify(notificationIdCounter++, notification)
    }
}
