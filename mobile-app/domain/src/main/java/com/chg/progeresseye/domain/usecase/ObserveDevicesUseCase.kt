package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.DeviceRepository
import javax.inject.Inject

/**
 * 데스크탑 기기들의 상태 및 작업 목록 변경사항을 실시간으로 구독하는 UseCase
 *
 * @property repo 기기 제어 데이터소스에 접근하는 Repository
 * @constructor Create empty [ObserveDevicesUseCase]
 */
class ObserveDevicesUseCase @Inject constructor(private val repo: DeviceRepository) {
    operator fun invoke(uid: String) = repo.observeDevices(uid)
}
