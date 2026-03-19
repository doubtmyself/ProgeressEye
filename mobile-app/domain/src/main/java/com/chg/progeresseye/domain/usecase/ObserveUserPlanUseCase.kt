package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.UserPlanRepository
import javax.inject.Inject

class ObserveUserPlanUseCase @Inject constructor(private val repo: UserPlanRepository) {
    operator fun invoke(uid: String) = repo.observeUserPlan(uid)
}
