package com.chg.progeresseye.domain.repository

import kotlinx.coroutines.flow.Flow

interface AdPrefsRepository {
    suspend fun getAdFreeUntilMs(): Long
    suspend fun setAdFreeUntilMs(ms: Long)
    suspend fun clearAdFreeUntil()
    suspend fun getAdsConsented(): Boolean
    suspend fun setAdsConsented(consented: Boolean)
    suspend fun getIsPersonalizedAds(): Boolean
    suspend fun setIsPersonalizedAds(personalized: Boolean)
    fun observeShowAllPcs(): Flow<Boolean>
    suspend fun getDefaultDeviceId(): String?
    suspend fun setDefaultDeviceId(id: String?)
    suspend fun setShowAllPcs(show: Boolean)
}
