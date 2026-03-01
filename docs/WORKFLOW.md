# 문서 작업 워크플로우

## 기본 원칙

1. 작업 시작 시 `docs/INDEX.md`를 가장 먼저 읽는다.
2. 플랫폼 인덱스로 이동해 관련 항목 문서를 확인한다.
3. 항목 문서에서 지정한 코드/설계 문서를 기준으로 수정한다.
4. 문서는 `docs/`만 공식 소스로 관리하고, 루트/서브 디렉터리의 별도 README/임시 문서는 유지하지 않는다.

## 플랫폼별 인덱스

- PC: `docs/pc-agent/INDEX.md`
- 모바일: `docs/mobile-app/INDEX.md`
- 백엔드: `docs/backend/INDEX.md`

## 업데이트 규칙

- 새 기능을 추가하면 아래를 함께 업데이트한다.
  - 해당 플랫폼 `topics/*.md`
  - 해당 플랫폼 `INDEX.md`
  - 정책 변경 시 `docs/privacy-policy-ko.md`
