package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AuthRepository
import javax.inject.Inject

/**
 * 모바일 기기의 고유 접속 세션을 갱신하여 중복 로그인을 차단하는 UseCase
 *
 * @property repo 인증 및 세션 관리를 수행하는 Repository
 * @constructor Create empty [ActivateMobileSessionUseCase]
 */
class ActivateMobileSessionUseCase @Inject constructor(private val repo: AuthRepository) {
    suspend operator fun invoke(uid: String, deviceId: String, deviceName: String, sessionId: String) = repo.activateMobileSession(uid, deviceId, deviceName, sessionId)
}
