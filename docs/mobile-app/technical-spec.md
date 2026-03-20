# Mobile App (Android) - 기술 설계서

---

## 1. 기술 스택

| 영역 | 선택 | 근거 |
|------|------|------|
| 언어 | Kotlin | Android 공식 권장, null-safety |
| UI | Jetpack Compose | 선언형 UI, 빠른 개발, Google 권장 |
| 디자인 | Material Design 3 | 일관된 UX, Dynamic Color 지원 |
| 아키텍처 | MVVM + Clean Architecture | 테스트 용이, 관심사 분리 |
| DI | Hilt | Android 표준 DI 프레임워크 |
| 네비게이션 | Navigation Compose | 단일 Activity + Compose 네비게이션 |
| 인증 | Firebase Auth + Google Sign-In | Android 네이티브 One Tap UI |
| Firebase | Firebase Android SDK | Realtime DB, Storage, FCM, Auth |
| 로컬 저장 | DataStore (Preferences) | 설정 값 영속화 |
| 비동기 | Kotlin Coroutines + Flow | 실시간 데이터 스트림 처리 |
| 차트 | Vico | Compose 네이티브 차트 라이브러리 |
| 위젯 | Glance | Compose 기반 앱 위젯 |
| 이미지 로딩 | Coil | Compose 네이티브 이미지 로더 (스크린샷 표시) |

---

## 2. 모듈 구조

멀티 모듈 Clean Architecture — `:domain` → `:data` → `:app` 의존 방향.

```
mobile-app/
├── domain/                          # 순수 Kotlin (JVM 17, android 의존 없음)
│   └── src/main/java/com/chg/progeresseye/domain/
│       ├── model/
│       │   ├── Alert.kt             # AlertItem data class, AlertType enum
│       │   └── Device.kt            # Device data class (tasks, stats, screenshots 포함)
│       ├── repository/
│       │   ├── AlertRepository.kt
│       │   ├── AuthRepository.kt    # 로그인/로그아웃/FCM 토큰 등록
│       │   ├── DeviceRepository.kt  # 기기 목록, heartbeat, 명령 전송
│       │   ├── UserPlanRepository.kt
│       │   └── PolicyRepository.kt
│       └── usecase/
│           ├── ObserveAlertsUseCase.kt
│           ├── DeleteAlertUseCase.kt
│           ├── ClearAlertsUseCase.kt
│           ├── ObserveUserPlanUseCase.kt
│           ├── UpdateUserPlanUseCase.kt
│           ├── ObservePolicyUseCase.kt
│           ├── ObserveDevicesUseCase.kt
│           ├── CheckDeviceHeartbeatsUseCase.kt
│           ├── UpdateMobileHeartbeatUseCase.kt
│           ├── SendScreenshotCommandUseCase.kt
│           ├── SendShutdownCommandUseCase.kt
│           ├── SendSleepCommandUseCase.kt
│           ├── RegisterFcmTokenUseCase.kt
│           ├── GetCurrentUserUidUseCase.kt
│           ├── ActivateMobileSessionUseCase.kt
│           ├── CheckExistingSessionUseCase.kt
│           ├── ClearSessionIfOwnedUseCase.kt
│           ├── UpdateUserDocumentUseCase.kt
│           ├── GetWithdrawalStateUseCase.kt
│           ├── CallWithdrawalApiUseCase.kt
│           └── RecordSubscriptionPurchaseUseCase.kt
│
├── data/                            # Android Library — Firebase + Hilt 구현체
│   └── src/main/java/com/chg/progeresseye/data/
│       ├── repository/
│       │   ├── AlertRepositoryImpl.kt
│       │   ├── AuthRepositoryImpl.kt       # GoogleAuthRepository 래퍼, FCM 토큰
│       │   ├── DeviceRepositoryImpl.kt     # RTDB devices, commands, heartbeat
│       │   ├── UserPlanRepositoryImpl.kt   # Firestore users/{uid}.plan
│       │   └── PolicyRepositoryImpl.kt     # RTDB policy/isAdFreeModeEnabled
│       ├── di/
│       │   └── DataModule.kt              # @Binds @Singleton — Hilt 바인딩
│       └── util/
│           ├── FirebaseConstants.kt        # FIRESTORE_DB = "progress"
│           ├── FirebaseRefs.kt             # RTDB 경로 상수
│           └── CommandBuilder.kt          # 명령 Map 생성 헬퍼
│
└── app/                             # Android Application — UI + ViewModel
    └── src/main/java/com/chg/progeresseye/
        ├── ProgressEyeApp.kt        # @HiltAndroidApp, Crashlytics(릴리즈만)
        ├── MainActivity.kt          # @AndroidEntryPoint, 세션/forceLogout/탈퇴 리스너
        ├── AppConstants.kt          # NotificationPrefs 등 앱 상수
        ├── auth/
        │   ├── AuthViewModel.kt     # @HiltViewModel, 로그인/세션/탈퇴 처리
        │   ├── GoogleAuthRepository.kt
        │   └── MobileSessionManager.kt
        └── ui/screen/
            ├── main/
            │   └── MainScreen.kt
            ├── dashboard/
            │   ├── DashboardScreen.kt
            │   ├── DashboardUiState.kt     # UI 상태 data class 분리
            │   └── DashboardViewModel.kt  # @HiltViewModel
            ├── alerts/
            │   ├── AlertsScreen.kt
            │   └── AlertsViewModel.kt     # @HiltViewModel
            └── settings/
                ├── SettingsScreen.kt
                └── SettingsViewModel.kt   # @HiltViewModel, 구독 결제
```

