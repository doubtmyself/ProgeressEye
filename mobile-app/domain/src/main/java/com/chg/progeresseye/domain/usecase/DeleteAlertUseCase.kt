package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AlertRepository
import javax.inject.Inject

/**
 * 특정 알림 항목을 삭제하는 UseCase
 */
class DeleteAlertUseCase @Inject constructor(private val repo: AlertRepository) {
    operator fun invoke(uid: String, alertId: String) = repo.deleteAlert(uid, alertId)
}
