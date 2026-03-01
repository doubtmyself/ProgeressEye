# 백엔드 배포 가이드

## 목적
Firebase Functions/Rules/전체 배포 명령을 문서화한다.

## 사전 준비

```bash
npm install -g firebase-tools
firebase login
```

프로젝트 루트: `C:\ProgressEye`

## Functions 배포

```bash
firebase deploy --only functions --project progresseye-49244
```

## RTDB Rules 배포

```bash
firebase deploy --only database --project progresseye-49244
```

## Firestore Rules 배포

```bash
firebase deploy --only firestore:rules --project progresseye-49244
```

## 전체 배포

```bash
firebase deploy --project progresseye-49244
```

## 배포 확인

```bash
firebase functions:list
firebase functions:log
```
