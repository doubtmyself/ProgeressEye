# Android 앱 — 화면 전환 흐름도

## 페이지 구조

`NavHost`에 두 개의 최상위 목적지가 있다. 시작 목적지는 `authTarget`으로 결정된다.

```
NavHost
├── "login"  ← LoginScreen  (Google 로그인 / 세션 인수 다이얼로그 / 탈퇴 취소 다이얼로그)
└── "main"   ← MainScreen   (하단 탭 3개)
      ├── tab 0 — DashboardContent
      ├── tab 1 — AlertsContent
      └── tab 2 — SettingsContent
```

> `authTarget`은 `AuthUiState`에서 파생된다.
> `user != null && !requiresSessionTakeover && !requiresWithdrawalCancel` → `"main"`, 나머지 → `"login"`.
> 동시에 표시되는 목적지는 항상 1개.

---

## 1. 앱 시작 흐름

```
앱 시작 (MainActivity.onCreate)
  │
  ├─ checkMinVersion()  ← Firestore appConfig/android.minVersion 비동기 조회
  │     ├─ 현재 버전 >= 최소 버전 ──→ 계속
  │     └─ 현재 버전 < 최소 버전
  │           ├─ Play Store 인앱 업데이트(IMMEDIATE) 가능 → 업데이트 플로우 시작
  │           └─ 불가(사이드로드 등) → 폴백 다이얼로그 → Play Store 링크 → 앱 종료
  │
  ├─ requestConsentAndInitAds()  ← UMP 광고 동의 비동기 처리
  │     └─ (광고 흐름 — 아래 §5 참조)
  │
  ├─ AuthViewModel 초기화 (init)
  │     ├─ Firebase 현재 사용자 있음 AND 로컬 sessionId 있음
  │     │     └─ AuthUiState(user = firebaseUser) → authTarget = "main"
  │     └─ 사용자 없음 / sessionId 없음
  │           └─ AuthUiState() → authTarget = "login"
  │
  └─ NavHost 렌더링 → authTarget에 따라 초기 화면 결정
```

---

## 2. 로그인 화면 (`LoginScreen`)

```
[로그인 화면]
  │
  ├─ isLoading = true  → 로딩 스피너 표시
  │
  ├─ 사용자가 "Google로 계속" 클릭 → signInWithGoogle()
  │     │
  │     ├─ Google 로그인 성공 → 탈퇴 상태 조회
  │     │     ├─ 탈퇴 유예 중 (pending && deleteAt > now)
  │     │     │     └─ requiresWithdrawalCancel = true → [탈퇴 취소 다이얼로그] (§2-C)
  │     │     ├─ 재가입 제한 기간 중 (rejoinAllowedAt > now)
  │     │     │     └─ 로그아웃 + error 메시지 → 로그인 화면 유지
  │     │     └─ 정상 → proceedSessionCheck() (§2-B)
  │     │
  │     ├─ Google 로그인 취소됨 → error 메시지 표시 → 로그인 화면 유지
  │     └─ Google 로그인 에러 → error 메시지 표시 → 로그인 화면 유지
  │
  ├─ error != null → 에러 텍스트 표시 (버튼 위)
  │
  ├─ [세션 인수 다이얼로그 — §2-A]
  └─ [탈퇴 취소 다이얼로그 — §2-C]
```

### 2-A. 세션 인수 다이얼로그 (`requiresSessionTakeover = true`)

```
[세션 인수 다이얼로그]
  다른 기기(existingDeviceName)에서 이미 로그인 중
  │
  ├─ "이 기기로 가져오기" 클릭 → confirmSessionTakeover()
  │     └─ doActivateSession() → AuthUiState(user) → navController "main"
  │
  └─ "취소" 클릭 → cancelSessionTakeover()
        └─ 로그아웃 + error 메시지 → 로그인 화면 유지
```

### 2-B. 세션 체크 (`proceedSessionCheck`)

```
proceedSessionCheck()
  │
  ├─ checkExistingSessionUseCase → 다른 기기 세션 있음?
  │     ├─ YES (existingDeviceName != null)
  │     │     └─ requiresSessionTakeover = true → [세션 인수 다이얼로그 §2-A]
  │     └─ NO
  │           └─ doActivateSession() → AuthUiState(user) → navController "main"
  │
  └─ 예외 발생 → error 메시지 → 로그인 화면 유지
```

### 2-C. 탈퇴 취소 다이얼로그 (`requiresWithdrawalCancel = true`)

```
[탈퇴 취소 다이얼로그]
  "탈퇴 처리 중인 계정입니다. 취소하시겠습니까?" (deleteAt까지 날짜 표시)
  │
  ├─ "탈퇴 취소" 클릭 → confirmWithdrawalCancellation()
  │     └─ cancelWithdrawal API → proceedSessionCheck() → "main"
  │
  └─ "탈퇴 유지" 클릭 → keepWithdrawalAndCancelLogin()
        └─ 로그아웃 + 재가입 제한 날짜 안내 → 로그인 화면 유지
```

---

## 3. 메인 화면 (`MainScreen`)