### 의존 관계

```
:app  ──depends──>  :domain  (모델, 인터페이스, UseCase)
:app  ──depends──>  :data    (Hilt 모듈 자동 발견)
:data ──depends──>  :domain  (인터페이스 구현)
:domain ── 외부 의존 없음 (javax.inject, coroutines-core만 허용)
```

---

## 3. 핵심 플로우

### 3.1 Google 로그인 플로우

```kotlin
// 의사코드
class AuthRepository @Inject constructor(
    private val firebaseAuth: FirebaseAuth,
    private val googleSignInClient: GoogleSignInClient
) {
    suspend fun signInWithGoogle(idToken: String): Result<FirebaseUser> {
        val credential = GoogleAuthProvider.getCredential(idToken, null)
        val authResult = firebaseAuth.signInWithCredential(credential).await()
        
        // FCM 토큰 등록
        val fcmToken = FirebaseMessaging.getInstance().token.await()
        saveFcmToken(authResult.user!!.uid, fcmToken)
        
        return Result.success(authResult.user!!)
    }
    
    fun observeAuthState(): Flow<FirebaseUser?> = callbackFlow {
        val listener = FirebaseAuth.AuthStateListener { auth ->
            trySend(auth.currentUser)
        }
        firebaseAuth.addAuthStateListener(listener)
        awaitClose { firebaseAuth.removeAuthStateListener(listener) }
    }
}
```

### 3.2 실시간 진행률 수신 (현재 구현)

