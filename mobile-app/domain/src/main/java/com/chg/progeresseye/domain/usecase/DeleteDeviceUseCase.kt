package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.DeviceRepository
import javax.inject.Inject

class DeleteDeviceUseCase @Inject constructor(private val repo: DeviceRepository) {
    suspend operator fun invoke(uid: String, deviceId: String) = repo.deleteDevice(uid, deviceId)
}
