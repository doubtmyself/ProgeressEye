# 모바일 구독/결제

## 목적
Google Play 정기구독 결제 성공 시 `Pro` 플랜으로 전환하고 광고를 제거하는 흐름을 정의한다.

## 핵심 코드
- `mobile-app/app/src/main/java/com/chg/progeresseye/ui/screen/settings/SettingsViewModel.kt`
- `mobile-app/app/src/main/java/com/chg/progeresseye/ui/screen/settings/SettingsScreen.kt`
- `mobile-app/app/src/main/java/com/chg/progeresseye/ui/screen/dashboard/DashboardViewModel.kt`
- `mobile-app/gradle/libs.versions.toml`
- `mobile-app/app/build.gradle.kts`

## 동작 요약
- 구독 상품 ID: `pro_monthly_3000` (Play Console 상품과 동일해야 함)
- 설정 화면에서 BillingClient 연결 -> 구독 상품 조회 -> 월 구독 구매 플로우 실행
- 구매 완료 시 `acknowledgePurchase` 후 entitlement 반영을 수행
- 대시보드는 Firestore `users/{uid}` 스냅샷 리스너로 plan 변경을 즉시 반영
- `plan == "pro"`이면 보상형 광고 경로를 우회하고 바로 스크린샷 요청을 실행
- `users/{uid}.adFreeMode == true`이면 Free 플랜에서도 보상형 광고를 건너뛴다.

## 운영 메모
- 결제 테스트는 Play Console 내부 테스트 트랙 + 라이선스 테스터 계정으로 검증한다.
- 가격(월 3,000원)은 코드가 아니라 Play Console 구독 상품/베이스 플랜 설정에서 관리한다.
- 앱은 구매 복구를 위해 시작 시 활성 구독을 조회하고 Pro entitlement를 재동기화한다.
- Firestore Rules상 `users/{uid}.plan`은 신규 문서 생성 시 `free`만 클라이언트 허용되고, `pro` 전환/변경은 금지되어 있으므로 운영 배포 전 서버 검증 경로로 전환해야 한다.
- 광고 비표시 모드는 사용자 문서 `adFreeMode` 플래그로 제어하며, 계정 단위로 기기 간 동기화된다.
- `adFreeMode`는 클라이언트 앱에서 직접 변경하지 않고, 관리자(Firebase Console 또는 서버 함수)만 변경한다.

## 서버 검증 문서
- `docs/backend/topics/subscription-server-validation.md`
