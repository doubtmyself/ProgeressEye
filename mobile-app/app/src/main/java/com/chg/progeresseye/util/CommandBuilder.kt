package com.chg.progeresseye.util

import java.util.UUID

object CommandBuilder {
    fun build(deviceId: String): Map<String, Any> = mapOf(
        "ts" to System.currentTimeMillis() / 1000,
        "cmdId" to UUID.randomUUID().toString(),
        "targetDeviceId" to deviceId,
    )
}
