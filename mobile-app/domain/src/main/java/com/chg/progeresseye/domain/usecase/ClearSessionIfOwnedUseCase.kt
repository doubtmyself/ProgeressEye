package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AuthRepository
import javax.inject.Inject

/**
 * 현재 기기에서 활성화된 로그아웃 요청 시 권한을 검증 후 원격 세션을 파기하는 UseCase
 *
 * @property repo 인증 및 세션 관리를 수행하는 Repository
 * @constructor Create empty [ClearSessionIfOwnedUseCase]
 */
class ClearSessionIfOwnedUseCase @Inject constructor(private val repo: AuthRepository) {
    suspend operator fun invoke(uid: String, localSessionId: String) = repo.clearSessionIfOwned(uid, localSessionId)
}
