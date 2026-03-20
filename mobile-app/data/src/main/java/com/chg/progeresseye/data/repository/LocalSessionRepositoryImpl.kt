package com.chg.progeresseye.data.repository

import com.chg.progeresseye.data.db.dao.SessionDao
import com.chg.progeresseye.data.db.entity.SessionEntity
import com.chg.progeresseye.domain.repository.LocalSessionRepository
import java.util.UUID
import javax.inject.Inject

class LocalSessionRepositoryImpl @Inject constructor(
    private val sessionDao: SessionDao,
) : LocalSessionRepository {

    override suspend fun getOrCreateDeviceId(): String {
        val existing = sessionDao.get()
        if (existing != null && existing.deviceId.isNotBlank()) return existing.deviceId
        val created = "android_${UUID.randomUUID()}"
        sessionDao.upsert(SessionEntity(deviceId = created, sessionId = existing?.sessionId))
        return created
    }

    override suspend fun getSessionId(): String? = sessionDao.get()?.sessionId

    override suspend fun saveSessionId(sessionId: String) {
        val current = sessionDao.get()
        val deviceId = current?.deviceId ?: "android_${UUID.randomUUID()}"
        sessionDao.upsert(SessionEntity(deviceId = deviceId, sessionId = sessionId))
    }

    override suspend fun clearSession() {
        sessionDao.clearSessionId()
    }
}
