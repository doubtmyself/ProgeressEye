package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AlertRepository
import javax.inject.Inject

/**
 * 특정 사용자의 모든 알림 데이터를 삭제하는 UseCase
 */
class ClearAlertsUseCase @Inject constructor(private val repo: AlertRepository) {
    operator fun invoke(uid: String) = repo.clearAlerts(uid)
}
