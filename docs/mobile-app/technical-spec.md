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
| Firestore | Firebase Firestore SDK | plan 조회 (users/{uid}) |

---

## 2. 모듈 구조

```
mobile-app/
├── app/
│   ├── src/main/
│   │   ├── java/com/progresseye/
│   │   │   ├── ProgressEyeApp.kt          # Application 클래스
│   │   │   ├── MainActivity.kt             # 단일 Activity
│   │   │   │
│   │   │   ├── data/
│   │   │   │   ├── repository/
│   │   │   │   │   ├── AuthRepository.kt       # Google 인증 레포지토리
│   │   │   │   │   ├── TaskRepository.kt       # 작업 데이터 레포지토리
│   │   │   │   │   ├── DeviceRepository.kt     # 기기 관리 레포지토리
│   │   │   │   │   └── SettingsRepository.kt   # 설정 레포지토리
│   │   │   │   ├── remote/
│   │   │   │   │   ├── FirebaseAuthSource.kt   # Firebase Auth + Google Sign-In
│   │   │   │   │   ├── FirebaseDataSource.kt   # Firebase Realtime DB
│   │   │   │   │   ├── FirebaseStorageSource.kt # Firebase Storage (스크린샷)
│   │   │   │   │   └── FirebaseMessaging.kt    # FCM 서비스
│   │   │   │   ├── local/
│   │   │   │   │   └── PreferencesDataStore.kt # 로컬 설정 저장
│   │   │   │   └── model/
│   │   │   │       ├── User.kt                 # 사용자 모델
│   │   │   │       ├── Device.kt               # PC 기기 모델
│   │   │   │       ├── Task.kt                 # 작업 모델
│   │   │   │       ├── Command.kt              # 원격 명령 모델
│   │   │   │       └── Screenshot.kt           # 스크린샷 모델 (url, ts)
│   │   │   │
│   │   │   ├── domain/
│   │   │   │   ├── usecase/
│   │   │   │   │   ├── SignInUseCase.kt             # Google 로그인
│   │   │   │   │   ├── SignOutUseCase.kt            # 로그아웃
│   │   │   │   │   ├── ObserveAuthStateUseCase.kt   # 인증 상태 감시
│   │   │   │   │   ├── ObserveDevicesUseCase.kt     # PC 목록 실시간 관찰
│   │   │   │   │   ├── ObserveTasksUseCase.kt       # 작업 목록 실시간 관찰
│   │   │   │   │   ├── SendCommandUseCase.kt        # 원격 명령 전송
│   │   │   │   │   ├── RequestScreenshotUseCase.kt  # 스크린샷 요청
│   │   │   │   │   ├── ObserveScreenshotUseCase.kt  # 스크린샷 URL 관찰
│   │   │   │   │   └── GetProgressHistoryUseCase.kt # 진행 이력 조회
│   │   │   │   └── model/
│   │   │   │       └── TaskStatus.kt                # 상태 enum
│   │   │   │
│   │   │   ├── ui/
│   │   │   │   ├── navigation/
│   │   │   │   │   └── NavGraph.kt             # 네비게이션 그래프
│   │   │   │   ├── theme/
│   │   │   │   │   ├── Theme.kt                # MD3 테마
│   │   │   │   │   ├── Color.kt                # 컬러 팔레트
│   │   │   │   │   └── Type.kt                 # 타이포그래피
│   │   │   │   ├── auth/
│   │   │   │   │   ├── LoginScreen.kt          # Google 로그인 화면
│   │   │   │   │   └── LoginViewModel.kt
│   │   │   │   ├── dashboard/
│   │   │   │   │   ├── DashboardScreen.kt      # 대시보드 화면
│   │   │   │   │   ├── DashboardViewModel.kt
│   │   │   │   │   └── components/
│   │   │   │   │       ├── DeviceCard.kt       # PC 카드 컴포넌트
│   │   │   │   │       ├── ProgressIndicator.kt # 진행률 표시
│   │   │   │   │       └── EmptyState.kt       # PC 미등록 안내
│   │   │   │   ├── detail/
│   │   │   │   │   ├── TaskDetailScreen.kt     # 작업 상세 화면
│   │   │   │   │   ├── TaskDetailViewModel.kt
│   │   │   │   │   └── components/
│   │   │   │   │       └── ProgressChart.kt    # 진행 추이 차트
│   │   │   │   └── settings/
│   │   │   │       ├── SettingsScreen.kt       # 설정 화면
│   │   │   │       └── SettingsViewModel.kt
│   │   │   │
│   │   │   ├── widget/
│   │   │   │   ├── ProgressWidget.kt           # 홈 위젯 UI
│   │   │   │   └── WidgetUpdateWorker.kt       # 위젯 갱신
│   │   │   │
│   │   │   └── di/
│   │   │       └── AppModule.kt                # Hilt DI 모듈
│   │   │
│   │   └── res/
│   │       ├── values/
│   │       │   ├── strings.xml
│   │       │   └── themes.xml
│   │       └── drawable/
│   │           └── ic_launcher.xml
│   │
│   ├── build.gradle.kts
│   └── proguard-rules.pro
│
├── gradle/
├── build.gradle.kts            # 프로젝트 수준 빌드
├── settings.gradle.kts
└── gradle.properties
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

### Firestore

```
users/{uid}            → { plan: "free" | "pro" }                      # 계정 구독 상태
appConfig/policies     → { adFreeModeGlobal: true | false }              # 전역 광고 정책(관리자 변경)
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

```kotlin
// build.gradle.kts (app) — 현재 설정
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.google.services)
    id("com.github.triplet.play") version libs.versions.gradlePlayPublisher.get()
}

android {
    compileSdk = 36
    defaultConfig {
        applicationId = "com.chg.progeresseye"
        minSdk = 24
        targetSdk = 36
        // version.properties에서 읽기
        val vProps = java.util.Properties().apply {
            file("version.properties").inputStream().use { load(it) }
        }
        versionCode = vProps.getProperty("VERSION_CODE").toInt()
        versionName = vProps.getProperty("VERSION_NAME_PREFIX")
    }
    signingConfigs {
        create("release") {
            // keystore.properties에서 읽기
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = true      // R8 난독화
            isShrinkResources = true    // 리소스 축소
            signingConfig = signingConfigs.getByName("release")
        }
    }
}

play {
    track.set("internal")
    releaseStatus.set(com.github.triplet.gradle.androidpublisher.ReleaseStatus.COMPLETED)
    defaultToAppBundles.set(true)
    serviceAccountCredentials.set(file("google-play-api-key.json"))
}

dependencies {
    // Firebase (BOM 34.9.0)
    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.auth)
    implementation(libs.firebase.database)
    implementation(libs.firebase.firestore)    // 추가됨
    // Credential Manager
    implementation(libs.androidx.credentials)
    implementation(libs.androidx.credentials.play.services.auth)
    implementation(libs.googleid)
}
```

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
