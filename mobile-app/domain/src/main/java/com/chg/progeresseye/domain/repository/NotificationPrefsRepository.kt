package com.chg.progeresseye.domain.repository

import kotlinx.coroutines.flow.Flow

interface NotificationPrefsRepository {
    fun observeCompletionAlerts(): Flow<Boolean>
    fun observeStallWarnings(): Flow<Boolean>
    suspend fun getCompletionAlerts(): Boolean
    suspend fun getStallWarnings(): Boolean
    suspend fun setCompletionAlerts(enabled: Boolean)
    suspend fun setStallWarnings(enabled: Boolean)
}
