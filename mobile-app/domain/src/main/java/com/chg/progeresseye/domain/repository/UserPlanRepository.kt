package com.chg.progeresseye.domain.repository

import kotlinx.coroutines.flow.Flow

interface UserPlanRepository {
    fun observeUserPlan(uid: String): Flow<String>
    fun reset()
}
