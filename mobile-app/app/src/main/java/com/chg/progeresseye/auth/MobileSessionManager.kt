package com.chg.progeresseye.auth

import android.content.Context
import android.os.Build
import java.util.UUID

/**
 * 모바일 기기의 고유 세션 및 디바이스 정보를 관리하는 유틸리티 싱글톤
 */
object MobileSessionManager {
    private const val PREFS_NAME = "mobile_session"
    private const val KEY_DEVICE_ID = "device_id"
    private const val KEY_SESSION_ID = "session_id"

    /**
     * 기기의 고유 ID를 가져오거나 없다면 새로 생성하여 반환
     *
     * @param context SharedPreference 접근용 컨텍스트
     * @return 기기의 UUID 문자열
     */
    fun getOrCreateDeviceId(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val existing = prefs.getString(KEY_DEVICE_ID, null)
        if (!existing.isNullOrBlank()) {
            return existing
        }
        val created = "android_${UUID.randomUUID()}"
        prefs.edit().putString(KEY_DEVICE_ID, created).apply()
        return created
    }

    fun getSessionId(context: Context): String? {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getString(KEY_SESSION_ID, null)
    }

    fun saveSessionId(context: Context, sessionId: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_SESSION_ID, sessionId).apply()
    }

    fun clearSession(context: Context) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().remove(KEY_SESSION_ID).apply()
    }

    /**
     * 기기의 제조사 및 모델명을 조합하여 사람이 읽기 쉬운 형태의 디바이스 이름을 반환
     *
     * @return 렌더링 가능한 디바이스 이름 문자열
     */
    fun getDeviceName(): String {
        val manufacturer = Build.MANUFACTURER?.trim().orEmpty()
        val model = Build.MODEL?.trim().orEmpty()
        return listOf(manufacturer, model).filter { it.isNotBlank() }.joinToString(" ")
            .ifBlank { "Android Device" }
    }
}
