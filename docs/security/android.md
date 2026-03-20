# Android 앱 보안 체크리스트

> 마지막 감사: 2026-03-20

---

## 요약

| 항목 | 상태 |
|------|------|
| 스크린샷 URL Firebase Storage 도메인 검증 | ✅ 완료 |
| R8/ProGuard 난독화 | ✅ 안전 |
| Timber 로그 (릴리즈 비활성화) | ✅ 안전 |
| Crashlytics 디버그 빌드 비활성화 | ✅ 완료 |
| AndroidManifest exported 컴포넌트 | ✅ 안전 |
| Firebase 인증 토큰 저장 | ✅ 안전 |
| google-services.json 노출 | ✅ 정상 |
| WebView 사용 | ✅ 없음 |
| 하드코딩된 시크릿 | ✅ 없음 |

---

## 1. 인증 / 토큰

### 1-1. Firebase 인증 토큰 저장 ✅ 안전
- **내용:** Firebase Auth SDK가 토큰을 내부적으로 SharedPreferences (암호화) 에 저장
- **위험도:** 없음 — SDK 표준 처리
- **현재 상태:** 안전

### 1-2. google-services.json ✅ 정상
- **파일:** `mobile-app/app/google-services.json`
- **내용:** Firebase 프로젝트 설정, API Key, OAuth Client ID 포함
- **위험도:** 없음 — Firebase 클라이언트 키는 공개 설계. 실제 보안은 Firebase Rules가 담당
- **현재 상태:** 정상 (Firebase Rules로 보호 중)

### 1-3. 하드코딩된 시크릿 ✅ 없음
- **파일:** `strings.xml`, `build.gradle.kts`, 소스코드 전체
- **내용:** API Key, 비밀번호 등 민감 정보 하드코딩 없음
- **현재 상태:** 안전

---

## 2. 네트워크 / 데이터 로딩

### 2-1. 스크린샷 URL Firebase Storage 도메인 검증 ✅ 완료
- **파일:** `ui/screen/dashboard/DashboardViewModel.kt`
- **조치 내용:** RTDB에서 가져온 URL을 Firebase Storage 도메인만 허용하도록 검증 후 Coil에 전달
  ```kotlin
  val screenshotUrl = rawScreenshotUrl?.takeIf {
      it.startsWith("https://firebasestorage.googleapis.com/") ||
      it.startsWith("https://progresseye-49244.firebasestorage.app/")
  }
  ```
- **현재 상태:** 완료

---

## 3. 앱 컴포넌트

### 3-1. AndroidManifest exported 컴포넌트 ✅ 안전
- **파일:** `AndroidManifest.xml`
- **내용:** MainActivity만 `exported=true` (런처 활동, 필수), 나머지 컴포넌트 없음
- **딥링크:** 커스텀 딥링크 없음
- **위험도:** 없음
- **현재 상태:** 안전

### 3-2. WebView ✅ 없음
- **내용:** 앱 전체에서 WebView 사용 없음 → XSS, JavaScript 인터페이스 취약점 없음
- **현재 상태:** 안전

---

## 4. 코드 보호

### 4-1. R8/ProGuard 난독화 ✅ 안전
- **파일:** `app/build.gradle.kts:85-98`
- **내용:**
  ```kotlin
  release {
      isMinifyEnabled = true      // 코드 축소/난독화
      isShrinkResources = true    // 리소스 축소
      proguardFiles(...)
  }
  ```
- **위험도:** 없음 — 릴리즈 빌드 난독화 활성화
- **현재 상태:** 안전

### 4-2. Timber 로그 ✅ 안전
- **파일:** `util/logging/TimberInit.kt`
- **내용:** `BuildConfig.DEBUG`가 true일 때만 Timber tree 등록 → 릴리즈 빌드에서 로그 없음
- **위험도:** 없음
- **현재 상태:** 안전

### 4-3. Crashlytics 디버그 비활성화 ✅ 완료
- **파일:** `ProgressEyeApp.kt`
- **내용:** `FirebaseCrashlytics.getInstance().isCrashlyticsCollectionEnabled = !BuildConfig.DEBUG`
- **효과:** 디버그 빌드에서 Crashlytics 초기화 생략 → 시작 속도 개선 + 디버그 데이터 오염 방지
- **현재 상태:** 완료

---

## 5. Firebase Rules 의존

### 5-1. 클라이언트 보안 의존도
- **내용:** Android 앱의 보안은 Firebase Rules에 상당 부분 의존
- **현재 Rules 상태:**
  - `users/{uid}/*` — 본인만 읽기/쓰기 ✅
  - `commands/{type}` — 본인만 쓰기 ✅
  - 다른 사용자 데이터 접근 불가 ✅
- **위험도:** 없음 — Rules 정상 설정 중
- **현재 상태:** 안전

---

## 조치 현황

| 항목 | 상태 |
|------|------|
| 2-1. 스크린샷 URL 화이트리스트 검증 | ✅ 완료 |
