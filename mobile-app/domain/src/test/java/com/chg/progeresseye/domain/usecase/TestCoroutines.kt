package com.chg.progeresseye.domain.usecase

import kotlin.coroutines.Continuation
import kotlin.coroutines.EmptyCoroutineContext
import kotlin.coroutines.startCoroutine

/**
 * 간단한 domain TDD 테스트에서 추가 코루틴 테스트 의존성 없이 suspend 블록을 동기 실행한다.
 *
 * @param block 실행할 suspend 블록
 * @return [block]의 반환값
 */
internal fun <T> runSuspend(block: suspend () -> T): T {
    var failure: Throwable? = null
    var value: T? = null
    block.startCoroutine(object : Continuation<T> {
        override val context = EmptyCoroutineContext

        override fun resumeWith(result: Result<T>) {
            value = result.getOrNull()
            failure = result.exceptionOrNull()
        }
    })
    failure?.let { throw it }
    @Suppress("UNCHECKED_CAST")
    return value as T
}
