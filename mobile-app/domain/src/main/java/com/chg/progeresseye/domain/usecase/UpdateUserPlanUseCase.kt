package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.UserPlanRepository
import javax.inject.Inject

class UpdateUserPlanUseCase @Inject constructor(private val repo: UserPlanRepository) {
    suspend operator fun invoke(uid: String, plan: String) = repo.updateUserPlan(uid, plan)
}