```
[메인 화면 — MainScreen]
  │
  ├─ 하단 탭 바: Dashboard(0) / Alerts(1) / Settings(2)
  │
  ├─ 상단: 배너 광고 (userPlan == "free" && !isAdFreeMode 일 때만 표시)
  │
  ├─ tab 0: [대시보드 §4]
  ├─ tab 1: [알림 §5]
  └─ tab 2: [설정 §6]
```

---

## 4. 대시보드 탭 (`DashboardContent`)

```
[대시보드]
  │
  ├─ 앱 포그라운드 복귀 시 (LifecycleStartEffect)
  │     ├─ startListening() ← RTDB 기기 목록 실시간 구독
  │     └─ refreshSubscriptionStatus() ← 구독 상태 재확인
  │
  ├─ devices 목록 (PC 기기 카드)
  │     ├─ userPlan == "pro" 또는 isAdFreeMode
  │     │     └─ 모든 기기 카드 + 제어 버튼 즉시 사용 가능
  │     └─ userPlan == "free" && !isAdFreeMode && adFreePassRemainingMs <= 0
  │           └─ 첫 번째 기기만 표시 + Pro 업그레이드 배너
  │                 └─ "PRO로 업그레이드" → tab 2 (Settings) 이동
  │
  ├─ 기기 제어 버튼 (스크린샷 / 절전 / 종료)
  │     └─ userPlan == "free" && !isAdFreeMode && adFreePassRemainingMs <= 0
  │           └─ showRewardedAdThen() → 광고 시청 → 명령 실행 + adFreePass 부여
  │
  ├─ screenshotError Snackbar (스크린샷 전송 실패 시)
  │
  └─ requiresForcedSignOut = true → consumeForcedSignOut() → onSignOut()
        └─ AuthViewModel.signOut() → "login" 이동
```

---

## 5. 알림 탭 (`AlertsContent`)

```
[알림]
  │
  └─ RTDB users/{uid}/alerts 목록 표시
        (타임스탬프 기준 최신순, 각 항목: 타입 / 기기명 / 시각)
```

---

## 6. 설정 탭 (`SettingsContent`)

```
[설정]
  │
  ├─ 계정 정보 (이메일)
  ├─ 구독 상태 (Free / Pro)
  │     └─ "Pro 구독" 버튼 → Google Play 구독 플로우
  │
  ├─ 알림 설정 (완료 / 정체)
  │
  ├─ "로그아웃" 클릭 → onSignOut()
  │     └─ AuthViewModel.signOut()
  │           └─ 세션 정리 → Firebase 로그아웃 → AuthUiState() → "login"
  │
  ├─ "계정 삭제" 클릭 → onDeleteAccount()
  │     └─ AuthViewModel.deleteAccount()
  │           └─ requestWithdrawal API → Firebase 로그아웃 → "login"
  │
  └─ 개인정보 보호 옵션 버튼 (EEA / US 규제 지역만 표시)
        └─ onShowPrivacyOptions() → UMP 개인정보 폼 표시
```

---

## 7. 외부 이벤트로 인한 강제 전환

```
다른 기기에서 로그인 (mobileSession.sessionId 변경 감지)
  └─ forceSignOutBySessionConflict() → AuthUiState(error) → "login"

forceLogout 명령 수신 (RTDB commands/forceLogout)
  └─ forceSignOutByWithdrawal() → AuthUiState(error) → "login"

탈퇴 진행 중 감지 (Firestore withdrawalStatus == "pending")
  └─ forceSignOutByWithdrawal() → AuthUiState(error) → "login"
```

---

## 8. 광고 동의 흐름 (앱 시작 시)

```
requestConsentAndInitAds() (UMP)
  │
  ├─ 기존 동의 있음 → initMobileAds() → 광고 초기화 즉시
  │
  ├─ consentInformation.requestConsentInfoUpdate()
  │     └─ 성공 → loadAndShowConsentFormIfRequired()
  │                 ├─ 맞춤형 광고 동의 → initMobileAds()
  │                 └─ 거부 / 닫기 / 비맞춤형 → showConsentRequiredDialog()
  │                       ├─ "재동의" → requestConsentAndInitAds() 재시도
  │                       └─ "Pro 구독" → 광고 미초기화 + 로그인 허용
  │
  └─ 실패 (네트워크 오류) → initMobileAds() (Graceful Degradation)
```

---

## 9. 화면 전환 트리거 요약

| 이벤트 | 출발 화면 | 도착 화면 |
|--------|-----------|-----------|
| 로그인 성공 (세션 정상) | `login` | `main` |
| 로그인 성공 (세션 충돌) | `login` | `login` (세션 인수 다이얼로그) |
| 로그인 성공 (탈퇴 유예) | `login` | `login` (탈퇴 취소 다이얼로그) |
| 세션 인수 확정 | `login` | `main` |
| 세션 인수 취소 | `login` | `login` |
| 탈퇴 취소 성공 | `login` | `main` |
| 탈퇴 유지 선택 | `login` | `login` |
| 로그아웃 | `main` | `login` |
| 계정 삭제 | `main` | `login` |
| 세션 충돌 감지 (외부) | `main` | `login` |
| forceLogout 명령 | `main` | `login` |
| 탈퇴 pending 감지 | `main` | `login` |
| Pro 업그레이드 배너 클릭 | `main` tab 0 | `main` tab 2 |
