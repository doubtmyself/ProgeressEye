package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AlertRepository
import javax.inject.Inject

/**
 * 특정 사용자의 알림 목록 변경사항을 실시간으로 구독하는 UseCase
 */
class ObserveAlertsUseCase @Inject constructor(private val repo: AlertRepository) {
    operator fun invoke(uid: String) = repo.observeAlerts(uid)
}
