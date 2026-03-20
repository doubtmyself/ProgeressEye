package com.chg.progeresseye.auth

import android.content.Context
import android.os.Build
import java.util.UUID
import androidx.core.content.edit

/**
 * 모바일 기기의 고유 세션 및 디바이스 정보를 관리하는 유틸리티 싱글톤
 */
object MobileSessionManager {
    private const val PREFS_NAME = "mobile_session"
    private const val KEY_DEVICE_ID = "device_id"
    private const val KEY_SESSION_ID = "session_id"

    /**
     * 기기의 고유 ID를 가져오거나 없다면 새로 생성하여 저장 후 반환합니다.
     *
     * @param context SharedPreference 접근용 컨텍스트
     * @return 기기의 UUID 문자열 (android_ 접두어 포함)
     */
    fun getOrCreateDeviceId(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val existing = prefs.getString(KEY_DEVICE_ID, null)
        if (!existing.isNullOrBlank()) {
            return existing
        }
        val created = "android_${UUID.randomUUID()}"
        prefs.edit { putString(KEY_DEVICE_ID, created) }
        return created
    }

    /**
     * 저장된 현재 세션 ID를 가져옵니다.
     *
     * @param context SharedPreference 접근용 컨텍스트
     * @return 저장된 세션 ID 문자열, 없으면 null
     */
    fun getSessionId(context: Context): String? {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getString(KEY_SESSION_ID, null)
    }

    /**
     * 새로운 세션 ID를 영구 저장소에 저장합니다.
     *
     * @param context SharedPreference 접근용 컨텍스트
     * @param sessionId 저장할 새로운 세션 ID
     */
    fun saveSessionId(context: Context, sessionId: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit { putString(KEY_SESSION_ID, sessionId) }
    }

    /**
     * 현재 저장된 세션 ID를 삭제합니다. 로그아웃 시 호출됩니다.
     *
     * @param context SharedPreference 접근용 컨텍스트
     */
    fun clearSession(context: Context) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().remove(KEY_SESSION_ID).apply()
    }

    /**
     * 기기의 제조사 및 모델명을 조합하여 사람이 읽기 쉬운 형태의 디바이스 이름을 반환합니다.
     *
     * @return 렌더링 가능한 디바이스 이름 문자열 (예: "Samsung SM-G991N")
     */
    fun getDeviceName(): String {
        val manufacturer = Build.MANUFACTURER?.trim().orEmpty()
        val model = Build.MODEL?.trim().orEmpty()
        return listOf(manufacturer, model).filter { it.isNotBlank() }.joinToString(" ")
            .ifBlank { "Android Device" }
    }
}