```kotlin
// DashboardViewModel.kt — Lifecycle-aware RTDB 리스너
class DashboardViewModel : ViewModel() {
    private val auth = FirebaseAuth.getInstance()
    private val db = FirebaseDatabase.getInstance()
    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    private var devicesRef: DatabaseReference? = null
    private var devicesListener: ValueEventListener? = null

    // Lifecycle-driven: MainScreen이 ON_START/ON_STOP에서 호출
    fun startListening() {
        if (devicesListener != null) return  // already listening
        val uid = auth.currentUser?.uid ?: return
        devicesRef = db.reference.child("users").child(uid).child("devices")
        devicesListener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                val devices = snapshot.children.mapNotNull { parseDevice(it) }
                _uiState.value = DashboardUiState(isLoading = false, devices = devices)
            }
            override fun onCancelled(error: DatabaseError) { /* 에러 처리 */ }
        }
        devicesRef?.addValueEventListener(devicesListener!!)
    }

    fun stopListening() {
        devicesListener?.let { devicesRef?.removeEventListener(it) }
        devicesListener = null
    }

    override fun onCleared() {
        super.onCleared()
        stopListening()
    }
}

// MainScreen.kt — LifecycleStartEffect로 포그라운드에서만 리스너 활성화
LifecycleStartEffect(dashboardViewModel) {
    dashboardViewModel.startListening()
    onStopOrDispose { dashboardViewModel.stopListening() }
}
```

> **데이터 최적화 설계 (중요)**:
> - RTDB 리스너는 **앱이 포그라운드일 때만** 활성화된다.
> - 백그라운드 진입 시 리스너를 해제하여 **heartbeat 등 불필요한 push 수신을 차단**한다.
> - 완료/프리징 같은 중요 이벤트는 **FCM 푸시 알림**으로 전달 예정 (백그라운드에서도 수신 가능).
> - 이 구조에서 **모바일 앱이 꺼져 있으면 RTDB 다운로드 비용 = 0**이다.
> - 대시보드에는 PC 앱 설치/공유/복사 CTA가 상시 노출되며, Microsoft Store 이동 및 공유앱(카카오톡 등) 전달/클립보드 복사를 지원한다.
> - Pull-to-refresh는 heartbeat 재검증 후 연결 상태를 보정하며, 새로고침 인디케이터 최소 표시 시간(약 0.9초)으로 끊김을 완화한다.
> - 대시보드 초기 로딩은 ChildEventListener 외에 초기 1회 스냅샷 조회를 사용해, 디바이스가 0개여도 무한 로딩 없이 빈 상태 UI를 표시한다.
> - 전역 광고 비표시 모드(`appConfig/policies.adFreeModeGlobal`)가 활성화되면 스크린샷 요청은 항상 광고를 우회하며, 설정 화면 Pro 구독 CTA는 노출하지 않는다.
>
> Firebase RTDB Spark(무료) 플랜에서 쓰기(PATCH/PUT)는 과금되지 않으며,
> 리스너가 받는 push(다운로드)만 전송량에 잡힌다.

### 3.3 FCM 푸시 알림 처리

```kotlin
class ProgressEyeMessagingService : FirebaseMessagingService() {
    override fun onMessageReceived(message: RemoteMessage) {
        when (message.data["type"]) {
            "complete"  -> showCompletionNotification(message)
            "freeze"    -> showFreezeWarningNotification(message)
            "offline"   -> showOfflineNotification(message)
        }
    }
    
    override fun onNewToken(token: String) {
        updateFcmToken(token)
    }
}
```

### 3.4 원격 명령 전송 (양방향 통신)

PC Agent는 `users/{uid}/commands/` 경로를 SSE(Server-Sent Events)로 실시간 감시한다.
모바일 앱이 해당 경로에 데이터를 기록하면 PC Agent가 즉시 수신하여 처리한다.

```
┌─────────────┐     Firebase RTDB      ┌─────────────┐
│  PC Agent   │ ──── 진행률 push ────→ │  Mobile App │
│  (Python)   │ ←─── 명령 SSE ──────── │  (Kotlin)   │
└──────┬──────┘                        └──────┬──────┘
       │          Firebase Storage            │
       └──── 스크린샷 업로드 ──────────────────┘
              모바일에서 URL로 표시
```

#### 명령 종류

| 명령 | RTDB 경로 | 값 | PC Agent 동작 |
|------|-----------|-----|---------------|
| 스크린샷 | `users/{uid}/commands/screenshot` | `{ts: <epoch>}` | 전체 화면 캡처 → JPEG → Storage 업로드 → RTDB URL 기록 |
| 모니터링 | `users/{uid}/commands/monitor` | `{action: "start"\|"stop", ts}` | 모니터링 시작/정지 토글 |

