package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.PolicyRepository
import javax.inject.Inject

class ObservePolicyUseCase @Inject constructor(private val repo: PolicyRepository) {
    operator fun invoke() = repo.observePolicy()
}
