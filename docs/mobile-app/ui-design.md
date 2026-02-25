# Mobile App (Android) - UI 설계서

---

## 1. 설계 원칙

### 1.1 핵심 방향

| 원칙 | 설명 |
|------|------|
| **한눈에 진행률** | 앱을 열면 즉시 모든 작업의 진행 상태가 보여야 한다 |
| **최소 터치** | 가장 많이 쓰는 기능(진행률 확인)은 0 터치, 스크린샷 요청은 1 터치 |
| **PC Agent와 시각적 일관성** | 다크 테마 기반, 동일한 색상 팔레트 + 진행바 그라데이션 |
| **오프라인 대응** | 네트워크 끊김 시 마지막 캐시 데이터 표시, 새로고침 유도 |

### 1.2 디자인 시스템

- **Material Design 3** 기반
- **Dynamic Color** 비활성 → 브랜드 커스텀 테마 고정 (PC Agent 일관성)
- **다크 모드 기본** (라이트 모드는 설정에서 선택 가능)
- **언어**: 영어 / 한국어 (PC Agent와 동일)

### 1.3 PC Agent 색상 팔레트 → MD3 매핑

| PC Agent 용도 | PC Agent 값 | MD3 역할 | Compose Token |
|---|---|---|---|
| 앱 배경 | `#0f0f1a` | Surface | `MaterialTheme.colorScheme.surface` |
| 카드 배경 | `#1c1c30` | SurfaceContainer | `MaterialTheme.colorScheme.surfaceContainer` |
| 카드 테두리 | `#2a2a45` | OutlineVariant | `MaterialTheme.colorScheme.outlineVariant` |
| 제목 텍스트 | `#ffffff` | OnSurface | `MaterialTheme.colorScheme.onSurface` |
| 부제목 텍스트 | `#8888aa` | OnSurfaceVariant | `MaterialTheme.colorScheme.onSurfaceVariant` |
| 진행바 왼쪽 | `#3b82f6` | Primary | `MaterialTheme.colorScheme.primary` |
| 진행바 오른쪽 | `#22d3ee` | — | 커스텀 그라데이션 끝 색상 |
| 진행바 트랙 | `#252540` | SurfaceContainerHighest | 커스텀 |
| 상태: 진행중 | `#3b82f6` | Primary | 파란색 |
| 상태: 완료 | `#4ade80` | 커스텀 | 초록색 |
| 상태: 멈춤 | `#666688` → `Amber` | 커스텀 | MD3 Warning 계열 |
| 정지 버튼 | `#ef4444` | Error | `MaterialTheme.colorScheme.error` |
| 시작 버튼 | `#3b82f6` | Primary | `MaterialTheme.colorScheme.primary` |
| 스크롤바 | `#2a2a45` | — | `MaterialTheme.colorScheme.outlineVariant` |

---

## 2. 네비게이션 구조

### 2.1 화면 목록

```
App
├── SplashScreen (자동 로그인 체크, 0.5~1초)
├── LoginScreen (Google Sign-In)
├── MainScaffold (하단 네비게이션)
│   ├── DashboardScreen (홈 탭) ─── 기본 탭
│   │   ├── DeviceSection (PC별 접이식 섹션)
│   │   │   ├── TaskCard × N (작업 카드)
│   │   │   └── QuickActions (스크린샷, 모니터링 제어)
│   │   └── EmptyState (PC 미등록 안내)
│   └── SettingsScreen (설정 탭)
│       ├── AccountSection (계정 정보, 로그아웃)
│       ├── NotificationSection (알림 설정)
│       ├── AppearanceSection (테마)
│       └── AboutSection (버전, 정보)
├── ScreenshotViewerScreen (전체 화면, 핀치 줌)
└── TaskDetailScreen (2단계, 진행 그래프)
```

### 2.2 네비게이션 그래프

```kotlin
// NavGraph.kt
sealed class Screen(val route: String) {
    object Splash : Screen("splash")
    object Login : Screen("login")
    object Dashboard : Screen("dashboard")
    object Settings : Screen("settings")
    object ScreenshotViewer : Screen("screenshot/{deviceId}")
    object TaskDetail : Screen("task/{deviceId}/{taskId}")  // P1
}
```

