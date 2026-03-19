# 광고 동의 흐름 (Ad Consent Flow)

> 최종 업데이트: 2026-03-19
> 관련 커밋: `a76dfab`, `f03db42`

---

## 개요

ProgressEye Android 앱은 UMP (User Messaging Platform) SDK 3.x를 사용해 GDPR(EEA)·CCPA/MSPA(미국) 규정을 준수한다.
**맞춤형 광고 동의 없이는 Pro 구독을 유도**하는 "Consent or Pay" 모델을 채택한다.

---

## 지역별 동의 흐름

### EEA (유럽)

```
앱 최초 실행
  └─ loadAndShowConsentFormIfRequired → GDPR 동의 폼 표시
        ├─ 맞춤형 광고 동의 → initMobileAds() [리워드 1시간]
        ├─ 비맞춤형 선택 / X 버튼 → Pro 구독 유도 다이얼로그
        │     ├─ "동의하기" → reset() + 폼 재표시
        │     └─ "Pro 구독" → KEY_ADS_CONSENTED=false, 광고 미초기화
        └─ 완전 거부 (canRequestAds=false) → Pro 구독 유도 다이얼로그

설정 > 광고 개인정보 설정 (showPrivacyOptionsForm)
  └─ 비맞춤형으로 변경 시 → Pro 구독 유도 다이얼로그
```

**맞춤형 광고 판정**: `IABTCF_PurposeConsents[3] == '1'` (TCF v2 Purpose 4)

### 미국 (US State Regulations)

```
앱 최초 실행
  └─ loadAndShowConsentFormIfRequired → MSPA 동의 폼 표시
        ├─ 동의 (기본값) → initMobileAds() [리워드 1시간]
        └─ 완전 거부 (Don't sell or share) → Pro 구독 유도 다이얼로그
              ├─ "동의하기" → onShowPrivacyOptions() (US 폼 재표시)
              └─ "Pro 구독" → KEY_ADS_CONSENTED=false

설정 > 광고 개인정보 설정 (showPrivacyOptionsForm)
  └─ Manage options 개별 조정 가능 (Pro 유도 없음)
     └─ 이유: Confirm choices 시 오발동 문제로 설정 화면에서는 비차단
```

**완전 거부 판정**: GPP 섹션 문자열 Base64 디코딩
- `SaleOptOut` (bits 18-19) == 1 **AND**
- `SharingOptOut` (bits 20-21) == 1 **AND**
- `TargetedAdvertisingOptOut` (bits 22-23) == 1

> Manage options 부분 거부는 세 필드 중 일부만 1이므로 조건 불충족 → 유도 없음

### 기타 지역

`isPersonalizedAdsConsented()` → 항상 `true` → `initMobileAds()` (맞춤형)

---

## 리워드 광고 게이트

```
showRewardedAdThen() 호출
  ├─ shouldSkipRewardedAds() (Pro/패스 보유) → 바로 실행
  ├─ KEY_ADS_CONSENTED == false → _showSubscribeDialog = true
  ├─ KEY_IS_PERSONALIZED_ADS == false → _showSubscribeDialog = true
  └─ 정상 → 리워드 광고 표시 → 시청 완료 → 1시간 패스 부여
```

| 상태 | 리워드 |
|---|---|
| 맞춤형 광고 동의 | 광고 시청 후 1시간 ad-free pass |
| 비맞춤형 / 동의 없음 | 없음 → Pro 구독 유도 |

---

## SharedPreferences 키 (`dashboard_prefs`)

| 키 | 타입 | 설명 |
|---|---|---|
| `ads_consented` | Boolean | 광고 초기화 허용 여부 |
| `is_personalized_ads` | Boolean | 맞춤형 광고 여부 |
| `ad_free_until_ms` | Long | ad-free 패스 만료 시각 (epoch ms) |

---

## 주요 함수 (`MainActivity.kt`)

| 함수 | 설명 |
|---|---|
| `requestConsentAndInitAds()` | UMP 동의 요청 진입점. 앱 시작 시 호출 |
| `handleConsentResult()` | 동의 폼 닫힌 후 결과 처리 |
| `showConsentRequiredDialog()` | Pro 구독 유도 다이얼로그 표시 |
| `onShowPrivacyOptions()` | 설정 화면 광고 개인정보 설정 버튼 핸들러 |
| `initMobileAds()` | MobileAds 초기화 + SharedPrefs 저장 |
| `isPersonalizedAdsConsented()` | 지역별 맞춤형 광고 동의 여부 반환 |
| `isGppUsSectionOptedOut()` | GPP 섹션 문자열 디코딩 (US 완전 거부 판정) |
| `isEeaRegion()` | `IABTCF_gdprApplies == 1` 여부 |

---

## 디버그 지역 전환 (`requestConsentAndInitAds`)

```kotlin
val debugGeography = ConsentDebugSettings.DebugGeography.DEBUG_GEOGRAPHY_EEA
// DEBUG_GEOGRAPHY_EEA              → 유럽 시뮬레이션
// DEBUG_GEOGRAPHY_REGULATED_US_STATE → 미국 시뮬레이션
// DEBUG_GEOGRAPHY_OTHER            → 기타 (광고 바로 표시)
```

폼 강제 재표시: `// consentInformation.reset()` 주석 해제
