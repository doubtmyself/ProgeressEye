package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.DeviceRepository
import javax.inject.Inject

/**
 * 타겟 기기가 완전히 시스템을 종료하도록 원격 명령을 발행하는 UseCase
 *
 * @property repo 기기 제어 데이터소스에 접근하는 Repository
 * @constructor Create empty [SendShutdownCommandUseCase]
 */
class SendShutdownCommandUseCase @Inject constructor(private val repo: DeviceRepository) {
    suspend operator fun invoke(uid: String, deviceId: String) = repo.sendShutdownCommand(uid, deviceId)
}
