package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AuthRepository
import javax.inject.Inject

/**
 * 서버에 다른 기기가 로그인되어 있는지 확인하여 세션 뺏기 동의 여부를 묻기 위해 검사하는 UseCase
 *
 * @property repo 인증 및 세션 관리를 수행하는 Repository
 * @constructor Create empty [CheckExistingSessionUseCase]
 */
class CheckExistingSessionUseCase @Inject constructor(private val repo: AuthRepository) {
    suspend operator fun invoke(uid: String, deviceId: String) = repo.checkExistingSession(uid, deviceId)
}
