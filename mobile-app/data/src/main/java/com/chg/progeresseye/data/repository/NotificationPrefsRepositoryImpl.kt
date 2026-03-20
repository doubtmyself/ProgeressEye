package com.chg.progeresseye.data.repository

import com.chg.progeresseye.data.db.dao.NotificationSettingsDao
import com.chg.progeresseye.data.db.entity.NotificationSettingsEntity
import com.chg.progeresseye.domain.repository.NotificationPrefsRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import javax.inject.Inject

class NotificationPrefsRepositoryImpl @Inject constructor(
    private val dao: NotificationSettingsDao,
) : NotificationPrefsRepository {

    private suspend fun getOrDefault(): NotificationSettingsEntity =
        dao.get() ?: NotificationSettingsEntity()

    override fun observeCompletionAlerts(): Flow<Boolean> =
        dao.observe().map { it?.completionAlerts ?: true }

    override fun observeStallWarnings(): Flow<Boolean> =
        dao.observe().map { it?.stallWarnings ?: true }

    override suspend fun getCompletionAlerts(): Boolean = getOrDefault().completionAlerts

    override suspend fun getStallWarnings(): Boolean = getOrDefault().stallWarnings

    override suspend fun setCompletionAlerts(enabled: Boolean) {
        dao.upsert(getOrDefault().copy(completionAlerts = enabled))
    }

    override suspend fun setStallWarnings(enabled: Boolean) {
        dao.upsert(getOrDefault().copy(stallWarnings = enabled))
    }
}
