package com.chg.progeresseye.domain.repository

interface AdPrefsRepository {
    suspend fun getAdFreeUntilMs(): Long
    suspend fun setAdFreeUntilMs(ms: Long)
    suspend fun clearAdFreeUntil()
    suspend fun getAdsConsented(): Boolean
    suspend fun setAdsConsented(consented: Boolean)
    suspend fun getIsPersonalizedAds(): Boolean
    suspend fun setIsPersonalizedAds(personalized: Boolean)
}
