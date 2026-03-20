package com.chg.progeresseye.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.os.Build
import android.widget.Toast
import timber.log.Timber
import androidx.core.app.NotificationCompat
import com.chg.progeresseye.NotificationPrefs
import com.chg.progeresseye.R
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.chg.progeresseye.domain.repository.AuthRepository
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.DelicateCoroutinesApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.GlobalScope
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * Firebase Cloud Messaging을 처리하여 푸시 알림을 수신하고 표시하는 백그라운드 서비스
 */
@AndroidEntryPoint
class FCMService : FirebaseMessagingService() {

    @Inject lateinit var authRepository: AuthRepository

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        val uid = FirebaseAuth.getInstance().currentUser?.uid ?: return
        @OptIn(DelicateCoroutinesApi::class)
        GlobalScope.launch(Dispatchers.IO) {
            try {
                authRepository.registerFcmToken(uid, token)
            } catch (e: Exception) {
                Timber.e(e, "Failed to save FCM token")
            }
        }
    }

    /**
     * 새로운 FCM 메시지를 수신 시 호출됨
     *
     * @param message 수신된 [RemoteMessage] 객체
     */
    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)

        val data = message.data
        val type = data["type"] ?: return
        val title = data["title"] ?: "ProgressEye"
        val body = data["body"] ?: return

        if (type == "error_report") {
            val traceback = data["traceback"] ?: body
            showErrorReportNotification(title, body, traceback)
            return
        }

        val prefs = applicationContext.getSharedPreferences(NotificationPrefs.PREFS_NAME, Context.MODE_PRIVATE)
        val completionEnabled = prefs.getBoolean(NotificationPrefs.KEY_COMPLETION_ALERTS, true)
        val stallEnabled = prefs.getBoolean(NotificationPrefs.KEY_STALL_WARNINGS, true)

        val shouldNotify = when (type) {
            "completion", "image_change" -> completionEnabled
            "stall", "device_offline" -> stallEnabled
            else -> false
        }

        if (shouldNotify) {
            showNotification(title, body)
        }
    }

    private fun showErrorReportNotification(title: String, body: String, traceback: String) {
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                ERROR_CHANNEL_ID,
                "Error Reports",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply { description = "Developer error report notifications" }
            notificationManager.createNotificationChannel(channel)
        }

        val copyIntent = Intent(applicationContext, CopyToClipboardReceiver::class.java).apply {
            putExtra(EXTRA_COPY_TEXT, traceback)
        }
        val copyPendingIntent = PendingIntent.getBroadcast(
            applicationContext,
            System.currentTimeMillis().toInt(),
            copyIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val notification = NotificationCompat.Builder(this, ERROR_CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setContentIntent(copyPendingIntent)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()

        notificationManager.notify(System.currentTimeMillis().toInt(), notification)
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

    companion object {
        private const val CHANNEL_ID = "progress_alerts"
        private const val ERROR_CHANNEL_ID = "error_reports"
        const val EXTRA_COPY_TEXT = "extra_copy_text"

        @OptIn(DelicateCoroutinesApi::class)
        fun registerToken(authRepository: AuthRepository) {
            FirebaseMessaging.getInstance().token
                .addOnSuccessListener { token ->
                    val uid = FirebaseAuth.getInstance().currentUser?.uid ?: return@addOnSuccessListener
                    GlobalScope.launch(Dispatchers.IO) {
                        try {
                            authRepository.registerFcmToken(uid, token)
                        } catch (e: Exception) {
                            Timber.e(e, "Failed to register FCM token")
                        }
                    }
                }
                .addOnFailureListener { error -> Timber.e(error, "Failed to fetch FCM token") }
        }
    }
}

class CopyToClipboardReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val text = intent.getStringExtra(FCMService.EXTRA_COPY_TEXT) ?: return
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        clipboard.setPrimaryClip(ClipData.newPlainText("error_report", text))
        Toast.makeText(context, "오류 내용이 복사되었습니다", Toast.LENGTH_SHORT).show()
    }
}
