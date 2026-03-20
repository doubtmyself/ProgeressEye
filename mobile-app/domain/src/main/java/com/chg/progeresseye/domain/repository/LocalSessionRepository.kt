package com.chg.progeresseye.domain.repository

interface LocalSessionRepository {
    suspend fun getOrCreateDeviceId(): String
    suspend fun getSessionId(): String?
    suspend fun saveSessionId(sessionId: String)
    suspend fun clearSession()
}
