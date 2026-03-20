package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AuthRepository
import javax.inject.Inject

/**
 * 사용자의 푸시 알림 수신을 위한 FCM 토큰을 계정과 연결하여 서버에 등록하는 UseCase
 *
 * @property repo 인증 및 세션 관리를 수행하는 Repository
 * @constructor Create empty [RegisterFcmTokenUseCase]
 */
class RegisterFcmTokenUseCase @Inject constructor(private val repo: AuthRepository) {
    suspend operator fun invoke(uid: String, token: String) = repo.registerFcmToken(uid, token)
}