### 2.3 하단 네비게이션

| 탭 | 아이콘 | 라벨(EN) | 라벨(KO) |
|---|---|---|---|
| 대시보드 | `Icons.Filled.Dashboard` | Dashboard | 대시보드 |
| 알림 | `Icons.Filled.Notifications` | Alerts | 알림 |
| 설정 | `Icons.Filled.Settings` | Settings | 설정 |

> 3탭 구조. Dashboard(핵심), Alerts(알림 이력), Settings(계정/설정).

### 2.4 공통 상단바 (CommonTopBar)

모든 탭 화면에서 동일한 `TopAppBar`를 사용한다. 탭별로 아이콘 + 타이틀이 변경된다.

| 탭 | 아이콘 | 타이틀 |
|---|---|---|
| Dashboard | `Icons.Filled.Dashboard` | Dashboard |
| Alerts | `Icons.Filled.Notifications` | Alerts |
| Settings | `Icons.Filled.Settings` | Settings |

```kotlin
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CommonTopBar(icon: ImageVector, title: String) {
    TopAppBar(
        title = {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(title)
            }
        },
        colors = TopAppBarDefaults.topAppBarColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    )
}
```

> 상단바에 별도 액션 아이콘(설정 등)을 두지 않는다. 설정은 하단 네비게이션 탭으로 접근.

---

## 3. 화면별 상세 설계

### 3.1 Splash Screen

```
┌─────────────────────────────────┐
│                                   │
│                                   │
│         [ProgressEye 로고]         │
│                                   │
│         ○ ○ ○  (로딩 인디케이터)   │
│                                   │
│                                   │
└─────────────────────────────────┘
```

**동작:**
1. 앱 시작 → Firebase Auth 상태 확인
2. 로그인 됨 → Dashboard 이동 (0.5초 딜레이)
3. 로그인 안됨 → Login 이동

**컴포넌트:** `Box` + `CircularProgressIndicator`

---

### 3.2 Login Screen

```
┌─────────────────────────────────┐
│                                   │
│                                   │
│         [ProgressEye 로고]         │
│                                   │
│    Monitor your progress,         │
│    anywhere.                      │
│                                   │
│  ┌─────────────────────────────┐ │
│  │  G  Sign in with Google      │ │
│  └─────────────────────────────┘ │
│                                   │
│                                   │
└─────────────────────────────────┘
```

**컴포넌트:**
- `Column` (수직 중앙 정렬)
- 앱 로고 (커스텀 이미지)
- 슬로건 텍스트
- Google Sign-In 버튼 (`Credential Manager` API)

**상태:**
- `Idle` → 버튼 활성
- `Loading` → 버튼 비활성 + `CircularProgressIndicator`
- `Error` → `Snackbar` 에러 메시지

---

### 3.3 Dashboard Screen (핵심 화면)

#### Free 플랜 (PC 1대) — 작업 카드가 바로 보임

```
┌─────────────────────────────────┐
│  [📊] Dashboard                  │  ← CommonTopBar
├─────────────────────────────────┤
│                                   │
│  🖥️ DESKTOP-ABC  🟢 Online       │  ← 기기 헤더
│     Windows · 2분 전 동기화       │
│                                   │
│  ┌─────────────────────────────┐ │
│  │  프리미어 렌더링      진행중  │ │  ← TaskCard
│  │  ████████████████░░░  73.2% │ │
│  │                     ▲ 80%   │ │  ← 알람 임계값 표시
│  └─────────────────────────────┘ │
│                                   │
│  ┌─────────────────────────────┐ │
│  │  파일 다운로드          완료  │ │
│  │  ████████████████████ 100%  │ │
│  └─────────────────────────────┘ │
│                                   │
│  ┌─────────────────────────────┐ │
│  │  설치 작업              멈춤  │ │
│  │  ████████░░░░░░░░░░░  34.5% │ │
│  │  ⚠️ 5분째 변화 없음          │ │  ← 프리징 경고
│  └─────────────────────────────┘ │
│                                   │
│  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  │
│                                   │
│  [📸 스크린샷]   [▶ 모니터링 시작] │  ← 빠른 액션 버튼
│                                   │
└─────────────────────────────────┘
│  [ 📊 대시보드 ] [ 🔔 알림 ] [ ⚙️ 설정 ] │  ← BottomNavigation (3탭)
└─────────────────────────────────┘
```

