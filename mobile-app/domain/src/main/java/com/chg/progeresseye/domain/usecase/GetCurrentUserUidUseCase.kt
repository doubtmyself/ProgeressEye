package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AuthRepository
import javax.inject.Inject

/**
 * 현재 로그인한 계정의 고유 ID를 가져오는 UseCase
 */
class GetCurrentUserUidUseCase @Inject constructor(private val repo: AuthRepository) {
    operator fun invoke(): String? = repo.getCurrentUserUid()
}
