package com.chg.progeresseye.domain.usecase

import com.chg.progeresseye.domain.repository.UserPlanRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * [RecordSubscriptionPurchaseUseCase]의 구매 기록 위임 동작을 검증하는 테스트
 */
class RecordSubscriptionPurchaseUseCaseTest {

    /**
     * 구매 토큰과 구매 시각이 변경 없이 레포지토리로 전달되어야 한다.
     */
    @Test
    fun `records purchase with original arguments`() {
        val repo = FakeUserPlanRepository()

        runSuspend {
            RecordSubscriptionPurchaseUseCase(repo)(
                uid = "user-1",
                purchaseToken = "token-1",
                purchaseTime = 1234L,
            )
        }

        assertEquals("user-1", repo.lastUid)
        assertEquals("token-1", repo.lastPurchaseToken)
        assertEquals(1234L, repo.lastPurchaseTime)
    }
}

/**
 * [RecordSubscriptionPurchaseUseCaseTest]에서 구매 기록 인자를 확인하기 위한 fake 구현체
 */
private class FakeUserPlanRepository : UserPlanRepository {
    var lastUid: String? = null
    var lastPurchaseToken: String? = null
    var lastPurchaseTime: Long? = null

    override fun observeUserPlan(uid: String): Flow<String> = flowOf("free")

    override fun reset() = Unit

    override suspend fun updateUserPlan(uid: String, plan: String) = Unit

    override suspend fun recordSubscriptionPurchase(uid: String, purchaseToken: String, purchaseTime: Long) {
        lastUid = uid
        lastPurchaseToken = purchaseToken
        lastPurchaseTime = purchaseTime
    }
}