#### Pro 플랜 (PC 여러 대) — 기기별 접이식 섹션

```
┌─────────────────────────────────┐
│  [📊] Dashboard                  │
├─────────────────────────────────┤
│                                   │
│  ▼ 🖥️ 작업용 PC       🟢 Online  │  ← 펼침 (ExpandableCard)
│  │  프리미어 렌더링  ████ 73.2%  │
│  │  파일 다운로드    ████ 100%   │
│  │  [📸] [▶ 모니터링]            │
│                                   │
│  ▶ 🖥️ 게임 PC         ⚫ Offline │  ← 접힘
│     마지막 접속: 3시간 전         │
│                                   │
└─────────────────────────────────┘
```

#### PC 미등록 시 (Empty State)

```
┌─────────────────────────────────┐
│  [📊] Dashboard                  │
├─────────────────────────────────┤
│                                   │
│                                   │
│         [일러스트 이미지]          │
│                                   │
│    No PCs connected yet           │
│                                   │
│    Sign in with the same Google   │
│    account on PC Agent to start   │
│    monitoring.                    │
│                                   │
│                                   │
└─────────────────────────────────┘
```

#### TaskCard 컴포넌트 상세

```kotlin
@Composable
fun TaskCard(task: Task) {
    // 카드 배경: surfaceContainer (#1c1c30)
    // 테두리: outlineVariant (#2a2a45), 1dp, 12dp 라운드
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainer
        ),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Row 1: 라벨 + 상태 배지
            Row {
                Text(task.label)           // onSurface, bodyLarge
                Spacer(Modifier.weight(1f))
                StatusBadge(task.status)    // 색상별 배지
            }
            Spacer(8.dp)
            // Row 2: 진행바 + 퍼센트
            Row(verticalAlignment = CenterVertically) {
                // 그라데이션 진행바 (#3b82f6 → #22d3ee)
                GradientProgressBar(
                    progress = task.progress / 100f,
                    modifier = Modifier.weight(1f).height(8.dp)
                )
                Spacer(8.dp)
                Text("${task.progress}%")  // onSurface, titleMedium
            }
            // Row 3: 경고 (프리징 등, 조건부)
            if (task.status == "f") {
                Spacer(4.dp)
                Text("⚠️ No change detected", color = warningColor)
            }
        }
    }
}
```

#### GradientProgressBar 컴포넌트

```kotlin
@Composable
fun GradientProgressBar(progress: Float, modifier: Modifier) {
    // 트랙: #252540
    // 그라데이션 fill: #3b82f6 → #22d3ee
    // 높이: 8dp, 코너: 4dp
    Canvas(modifier = modifier.clip(RoundedCornerShape(4.dp))) {
        // 트랙
        drawRoundRect(color = trackColor, cornerRadius = CornerRadius(4.dp))
        // Fill (그라데이션)
        drawRoundRect(
            brush = Brush.horizontalGradient(
                colors = listOf(Color(0xFF3B82F6), Color(0xFF22D3EE))
            ),
            size = Size(size.width * progress, size.height),
            cornerRadius = CornerRadius(4.dp)
        )
    }
}
```

#### StatusBadge 컴포넌트

```
상태별 표시:

  ● 진행중   → #3b82f6 (Primary Blue) + "Running" / "진행중"
  ● 완료     → #4ade80 (Green)        + "Done" / "완료"
  ● 멈춤     → #f59e0b (Amber)        + "Stalled" / "멈춤"
  ● 오프라인 → #666688 (Gray)         + "Offline" / "오프라인"
```

---

### 3.4 빠른 액션 바 (Quick Actions)

기기 섹션 하단에 위치. 오프라인 시 버튼 비활성.

```
┌────────────────┐  ┌────────────────────────┐
│  📸 Screenshot  │  │  ▶ Start Monitoring     │
└────────────────┘  └────────────────────────┘
```

