package com.chg.progeresseye.domain.repository

import kotlinx.coroutines.flow.Flow

/**
 * 사용자의 구독 플랜 정보를 조회하는 레포지토리 인터페이스입니다.
 */
interface UserPlanRepository {
    fun observeUserPlan(uid: String): Flow<String>
    fun reset()
}
