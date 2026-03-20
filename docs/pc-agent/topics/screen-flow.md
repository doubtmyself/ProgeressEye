# PC Agent — 화면 전환 흐름도

## 페이지 구조

`MainWindow._root_layout`(QVBoxLayout)에 모든 페이지가 형제 위젯으로 쌓여 있다.
`_hide_all_pages()`로 전부 숨긴 뒤 대상 페이지 하나만 show()한다.

```
_root_layout
├── _login_panel          ← 로그인 화면 (set_login_mode)
├── _settings_overlay     ← 설정 페이지 (set_settings_mode)
│                            welcome_mode=True 일 때 step 0 역할도 겸함
├── _tutorial_page        ← 온보딩 step 1: 사용법 안내 (set_tutorial_mode)
├── _welcome_page         ← 온보딩 step 2: 간격/동결 설정 (set_welcome_mode)
└── _app_container        ← 메인 모니터링 화면 (기본 상태)
```

> 동시에 보이는 페이지는 항상 1개. 다른 페이지로 전환할 때 반드시 `_hide_all_pages()` 먼저 호출.

---

## 1. 앱 시작 흐름

```
앱 시작
  │
  ├─ Firestore appConfig/pc.minVersion 조회
  │     ├─ 현재 버전 >= 최소 버전 ──→ 계속
  │     └─ 현재 버전 < 최소 버전  ──→ [업데이트 필요 다이얼로그] → 앱 종료
  │
  ├─ _try_auto_login()
  │     ├─ 성공 (keyring 토큰 유효) ──────────────────────────┐
  │     │     └─ 탈퇴 게이트 체크 (_handle_withdrawal_gate)    │
  │     │           ├─ 정상 → _init_firebase() ───────────────┤
  │     │           └─ 탈퇴/재가입 제한 → 토큰 삭제 → 자동로그인 실패로 처리
  │     │
  │     └─ 실패 (토큰 없음 / 만료)
  │           └─ MainWindow.show() + set_login_mode(True)
  │                 └─ _ensure_login() ← 로그인 루프 (아래 §2 참조)
  │
  ├─ is_first (config에 uid 없었음)?
  │     ├─ YES → _show_welcome() ← 온보딩 플로우 (아래 §3 참조)
  │     └─ NO  → 계속
  │
  ├─ MainWindow.show()
  ├─ RapidOCR PaddleOCR 런타임 안내 (필요 시 1회)
  └─ [메인 화면 — _app_container]
```

---

## 2. 로그인 루프 (`_ensure_login`)

```
[로그인 화면 — _login_panel]
  │
  ├─ 사용자가 "로그인 시작" 클릭
  │     └─ _do_login()
  │           ├─ GoogleOAuth 브라우저 팝업 → id_token 획득
  │           ├─ Firebase signInWithIdp → uid 획득
  │           ├─ 탈퇴 게이트 체크 (_handle_withdrawal_gate)
  │           │     ├─ 탈퇴 유예 중  → 탈퇴 취소 확인 다이얼로그
  │           │     │     ├─ 취소 선택 → cancelWithdrawal API → 계속
  │           │     │     └─ 유지 선택 → 토큰 삭제 → 로그인 화면 유지
  │           │     └─ 재가입 제한 기간 → 에러 메시지 → 로그인 화면 유지
  │           ├─ _init_firebase() → keyring 저장
  │           └─ set_login_mode(False) → [메인 화면]
  │
  ├─ AuthError 발생 → set_login_mode(True, error) → 루프 재시도
  │
  └─ 사용자가 "취소" 클릭
        └─ _silent_auth_abort = True → 앱 종료
```

---

## 3. 온보딩 플로우 (최초 로그인 시)

3단계 페이지를 순서대로 표시한다. 각 단계는 독립 페이지 위젯이다.

