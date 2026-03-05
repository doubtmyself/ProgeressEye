# 구독 서버 검증 체크리스트

## 목적
클라이언트 단 결제 성공 콜백만으로 `plan`을 올리지 않고, 서버 검증(Play Developer API + RTDN)으로 `free/pro` entitlement를 일관되게 관리한다.

## 전제
- 앱 패키지명: `com.chg.progeresseye`
- 구독 상품 ID: `pro_monthly_3000`
- Firestore Rules에서 `users/{uid}.plan`은 신규 문서 생성 시 `free`만 클라이언트 허용하고, `pro` 변경은 서버 전용으로 유지한다 (`firestore.rules`).

## 1) Play Console 설정
- [ ] 구독 상품 `pro_monthly_3000` 생성, 월 베이스 플랜 활성화, 가격 3,000원 설정
- [ ] 내부 테스트 트랙에 빌드 배포 + 라이선스 테스터 계정 등록
- [ ] Play Console -> API 액세스에서 Cloud 프로젝트 연결
- [ ] 서버 검증용 서비스 계정에 Android Publisher API 조회 권한 부여
- [ ] Real-time developer notifications(RTDN)용 Pub/Sub 토픽 연결

## 2) GCP/Firebase 인프라 설정
- [ ] Android Publisher API 활성화
- [ ] RTDN 수신용 Pub/Sub 토픽/권한 확인
- [ ] Cloud Functions 환경변수(또는 Secret)로 패키지명/허용 상품 ID 등록
- [ ] Functions 실행 서비스 계정이 Firestore `users` 문서를 갱신할 수 있는지 확인

## 3) 백엔드 구현 항목 (`functions/index.js`)
- [ ] `verifySubscriptionPurchase` HTTPS 함수 추가
  - 입력: `purchaseToken`, `productId`
  - 인증: `Authorization: Bearer <Firebase ID Token>` 검증
  - 검증: Play Developer API `purchases.subscriptionsv2.get` 호출
  - 판정: 상태(`ACTIVE`, `IN_GRACE_PERIOD`, `ON_HOLD`, `CANCELED`, `EXPIRED`)에 따라 entitlement 계산
  - 반영: Firestore `users/{uid}.plan` 갱신 (`pro` 또는 `free`)
- [ ] `onPlayRtdnMessage` Pub/Sub 트리거 함수 추가
  - RTDN `purchaseToken`/`notificationType` 파싱
  - `subscriptionsv2.get` 재조회 후 최신 상태로 Firestore 반영
- [ ] `reconcileSubscriptions` 스케줄 함수 추가(선택 권장)
  - RTDN 누락 대비 일별 재검증

## 4) 데이터 모델 권장
- [ ] `users/{uid}`
  - `plan`: `free | pro`
  - `planUpdatedAt`: epoch ms
  - `subscription`: `{ productId, purchaseTokenHash, subscriptionState, expiryTime, autoRenewEnabled, source }`
- [ ] 별도 컬렉션 `playSubscriptions/{purchaseTokenHash}`
  - `uid`, `productId`, `linkedPurchaseTokenHash`, `lastNotificationType`, `updatedAt`

## 5) 모바일 앱 변경 항목
- [ ] 결제 성공 후 Firestore 직접 `plan` 쓰기 제거
- [ ] 대신 `verifySubscriptionPurchase` HTTPS 함수 호출로 서버 반영 요청
- [ ] 앱 시작/설정 진입 시 복구 경로에서 서버 상태 재조회
- [ ] UI는 Firestore `users/{uid}.plan` 리스너 값만 기준으로 광고/Pro 기능 분기

## 6) 보안 체크
- [ ] `users/{uid}.plan`은 신규 `free` 생성 외 서버만 변경 가능(현재 규칙 유지)
- [ ] 함수 입력 `productId` 화이트리스트 검증 (`pro_monthly_3000`만 허용)
- [ ] `purchaseToken` 원문 저장 금지, 해시 저장
- [ ] 모든 entitlement 변경 로그(이유/이전값/새값) 기록

## 7) 운영 테스트 시나리오
- [ ] 신규 결제 -> 즉시 `plan=pro`
- [ ] 자동 갱신 -> expiryTime 갱신 + `pro` 유지
- [ ] 결제 실패/계정 보류(on hold) -> 정책에 맞게 `free` 또는 유예 처리
- [ ] 사용자 취소(만료 전) -> 만료 시점까지 `pro`, 이후 `free`
- [ ] 환불/취소(revoke) -> 즉시 `free`
- [ ] 앱 재설치/기기 변경 -> 서버 기준으로 `plan` 복구

## 8) 배포 순서 (권장)
- [ ] Functions 구현/배포: `firebase deploy --only functions --project progresseye-49244`
- [ ] 내부 테스트 트랙에 앱 배포
- [ ] 테스트 결제/취소/복구 시나리오 수행
- [ ] Firestore 상태와 RTDN 로그 대조

## 참고
- Google Play Billing 서버 통합 가이드: RTDN + Developer API 조합을 기준으로 entitlement를 관리한다.
- 구독 상태 조회 API: `purchases.subscriptionsv2.get`
