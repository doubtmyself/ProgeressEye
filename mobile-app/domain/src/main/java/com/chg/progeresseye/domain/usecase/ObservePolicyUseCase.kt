package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.PolicyRepository
import javax.inject.Inject

/**
 * 전역 정책 변경사항을 실시간으로 구독하는 UseCase
 */
class ObservePolicyUseCase @Inject constructor(private val repo: PolicyRepository) {
    operator fun invoke() = repo.observePolicy()
}
