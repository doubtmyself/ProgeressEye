package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AuthRepository
import javax.inject.Inject

/**
 * 사용자가 탈퇴 유예 기간 중인지, 혹은 완전히 삭제되어 접근이 차단된 상태인지 조회하는 UseCase
 *
 * @property repo 인증 및 세션 관리를 수행하는 Repository
 * @constructor Create empty [GetWithdrawalStateUseCase]
 */
class GetWithdrawalStateUseCase @Inject constructor(private val repo: AuthRepository) {
    suspend operator fun invoke(uid: String, email: String?) = repo.getWithdrawalState(uid, email)
}
