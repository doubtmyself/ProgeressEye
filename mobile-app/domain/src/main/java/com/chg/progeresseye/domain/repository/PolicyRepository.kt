package com.chg.progeresseye.domain.repository

import kotlinx.coroutines.flow.Flow

/**
 * 전역 정책(예: 광고 없는 모드 활성화 여부 등)을 관리하는 레포지토리 인터페이스입니다.
 */
interface PolicyRepository {
    fun observePolicy(): Flow<Boolean>
    fun reset()
}