| 버튼 | 동작 | 오프라인 시 |
|------|------|------------|
| 📸 스크린샷 | `commands/screenshot` 기록 → 로딩 → 이미지 표시 | 비활성 (grayed out) |
| ▶ 모니터링 시작 | `commands/monitor` 기록 `{action: "start"}` | 비활성 |
| ⏹ 모니터링 정지 | `commands/monitor` 기록 `{action: "stop"}` | 비활성 |

**스크린샷 요청 플로우 (UI 상태):**

```
[📸 버튼 탭]
    ↓
[로딩 상태] ← 버튼 → CircularProgressIndicator 교체
    ↓  (RTDB screenshots/latest 리스너 대기)
[이미지 수신] ← BottomSheet 또는 ScreenshotViewerScreen으로 표시
    ↓
[📸 버튼 복귀]
```

**타임아웃:** 15초 내 응답 없으면 "PC가 응답하지 않습니다" Snackbar

---

### 3.5 Screenshot Viewer Screen

```
┌─────────────────────────────────┐
│  ← Screenshot     12:34 PM      │  ← TopAppBar (뒤로가기)
├─────────────────────────────────┤
│                                   │
│                                   │
│     [전체 화면 스크린샷 이미지]     │  ← 핀치-투-줌 지원
│     (Coil AsyncImage)             │
│                                   │
│                                   │
│                                   │
├─────────────────────────────────┤
│  Captured: 2 minutes ago          │
│                                   │
│  ┌─────────────────────────────┐ │
│  │     📸  Request New          │ │  ← 새 스크린샷 요청 버튼
│  └─────────────────────────────┘ │
└─────────────────────────────────┘
```

**컴포넌트:**
- `Coil AsyncImage` + `ZoomableState` (pinch-to-zoom)
- 상대 시간 표시 ("2 minutes ago")
- "Request New" 버튼 → 스크린샷 재요청

**상태:**
- `Loading` → `CircularProgressIndicator` (중앙)
- `Success` → 이미지 표시
- `Error` → 에러 메시지 + 재시도 버튼
- `NoScreenshot` → "No screenshot available. Request one!" 안내

---

### 3.6 Settings Screen

```
┌─────────────────────────────────┐
│  Settings                        │
├─────────────────────────────────┤
│                                   │
│  ACCOUNT                          │
│  ┌─────────────────────────────┐ │
│  │  👤 user@gmail.com           │ │
│  │     Free Plan                │ │
│  │                   [Log out]  │ │
│  └─────────────────────────────┘ │
│                                   │
│  NOTIFICATIONS                    │
│  ┌─────────────────────────────┐ │
│  │  Completion alerts    [🔘]   │ │
│  │  Stall warnings       [🔘]   │ │
│  │  Offline alerts       [🔘]   │ │
│  └─────────────────────────────┘ │
│                                   │
│  APPEARANCE                       │
│  ┌─────────────────────────────┐ │
│  │  Theme          [Dark ▼]    │ │
│  │  Language       [English ▼] │ │
│  └─────────────────────────────┘ │
│                                   │
│  ABOUT                            │
│  ┌─────────────────────────────┐ │
│  │  Version        1.0.0       │ │
│  │  Licenses                 > │ │
│  └─────────────────────────────┘ │
│                                   │
└─────────────────────────────────┘
```

**컴포넌트:**
- `LazyColumn` + 섹션 헤더 (카테고리)
- 각 항목: MD3 `ListItem` 또는 커스텀 `Row`
- 토글: MD3 `Switch`
- 드롭다운: MD3 `ExposedDropdownMenuBox`
- 로그아웃: 확인 `AlertDialog` 후 실행

---

## 4. 상태 관리 (ViewModel → Compose)

### 4.1 Dashboard UiState

```kotlin
sealed interface DashboardUiState {
    object Loading : DashboardUiState
    object Empty : DashboardUiState  // PC 미등록
    data class Success(
        val devices: List<DeviceWithTasks>
    ) : DashboardUiState
    data class Error(val message: String) : DashboardUiState
}

data class DeviceWithTasks(
    val device: Device,
    val tasks: List<Task>,
    val screenshot: Screenshot?,
    val isMonitoring: Boolean,  // tasks 중 status="r" 존재 여부로 추론
)

data class Device(
    val id: String,
    val name: String,
    val platform: String,
    val status: String,        // "online" | "offline"
    val lastSeen: Long,        // epoch ms
    val appVersion: String,
)

data class Task(
    val id: String,
    val label: String,
    val progress: Double,      // 0.0 ~ 100.0
    val status: String,        // "r" | "f" | "c"
)

data class Screenshot(
    val url: String,
    val timestamp: Long,       // epoch seconds
)
```

