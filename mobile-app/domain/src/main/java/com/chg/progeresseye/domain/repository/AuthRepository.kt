package com.chg.progeresseye.domain.repository

/**
 * 계정 탈퇴 절차 및 접근 허용 상태를 나타내는 데이터 모델
 *
 * @property pending 회원탈퇴 신청이 처리 대기 중(유예 기간)인지 여부
 * @property deleteAt 데이터가 완전히 삭제되는 시점
 * @property rejoinAllowedAt 재가입이 허용되는 시점
 * @constructor Create empty [WithdrawalState]
 */
data class WithdrawalState(
    val pending: Boolean,
    val deleteAt: Long,
    val rejoinAllowedAt: Long,
)

/**
 * 사용자 세션, 계정 생명주기 및 원격 상태 갱신을 관리하는 Repository
 */
interface AuthRepository {
    /**
     * 모바일 기기의 고유 접속 세션을 갱신 (다른 기기 접속 차단용)
     *
     * @param uid 사용자 고유 ID
     * @param deviceId 기기 고유 ID
     * @param deviceName 기기 표시 이름
     */
    suspend fun activateMobileSession(uid: String, deviceId: String, deviceName: String, sessionId: String)

    /**
     * 다른 기기에서 접속이 시도된 경우, 본 기기의 세션 상태를 확인하여 충돌 여부를 반환
     *
     * @param uid 사용자 고유 ID
     * @param deviceId 기기 고유 ID
     * @return 기존에 연결된 디바이스 이름 문자열 (세션 충돌이 없으면 null 반환)
     */
    suspend fun checkExistingSession(uid: String, deviceId: String): String?

    /**
     * 계정에 저장된 세션 ID와 기기 세션이 일치할 경우 기존 원격 세션을 삭제
     *
     * @param uid 사용자 고유 ID
     * @param localSessionId 로컬에 캐시된 고유 세션 ID
     */
    suspend fun clearSessionIfOwned(uid: String, localSessionId: String)

    /**
     * Firestore 사용자 문서에 로그인 일자와 정보를 병합하여 업데이트
     *
     * @param uid 사용자 고유 ID
     * @param email 사용자 이메일
     * @param displayName 사용자 표시 이름
     */
    suspend fun updateUserDocument(uid: String, email: String, displayName: String)

    /**
     * FCM에서 발급받은 푸시 토큰을 사용자 문서에 등록
     *
     * @param uid 사용자 고유 ID
     * @param token FCM 토큰 페이로드
     */
    suspend fun registerFcmToken(uid: String, token: String)

    /**
     * 계정 탈퇴 요청 또는 취소 등의 작업을 외부 API에 의뢰
     *
     * @param action 수행할 Cloud Function 액션 ("requestWithdrawal" 또는 "cancelWithdrawal")
     * @param email 사용자 기본 이메일 주소
     * @param idToken 인증 검증에 사용할 Google ID 토큰 문자열
     */
    suspend fun callWithdrawalApi(action: String, email: String?, idToken: String)

    /**
     * 현재 로그인한 계정의 탈퇴 신청 및 유예 상태를 Firestore에서 조회 후 반환
     *
     * @param uid 사용자 고유 ID
     * @param email 사용자 계정 식별 이메일 주소
     * @return [WithdrawalState] 탈퇴 및 접근 제한 정보
     */
    suspend fun getWithdrawalState(uid: String, email: String?): WithdrawalState

    /**
     * 현재 로그인한 계정의 고유 ID를 조회하여 반환
     *
     * @return 사용자 UID (로그인 상태가 아닐 경우 null)
     */
    fun getCurrentUserUid(): String?
}
