package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AlertRepository
import javax.inject.Inject

class ObserveAlertsUseCase @Inject constructor(private val repo: AlertRepository) {
    operator fun invoke(uid: String) = repo.observeAlerts(uid)
}
