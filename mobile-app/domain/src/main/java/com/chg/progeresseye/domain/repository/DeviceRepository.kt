package com.chg.progeresseye.domain.repository

import com.chg.progeresseye.domain.model.DeviceData
import kotlinx.coroutines.flow.Flow

/**
 * 데스크탑 기기들의 상태 및 명령 제어를 담당하는 도메인 계층 Repository
 */
interface DeviceRepository {
    /**
     * 연동된 기기 목록과 상태(실시간 통신 정보 포함)를 지속적으로 관찰하여 반환
     *
     * @param uid 사용자 고유 ID
     * @return [DeviceData] 목록을 방출하는 Flow
     */
    fun observeDevices(uid: String): Flow<List<DeviceData>>

    /**
     * 서버와의 하트비트 상태를 수동으로 갱신하여 확인
     *
     * @param uid 사용자 고유 ID
     */
    suspend fun checkHeartbeats(uid: String)

    /**
     * 모바일 하트비트 신호를 서버로 주기적으로 전송
     *
     * @param uid 사용자 고유 ID
     */
    suspend fun updateMobileHeartbeat(uid: String)

    /**
     * 특정 기기에 스크린샷 캡처 명령을 전송
     *
     * @param uid 사용자 고유 ID
     * @param deviceId 명령을 받을 기기의 ID
     */
    suspend fun sendScreenshotCommand(uid: String, deviceId: String)

    /**
     * 특정 기기에 절전 모드 진입 명령을 전송
     *
     * @param uid 사용자 고유 ID
     * @param deviceId 명령을 받을 기기의 ID
     */
    suspend fun sendSleepCommand(uid: String, deviceId: String)

    /**
     * 특정 기기에 시스템 종료 명령을 전송
     *
     * @param uid 사용자 고유 ID
     * @param deviceId 명령을 받을 기기의 ID
     */
    suspend fun sendShutdownCommand(uid: String, deviceId: String)
}
