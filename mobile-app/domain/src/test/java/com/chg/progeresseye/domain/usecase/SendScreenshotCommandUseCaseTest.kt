package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.model.DeviceData
import com.chg.progeresseye.domain.repository.DeviceRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * [SendScreenshotCommandUseCase]의 명령 위임 동작을 검증하는 테스트
 */
class SendScreenshotCommandUseCaseTest {

    /**
     * 사용자 ID와 대상 기기 ID가 변경 없이 스크린샷 명령으로 전달되어야 한다.
     */
    @Test
    fun `sends screenshot command with uid and device id`() {
        val repo = FakeDeviceRepository()

        runSuspend {
            SendScreenshotCommandUseCase(repo)(
                uid = "user-1",
                deviceId = "device-1",
            )
        }

        assertEquals("user-1", repo.lastUid)
        assertEquals("device-1", repo.lastDeviceId)
    }
}

/**
 * [SendScreenshotCommandUseCaseTest]에서 스크린샷 명령 전달 인자를 기록하기 위한 fake 구현체
 */
private class FakeDeviceRepository : DeviceRepository {
    var lastUid: String? = null
    var lastDeviceId: String? = null

    override fun observeDevices(uid: String): Flow<List<DeviceData>> = emptyFlow()

    override suspend fun checkHeartbeats(uid: String) = Unit

    override suspend fun updateMobileHeartbeat(uid: String) = Unit

    override suspend fun sendScreenshotCommand(uid: String, deviceId: String) {
        lastUid = uid
        lastDeviceId = deviceId
    }

    override suspend fun sendSleepCommand(uid: String, deviceId: String) = Unit

    override suspend fun sendShutdownCommand(uid: String, deviceId: String) = Unit

    override suspend fun deleteDevice(uid: String, deviceId: String) = Unit
}