### 4.2 데이터 흐름 (현재 구현)

```
앱 포그라운드 (LifecycleStartEffect)
    │
    ├─ onStart → DashboardViewModel.startListening()
    │    └─ Firebase RTDB ValueEventListener 등록
    │        └─ ↓ (push)
    │    DashboardViewModel (MutableStateFlow<DashboardUiState>)
    │        └─ ↓ (.collectAsStateWithLifecycle())
    │    Compose UI (자동 recomposition)
    │
    └─ onStop → DashboardViewModel.stopListening()
         └─ ValueEventListener 해제 → 데이터 전송 0
```

> **Note**: Hilt DI 미적용 상태. ViewModel이 직접 FirebaseDatabase 인스턴스를 생성하여 리스너 관리.
> 추후 Hilt 도입 시 Repository 계층 분리 예정.

**데이터 최적화 설계:**
- **포그라운드 전용 리스너**: `LifecycleStartEffect`로 앱이 화면에 보일 때만 RTDB 리스너 활성화
- **백그라운드 전송 0**: 앱이 백그라운드로 가면 리스너 해제 → Firebase 데이터 전송량 발생 안 함
- **완료/프리징 알림**: FCM 푸시 알림으로 처리 (추후 구현)
- **쿠리 무료**: RTDB PATCH/PUT(쓰기)는 과금 안 됨. 리스너가 받는 push(다운로드)만 전송량 카운트

**구현된 상태:**
- DashboardViewModel: `startListening()`/`stopListening()` 메서드로 lifecycle-aware 리스너 관리
- `users/{uid}/devices` 경로에 ValueEventListener 등록/해제
- 디바이스 + 작업 데이터 실시간 수신 → DashboardUiState로 변환
- 로딩/에러/빈 상태/데이터 표시 4가지 UI 상태 처리
- 온라인 판단: lastSeen이 2분 이내이면 Online
- 스크린샷 요청/표시: Coil 3 AsyncImage + 풀스크린 다이얼로그(핀치 줌)

**TODO:**
- CPU 사용량, 온도 메트릭 표시 (MetricChip) — 추후 구현
- Pull-to-Refresh 지원
- FCM 푸시 알림 구현 (완료/프리징 백그라운드 알림)
### 4.3 리스너 경로

| 데이터 | RTDB 경로 | 갱신 주기 |
|---|---|---|
| 기기 목록 | `users/{uid}/devices` | 기기 등록/해제 시 |
| 작업 진행률 | `users/{uid}/devices/{id}/tasks` | 모니터링 사이클 (기본 30초) |
| 스크린샷 | `users/{uid}/devices/{id}/screenshots/latest` | 요청 시 |
| 사용자 플랜 | `users/{uid}/plan` | 로그인 시 1회 |

---

## 5. 인터랙션 상세

### 5.1 Pull-to-Refresh

```kotlin
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(viewModel: DashboardViewModel) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val pullRefreshState = rememberPullToRefreshState()

    PullToRefreshBox(
        isRefreshing = uiState is Loading,
        onRefresh = { viewModel.refresh() },
        state = pullRefreshState
    ) {
        LazyColumn { /* 기기 + 작업 카드 */ }
    }
}
```

### 5.2 명령 전송 확인 다이얼로그

모니터링 시작/정지 명령 시:

```
┌─────────────────────────────────┐
│                                   │
│  Start Monitoring?                │
│                                   │
│  This will begin monitoring all   │
│  active tasks on DESKTOP-ABC.     │
│                                   │
│           [Cancel]  [Start]       │
│                                   │
└─────────────────────────────────┘
```

### 5.3 오프라인 배너

PC가 오프라인일 때 기기 헤더 하단에:

