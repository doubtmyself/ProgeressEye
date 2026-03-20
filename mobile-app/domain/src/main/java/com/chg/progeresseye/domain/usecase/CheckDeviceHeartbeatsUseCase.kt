package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.DeviceRepository
import javax.inject.Inject

/**
 * 연동된 데스크탑 기기들의 접속 하트비트를 검사하고 오프라인 전환 여부를 판단하는 UseCase
 *
 * @property repo 기기 제어 데이터소스에 접근하는 Repository
 * @constructor Create empty [CheckDeviceHeartbeatsUseCase]
 */
class CheckDeviceHeartbeatsUseCase @Inject constructor(private val repo: DeviceRepository) {
    suspend operator fun invoke(uid: String) = repo.checkHeartbeats(uid)
}