#### 스크린샷 플로우 (현재 구현)

```kotlin
// 1. 모바일: DashboardViewModel.requestScreenshot(deviceId)
fun requestScreenshot(deviceId: String) {
    val uid = auth.currentUser?.uid ?: return
    _uiState.value = _uiState.value.copy(screenshotLoadingDeviceId = deviceId)
    val commandRef = db.reference
        .child("users").child(uid)
        .child("commands").child("screenshot")
    commandRef.setValue(mapOf("ts" to System.currentTimeMillis() / 1000))
}

// 2. PC Agent: SSE로 수신 → mss 캡처 → JPEG q=70 → Storage 업로드 → RTDB URL 기록
//    (firebase/command_listener.py + firebase/storage.py에서 처리)

// 3. 모바일: RTDB devices/{id}/screenshots/latest 리스너가 URL 수신
//    → Coil SubcomposeAsyncImage로 프리뷰 표시 (16:9)
//    → 클릭 시 풀스크린 다이얼로그 (핀치줌, Modifier.transformable)

// 4. 로딩 상태: screenshotLoadingDeviceId로 추적
//    → 버튼 "Capturing..." + CircularProgressIndicator
//    → RTDB에서 screenshotUrl 변경 감지 시 자동 해제
```

#### 모니터링 제어 플로우

```kotlin
class SendCommandUseCase @Inject constructor(
    private val deviceRepository: DeviceRepository,
    private val firebaseAuth: FirebaseAuth
) {
    suspend fun toggleMonitoring(action: String): Result<Unit> {
        val uid = firebaseAuth.currentUser!!.uid
        val ts = System.currentTimeMillis() / 1000
        return deviceRepository.writeCommand(
            path = "users/$uid/commands/monitor",
            data = mapOf("action" to action, "ts" to ts)
        )
    }
}
```

---

## 4. UI 컴포넌트 설계

### 로그인 화면

```
┌──────────────────────────────────┐
│                                    │
│          ProgressEye               │
│    진행률 모니터링 알리미           │
│                                    │
│    ┌──────────────────────────┐   │
│    │  G  Google로 로그인       │   │
│    └──────────────────────────┘   │
│                                    │
└──────────────────────────────────┘
```

### 대시보드 카드

```
┌──────────────────────────────────┐
│  🖥️  작업용 PC           🟢 온라인  │
│                                    │
│  프리미어 렌더링                    │
│  ████████████████░░░░  73%         │
│                                    │
│  [상세보기]          [⏻ PC 제어]   │
└──────────────────────────────────┘
```

### 상태별 색상

| 상태 | 색상 | 의미 |
|------|------|------|
| running | Primary (Blue) | 정상 진행 중 |
| freeze | Warning (Amber) | 진행 멈춤 감지 |
| complete | Success (Green) | 작업 완료 |
| error | Error (Red) | 오류 발생 |
| offline | Surface Variant (Gray) | PC 오프라인 |

### Firebase RTDB 데이터 구조

```
users/{uid}/
  activeDevice: "pc_xxxx"
  profile: {email, displayName, lastLoginAt}
  commands/                    ← 모바일 → PC 명령 채널
    screenshot: {ts: 1234567890}
    monitor: {action: "start" | "stop", ts: 1234567890}
    forceLogout: {ts: 1234567890}
  devices/
    pc_xxxx/
      name, platform, status, lastSeen, appVersion, createdAt
      screenshots/             ← PC → 모바일 스크린샷 URL
        latest: {url: "https://...", ts: 1234567890}
      tasks/
        region_1/
          p: 45.2      ← progress
          s: "r"        ← status (r=running, f=freeze, c=completed)
          l: "작업이름"  ← label
```

