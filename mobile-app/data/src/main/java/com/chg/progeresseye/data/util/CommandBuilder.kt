package com.chg.progeresseye.data.util

import java.util.UUID

/**
 * PC 클라이언트에게 전달할 RTDB 커맨드 페이로드 맵을 생성하는 유틸리티
 */
object CommandBuilder {
    fun build(deviceId: String): Map<String, Any> = mapOf(
        "ts" to System.currentTimeMillis() / 1000,
        "cmdId" to UUID.randomUUID().toString(),
        "targetDeviceId" to deviceId,
    )
}
