package com.chg.progeresseye.domain.repository

import kotlinx.coroutines.flow.Flow

/**
 * 사용자의 구독 플랜 정보를 조회하는 레포지토리 인터페이스입니다.
 */
interface UserPlanRepository {
    fun observeUserPlan(uid: String): Flow<String>
    fun reset()

    /**
     * 사용자의 플랜 정보를 RTDB에 업데이트합니다.
     */
    suspend fun updateUserPlan(uid: String, plan: String)

    /**
     * 사용자의 구독 구매 내역을 Firestore에 기록합니다.
     */
    suspend fun recordSubscriptionPurchase(uid: String, purchaseToken: String, purchaseTime: Long)
}
