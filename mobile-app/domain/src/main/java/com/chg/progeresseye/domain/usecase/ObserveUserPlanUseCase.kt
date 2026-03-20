package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.UserPlanRepository
import javax.inject.Inject

/**
 * 사용자의 현재 구독 플랜 변경사항을 실시간으로 구독하는 UseCase입니다.
 */
class ObserveUserPlanUseCase @Inject constructor(private val repo: UserPlanRepository) {
    operator fun invoke(uid: String) = repo.observeUserPlan(uid)
}