```
┌─────────────────────────────────┐
│  ⚫ DESKTOP-ABC       Offline    │
│  ┌─────────────────────────────┐│
│  │ ⚠️ PC is offline.            ││
│  │    Last seen: 3 hours ago   ││
│  └─────────────────────────────┘│
│  (작업 카드들은 마지막 캐시 표시)  │
└─────────────────────────────────┘
```

### 5.4 진행률 애니메이션

```kotlin
// 진행바 값 변경 시 부드러운 애니메이션
val animatedProgress by animateFloatAsState(
    targetValue = task.progress / 100f,
    animationSpec = tween(durationMillis = 600, easing = EaseOutCubic)
)
```

---

## 6. 알림 (Push Notification)

### 6.1 알림 채널

| 채널 ID | 이름(EN) | 이름(KO) | 중요도 |
|---|---|---|---|
| `completion` | Task Completed | 작업 완료 | HIGH (소리 + 진동) |
| `stall` | Task Stalled | 작업 멈춤 | DEFAULT (진동) |
| `offline` | PC Offline | PC 오프라인 | LOW (무음) |

### 6.2 알림 레이아웃

```
┌─────────────────────────────────┐
│ ProgressEye               12:34 │
│ ✅ 프리미어 렌더링 — 100% 완료    │
│ DESKTOP-ABC에서 작업이 완료되었습니다 │
└─────────────────────────────────┘
```

**알림 탭 → 해당 기기의 대시보드로 딥링크**

---

## 7. 반응형 레이아웃

### 7.1 화면 크기별 대응

| 분류 | 너비 | 레이아웃 |
|---|---|---|
| Compact (폰) | < 600dp | 단일 컬럼, 풀 너비 카드 |
| Medium (태블릿 세로) | 600~840dp | 2컬럼 그리드 |
| Expanded (태블릿 가로) | > 840dp | 좌측 기기 목록 + 우측 상세 (List-Detail) |

### 7.2 Compact (기본)

```
[TopAppBar]
[Device Header]
[TaskCard]
[TaskCard]
[TaskCard]
[QuickActions]
```

### 7.3 Expanded (태블릿)

```
┌──────────────┬──────────────────────┐
│ Device List   │ Device Detail         │
│               │                       │
│ ▶ 작업용 PC   │ 🖥️ 작업용 PC   🟢     │
│ ▶ 게임 PC     │                       │
│               │ [TaskCard]            │
│               │ [TaskCard]            │
│               │ [QuickActions]        │
│               │                       │
│               │ [스크린샷 미리보기]    │
└──────────────┴──────────────────────┘
```

---

## 8. 단계별 구현 계획

### P0 (1단계 — MVP)

| 화면 | 핵심 기능 |
|------|----------|
| Splash | 자동 로그인 |
| Login | Google Sign-In |
| Dashboard | 기기 목록, 작업 카드(진행바 + 상태), 실시간 갱신 |
| Quick Actions | 스크린샷 요청, 모니터링 시작/정지 |
| Screenshot Viewer | 이미지 표시, 핀치 줌 |
| Settings | 계정, 로그아웃, 언어, 테마 |
| Notification | 완료 알림 (FCM) |

### P1 (2단계)

| 화면 | 핵심 기능 |
|------|----------|
| Task Detail | 진행률 그래프 (시간별 추이, Vico 차트) |
| Task Detail | 예상 완료 시간 계산 |
| Settings | 알림 종류별 on/off, 방해금지 시간 |
| Remote Command | PC 종료, 절전 명령 |

### P2 (3단계)

| 화면 | 핵심 기능 |
|------|----------|
| Home Widget | Glance 기반, 단일/다중 작업 위젯 |
| History | 과거 작업 기록 열람 |

---

## 9. 접근성 (Accessibility)

| 항목 | 적용 |
|------|------|
| 콘텐츠 설명 | 모든 아이콘/이미지에 `contentDescription` |
| 터치 영역 | 최소 48dp × 48dp |
| 색상 대비 | WCAG AA 기준 4.5:1 이상 |
| 스크린 리더 | 진행바에 `semantics { stateDescription = "73% complete" }` |
| 키보드 접근 | 모든 인터랙션 요소 포커스 가능 |
| 동적 폰트 | `sp` 단위 사용, 시스템 폰트 크기 대응 |
