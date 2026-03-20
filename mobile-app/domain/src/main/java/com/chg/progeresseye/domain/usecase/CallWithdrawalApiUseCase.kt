package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AuthRepository
import javax.inject.Inject

/**
 * 보안 클라우드 함수(Cloud Function)를 호출하여 계정 탈퇴나 취소 요청 서명을 전달하는 UseCase
 *
 * @property repo 인증 및 세션 관리를 수행하는 Repository
 * @constructor Create empty [CallWithdrawalApiUseCase]
 */
class CallWithdrawalApiUseCase @Inject constructor(private val repo: AuthRepository) {
    suspend operator fun invoke(action: String, email: String?, idToken: String) = repo.callWithdrawalApi(action, email, idToken)
}
