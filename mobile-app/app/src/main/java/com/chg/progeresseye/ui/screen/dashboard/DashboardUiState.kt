package com.chg.progeresseye.ui.screen.dashboard

import com.chg.progeresseye.domain.model.DeviceData

/**
 * 대시보드 화면이 렌더링할 때 필요한 모든 UI 요소의 상태를 감싸는 UiState 모델
 *
 * @property isLoading 초기 로딩 중 여부
 * @property devices 조회된 디바이스 목록
 * @property error 발생한 일반 오류 메시지
 * @property requiresForcedSignOut 권한 문제로 강제 로그아웃이 필요한 상태인지 여부
 * @property screenshotLoadingDeviceId 스크린샷 갱신을 요청 중인 디바이스 ID
 * @property screenshotError 스크린샷 갱신 실패 시 표시할 오류 메시지
 * @property isRefreshing 전체 화면 새로고침 진행 여부
 * @constructor Create empty [DashboardUiState]
 */
data class DashboardUiState(
    val isLoading: Boolean = true,
    val devices: List<DeviceData> = emptyList(),
    val error: String? = null,
    val requiresForcedSignOut: Boolean = false,
    /** Device ID currently waiting for screenshot response. */
    val screenshotLoadingDeviceId: String? = null,
    /** Screenshot error message to display (timeout, failure). */
    val screenshotError: String? = null,
    /** True during pull-to-refresh. */
    val isRefreshing: Boolean = false,
)
