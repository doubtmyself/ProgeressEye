package com.chg.progeresseye.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import timber.log.Timber
import androidx.core.app.NotificationCompat
import com.chg.progeresseye.R
import com.chg.progeresseye.domain.repository.NotificationPrefsRepository
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
import kotlinx.coroutines.runBlocking
import javax.inject.Inject

/**
 * Firebase Cloud Messaging을 처리하여 푸시 알림을 수신하고 표시하는 백그라운드 서비스입니다.
 */
@AndroidEntryPoint
class FCMService : FirebaseMessagingService() {

    @Inject lateinit var authRepository: AuthRepository
    @Inject lateinit var notificationPrefsRepository: NotificationPrefsRepository

    /**
     * 새로운 FCM 토큰이 생성되었을 때 호출됩니다. 서버에 토큰을 등록합니다.
     *
     * @param token 생성된 FCM 등록 토큰
     */
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
     * 새로운 FCM 메시지를 수신했을 때 호출됩니다. 메시지 타입에 따라 알림 표시 여부를 결정합니다.
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
            showErrorReportNotification(title, body)
            return
        }

        val completionEnabled = runBlocking { notificationPrefsRepository.getCompletionAlerts() }
        val stallEnabled = runBlocking { notificationPrefsRepository.getStallWarnings() }

        val shouldNotify = when (type) {
            "completion", "image_change" -> completionEnabled
            "stall", "device_offline" -> stallEnabled
            else -> false
        }

        if (shouldNotify) {
            showNotification(title, body)
        }
    }

    /**
     * 개발자용 오류 보고 알림을 표시합니다.
     *
     * @param title 알림 제목
     * @param body 알림 본문
     */
    private fun showErrorReportNotification(title: String, body: String) {
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                ERROR_CHANNEL_ID,
                "Error Reports",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply { description = "Developer error report notifications" }
            notificationManager.createNotificationChannel(channel)
        }

        val notification = NotificationCompat.Builder(this, ERROR_CHANNEL_ID)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()

        notificationManager.notify(System.currentTimeMillis().toInt(), notification)
    }

    /**
     * 일반적인 상태 알림(진행 완료, 중단 경고 등)을 표시합니다.
     *
     * @param title 알림 제목
     * @param body 알림 본문
     */
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

        /**
         * 현재 기기의 FCM 토큰을 획득하여 서버에 등록합니다.
         *
         * @param authRepository 토큰 등록 처리를 수행할 저장소
         */
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