```
[Step 0 — SettingsOverlay (welcome_mode=True)]
  언어 선택 (한국어 / English)
  │
  "다음" 클릭 → welcome_next_requested 시그널
    └─ _on_welcome_next(language)
          ├─ _pending_welcome_language = language 저장
          └─ set_tutorial_mode(True)

          ↓

[Step 1 — TutorialPage]
  3단계 사용법 안내
  ① 진행률 바 또는 수치 추가
  ② 모니터링 시작
  ③ 모바일 앱으로 확인
  │
  "다음" 클릭 → tutorial_next_requested 시그널
    └─ _on_tutorial_next()
          └─ show_welcome_page(interval, freeze, language)
               └─ set_welcome_mode(True)

               ↓

[Step 2 — WelcomePage]
  모니터링 간격 설정 (SpinBox)
  멈춤 감지 시간 설정 (SpinBox)
  시스템 절전 방지 안내
  │
  "시작하기" 클릭 → started 시그널
    └─ set_welcome_mode(False) → [메인 화면 — _app_container]
```

---

## 4. 설정 화면 전환

```
[메인 화면 — _app_container]
  │
  ⚙️ 설정 버튼 클릭 → show_settings() → set_settings_mode(True)

  ↓

[설정 화면 — _settings_overlay]
  │
  ├─ 저장(saved) / 닫기(closed)
  │     └─ set_settings_mode(False) → [메인 화면]
  │
  ├─ 로그아웃(logout_requested)
  │     └─ set_settings_mode(False) → _do_logout() (§5 참조)
  │
  ├─ 계정 삭제(delete_account_requested)
  │     └─ set_settings_mode(False) → _do_delete_account() → _do_logout()
  │
  └─ [DEBUG] 설정 초기화(reset_settings_requested)
        └─ _do_reset_settings() (§6 참조)
```

---

## 5. 로그아웃 흐름 (`_do_logout`)

```
로그아웃 시작
  │
  ├─ 모니터링 중이면 스케줄러 정지
  ├─ 하트비트 타이머 정지
  ├─ CommandListener 정지
  ├─ Firebase 정리 (별도 스레드: clear_active_device, set_offline)
  ├─ 토큰 삭제 (keyring)
  ├─ config uid/email 초기화
  ├─ error_reporter.reset()
  └─ set_login_mode(True) → _ensure_login() ← 로그인 루프 재진입 (§2)
```

---

## 6. 설정 초기화 흐름 (DEBUG)

```
[DEBUG] 설정 초기화 클릭
  │
  ├─ config.json 파일 삭제  ← 반드시 _do_logout() 전에 삭제
  ├─ _do_logout()
  │     └─ set_login_mode(True) → _ensure_login()
  │           └─ 로그인 성공 후 is_first=True
  │                 └─ _show_welcome() → 온보딩 플로우 재시작 (§3)
  └─ (끝)
```

> **주의**: config.json을 `_do_logout()` 후에 삭제하면, 로그인 성공 시 새로 생성된
> config.json이 삭제되어 온보딩이 트리거되지 않는다.

---

## 7. 외부 이벤트로 인한 강제 전환

```
forceLogout 명령 수신 (RTDB SSE)
  └─ _do_logout() → 로그인 화면

탈퇴 완료 감지 (withdrawalStatus == "completed")
  └─ _do_logout() → 로그인 화면

버전 미달 (앱 실행 중 체크 없음, 시작 시에만 체크)
  └─ 업데이트 다이얼로그 → 앱 종료
```

---

## 8. 페이지 전환 메서드 요약

| 메서드 | 표시되는 페이지 |
|--------|----------------|
| `set_login_mode(True)` | `_login_panel` |
| `set_login_mode(False)` | `_app_container` |
| `set_settings_mode(True)` | `_settings_overlay` |
| `set_settings_mode(False)` | `_app_container` |
| `set_tutorial_mode(True)` | `_tutorial_page` |
| `set_tutorial_mode(False)` | `_app_container` |
| `set_welcome_mode(True)` | `_welcome_page` |
| `set_welcome_mode(False)` | `_app_container` |
| `show_settings(welcome_mode=True)` | `_settings_overlay` (step 0용) |

> 모든 `set_*_mode(True)`는 내부에서 `_hide_all_pages()` 호출 후 해당 페이지만 show().
