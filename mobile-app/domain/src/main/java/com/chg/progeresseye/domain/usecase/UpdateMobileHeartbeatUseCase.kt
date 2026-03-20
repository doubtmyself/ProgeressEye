package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.DeviceRepository
import javax.inject.Inject

/**
 * 모바일 클라이언트가 정상 접속 중임을 서버에 알리기 위해 하트비트를 전송하는 UseCase
 *
 * @property repo 기기 제어 데이터소스에 접근하는 Repository
 * @constructor Create empty [UpdateMobileHeartbeatUseCase]
 */
class UpdateMobileHeartbeatUseCase @Inject constructor(private val repo: DeviceRepository) {
    suspend operator fun invoke(uid: String) = repo.updateMobileHeartbeat(uid)
}
