package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.UserPlanRepository
import javax.inject.Inject

class RecordSubscriptionPurchaseUseCase @Inject constructor(private val repo: UserPlanRepository) {
    suspend operator fun invoke(uid: String, purchaseToken: String, purchaseTime: Long) = repo.recordSubscriptionPurchase(uid, purchaseToken, purchaseTime)
}
