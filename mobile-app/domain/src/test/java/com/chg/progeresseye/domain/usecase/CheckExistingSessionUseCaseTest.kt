package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AuthRepository
import com.chg.progeresseye.domain.repository.WithdrawalState
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * [CheckExistingSessionUseCase]가 레포지토리 호출 결과를 그대로 반환하는지 검증하는 테스트
 */
class CheckExistingSessionUseCaseTest {

    /**
     * 사용자 ID와 기기 ID를 변경 없이 전달하고, 레포지토리 반환값을 그대로 노출해야 한다.
     */
    @Test
    fun `returns repository session conflict result`() {
        val repo = FakeAuthRepository(existingDeviceName = "Desktop-PC")

        val result = runSuspend {
            CheckExistingSessionUseCase(repo)(
                uid = "user-1",
                deviceId = "device-1",
            )
        }

        assertEquals("Desktop-PC", result)
        assertEquals("user-1", repo.lastUid)
        assertEquals("device-1", repo.lastDeviceId)
    }
}

/**
 * [CheckExistingSessionUseCaseTest]에서 세션 충돌 조회 호출을 검증하기 위한 fake 구현체
 *
 * @property existingDeviceName 레포지토리 호출 시 반환할 기존 기기 이름
 */
private class FakeAuthRepository(
    private val existingDeviceName: String?,
) : AuthRepository {
    var lastUid: String? = null
    var lastDeviceId: String? = null

    override suspend fun activateMobileSession(uid: String, deviceId: String, deviceName: String, sessionId: String) = Unit

    override suspend fun checkExistingSession(uid: String, deviceId: String): String? {
        lastUid = uid
        lastDeviceId = deviceId
        return existingDeviceName
    }

    override suspend fun clearSessionIfOwned(uid: String, localSessionId: String) = Unit

    override suspend fun updateUserDocument(uid: String, email: String, displayName: String) = Unit

    override suspend fun registerFcmToken(uid: String, token: String) = Unit

    override suspend fun callWithdrawalApi(action: String, email: String?, idToken: String) = Unit

    override suspend fun getWithdrawalState(uid: String, email: String?): WithdrawalState {
        return WithdrawalState(pending = false, deleteAt = 0L, rejoinAllowedAt = 0L)
    }

    override fun getCurrentUserUid(): String? = null
}