### RTDB 추가 경로 (앱 정책)

```
users/{uid}/
  plan: "free" | "pro"              # 구독 상태 (UserPlanRepositoryImpl)

policy/
  isAdFreeModeEnabled: true | false  # 전역 광고 비표시 정책 (PolicyRepositoryImpl)
```

### Firestore

```
appConfig/pc           → { minVersion: "1.0.0" }   # PC 앱 강제 업데이트 최소 버전 (공개 읽기)
```

### Firebase Storage 경로

```
screenshots/{uid}/{timestamp}.jpg    ← PC Agent가 업로드
```

다운로드 URL 형식:
```
https://firebasestorage.googleapis.com/v0/b/{bucket}/o/screenshots%2F{uid}%2F{ts}.jpg?alt=media&token={token}
```

---

## 5. 빌드 및 배포

### 빌드 설정

멀티 모듈 + Hilt(KSP) 구조. AGP 9.0은 내장 Kotlin 지원을 제공하므로 `kotlin-android` 및 `kapt` 플러그인을 사용하지 않는다.

```kotlin
// settings.gradle.kts — 모듈 등록
include(":app", ":domain", ":data")

// build.gradle.kts (root) — 플러그인 버전 선언
plugins {
    alias(libs.plugins.android.application)  apply false
    alias(libs.plugins.android.library)      apply false
    alias(libs.plugins.kotlin.jvm)           apply false
    alias(libs.plugins.hilt)                 apply false
    alias(libs.plugins.ksp)                  apply false
    alias(libs.plugins.kotlin.compose)       apply false
    alias(libs.plugins.google.services)      apply false
}

// domain/build.gradle.kts — 순수 Kotlin JVM 모듈
plugins {
    alias(libs.plugins.kotlin.jvm)
}
java { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
dependencies {
    api(libs.kotlinx.coroutines.core)
    implementation("javax.inject:javax.inject:1")
}

// data/build.gradle.kts — Android Library + Hilt
plugins {
    alias(libs.plugins.android.library)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
}
android { compileSdk = 36; defaultConfig { minSdk = 24 } }
dependencies {
    implementation(project(":domain"))
    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.database)
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
}

// app/build.gradle.kts — Android Application + Hilt
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.google.services)
    alias(libs.plugins.hilt)
    alias(libs.plugins.ksp)
    id("com.github.triplet.play") version libs.versions.gradlePlayPublisher.get()
}
android {
    compileSdk = 36
    defaultConfig {
        applicationId = "com.chg.progeresseye"
        minSdk = 24; targetSdk = 36
    }
    kotlinOptions { jvmTarget = "11" }
    buildTypes {
        release { isMinifyEnabled = true; isShrinkResources = true }
    }
}
dependencies {
    implementation(project(":domain"))
    implementation(project(":data"))
    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.hilt.navigation.compose)
    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.auth)
    implementation(libs.firebase.database)
    implementation(libs.androidx.credentials)
    implementation(libs.googleid)
}
```

### 주요 라이브러리 버전 (libs.versions.toml)

| 라이브러리 | 버전 |
|-----------|------|
| Hilt | 2.59.2 (AGP 9.0 호환) |
| KSP | 2.3.6 (독립 버전, Kotlin 버전 무관) |
| kotlinx-coroutines | 1.10.2 |
| hilt-navigation-compose | 1.3.0 |

### CI/CD

```
GitHub Push → GitHub Actions
    ├── Lint + Unit Test
    ├── Build Debug APK
    └── (Release) → Signed AAB → GPP → Play Store 자동 업로드

# 수동 배포 명령
.\gradlew.bat publishBundle
```

### 버전 관리

`app/version.properties`에서 버전 관리:
```properties
VERSION_CODE=1
VERSION_NAME_PREFIX=1.0.0
```

`publishBundle` 성공 시 `incrementVersionCode` task가 자동으로 VERSION_CODE를 증가시킨다.
