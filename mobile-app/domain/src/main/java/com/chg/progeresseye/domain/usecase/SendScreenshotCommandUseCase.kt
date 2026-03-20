package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.DeviceRepository
import javax.inject.Inject

/**
 * 타겟 기기 화면을 캡처하도록 원격 명령을 발행하는 UseCase
 *
 * @property repo 기기 제어 데이터소스에 접근하는 Repository
 * @constructor Create empty [SendScreenshotCommandUseCase]
 */
class SendScreenshotCommandUseCase @Inject constructor(private val repo: DeviceRepository) {
    suspend operator fun invoke(uid: String, deviceId: String) = repo.sendScreenshotCommand(uid, deviceId)
}
