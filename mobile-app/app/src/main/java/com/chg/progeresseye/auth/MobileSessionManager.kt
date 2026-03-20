package com.chg.progeresseye.auth

import android.os.Build

/**
 * 모바일 기기의 디바이스 정보를 반환하는 유틸리티 싱글톤
 *
 * 세션 및 기기 ID 관리는 LocalSessionRepository로 이전되었습니다.
 */
object MobileSessionManager {

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
