package com.chg.progeresseye.domain.repository

import kotlinx.coroutines.flow.Flow

interface PolicyRepository {
    fun observePolicy(): Flow<Boolean>
    fun reset()
}
