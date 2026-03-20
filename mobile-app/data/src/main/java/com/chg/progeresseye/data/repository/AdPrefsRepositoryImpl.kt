package com.chg.progeresseye.data.repository

import com.chg.progeresseye.data.db.dao.AdPrefsDao
import com.chg.progeresseye.data.db.entity.AdPrefsEntity
import com.chg.progeresseye.domain.repository.AdPrefsRepository
import javax.inject.Inject

class AdPrefsRepositoryImpl @Inject constructor(
    private val dao: AdPrefsDao,
) : AdPrefsRepository {

    private suspend fun getOrDefault(): AdPrefsEntity = dao.get() ?: AdPrefsEntity()

    override suspend fun getAdFreeUntilMs(): Long = getOrDefault().adFreeUntilMs

    override suspend fun setAdFreeUntilMs(ms: Long) {
        dao.upsert(getOrDefault().copy(adFreeUntilMs = ms))
    }

    override suspend fun clearAdFreeUntil() {
        dao.clearAdFreeUntil()
    }

    override suspend fun getAdsConsented(): Boolean = getOrDefault().adsConsented

    override suspend fun setAdsConsented(consented: Boolean) {
        dao.upsert(getOrDefault().copy(adsConsented = consented))
    }

    override suspend fun getIsPersonalizedAds(): Boolean = getOrDefault().isPersonalizedAds

    override suspend fun setIsPersonalizedAds(personalized: Boolean) {
        dao.upsert(getOrDefault().copy(isPersonalizedAds = personalized))
    }
}
