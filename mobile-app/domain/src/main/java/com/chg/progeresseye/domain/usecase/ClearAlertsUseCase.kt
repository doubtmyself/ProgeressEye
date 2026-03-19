package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.AlertRepository
import javax.inject.Inject

class ClearAlertsUseCase @Inject constructor(private val repo: AlertRepository) {
    operator fun invoke(uid: String) = repo.clearAlerts(uid)
}
