package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AuthRepository
import javax.inject.Inject

/**
 * 최종 로그인 기록과 사용자 프로필 메타데이터를 갱신하는 UseCase
 *
 * @property repo 인증 및 세션 관리를 수행하는 Repository
 * @constructor Create empty [UpdateUserDocumentUseCase]
 */
class UpdateUserDocumentUseCase @Inject constructor(private val repo: AuthRepository) {
    suspend operator fun invoke(uid: String, email: String, displayName: String) = repo.updateUserDocument(uid, email, displayName)
}
