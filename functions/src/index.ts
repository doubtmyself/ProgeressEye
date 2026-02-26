/**
 * ProgressEye Cloud Functions
 *
 * 1. checkHeartbeats — 3분마다 실행, 하트비트 만료 기기 오프라인 처리 + FCM 푸시
 * 2. onTaskStatusChange — RTDB 태스크 상태 변경 시 완료/프리징 FCM 푸시
 */

import * as admin from "firebase-admin";
import { onSchedule } from "firebase-functions/v2/scheduler";
import { onValueWritten } from "firebase-functions/v2/database";

admin.initializeApp();

const db = admin.database();
const messaging = admin.messaging();

// ── 상수 ────────────────────────────────────────────────

/** 하트비트 만료 기준 (3분) */
const HEARTBEAT_TIMEOUT_MS = 3 * 60 * 1000;

// ── 유틸 ────────────────────────────────────────────────

/**
 * 유저의 FCM 토큰 목록을 조회한다.
 * RTDB 경로: users/{uid}/fcmTokens/{token}: true
 */
async function getFcmTokens(uid: string): Promise<string[]> {
  const snap = await db.ref(`users/${uid}/fcmTokens`).once("value");
  if (!snap.exists()) return [];
  const data = snap.val() as Record<string, unknown>;
  return Object.keys(data);
}

/**
 * FCM data-only 메시지를 전송한다 (알림 없이 앱이 조용히 처리).
 * 만료된 토큰은 자동 삭제한다.
 */
async function sendDataMessage(
  uid: string,
  tokens: string[],
  data: Record<string, string>,
): Promise<void> {
  if (tokens.length === 0) return;

  const response = await messaging.sendEachForMulticast({
    tokens,
    data,
    // notification 필드 없음 → data-only → 시스템 알림 없음
    android: { priority: "high" },
  });

  // 만료/무효 토큰 정리
  const tokensToRemove: string[] = [];
  response.responses.forEach((resp, idx) => {
    if (resp.error) {
      const code = resp.error.code;
      if (
        code === "messaging/invalid-registration-token" ||
        code === "messaging/registration-token-not-registered"
      ) {
        tokensToRemove.push(tokens[idx]);
      }
    }
  });

  if (tokensToRemove.length > 0) {
    const updates: Record<string, null> = {};
    for (const token of tokensToRemove) {
      updates[`users/${uid}/fcmTokens/${token}`] = null;
    }
    await db.ref().update(updates);
  }
}

// ═══════════════════════════════════════════════════════
// 1. checkHeartbeats — 스케줄 함수 (3분마다)
// ═══════════════════════════════════════════════════════

export const checkHeartbeats = onSchedule(
  { schedule: "every 3 minutes", region: "asia-northeast3" },
  async () => {
    const now = Date.now();
    const usersSnap = await db.ref("users").once("value");
    if (!usersSnap.exists()) return;

    const users = usersSnap.val() as Record<string, Record<string, unknown>>;

    for (const [uid, userData] of Object.entries(users)) {
      const heartbeat = userData.heartbeat as
        | Record<string, number>
        | undefined;
      const devices = userData.devices as
        | Record<string, Record<string, unknown>>
        | undefined;

      if (!heartbeat || !devices) continue;

      for (const [deviceId, lastTs] of Object.entries(heartbeat)) {
        if (typeof lastTs !== "number" || lastTs <= 0) continue;

        const device = devices[deviceId];
        if (!device) continue;

        const elapsed = now - lastTs;
        const currentStatus = device.status as string | undefined;

        // 하트비트 만료 + 아직 online → offline 처리
        if (elapsed > HEARTBEAT_TIMEOUT_MS && currentStatus !== "offline") {
          await db.ref(`users/${uid}/devices/${deviceId}/status`).set("offline");

          const tokens = await getFcmTokens(uid);
          await sendDataMessage(uid, tokens, {
            type: "device_offline",
            deviceId,
          });

          console.log(`Device ${deviceId} marked offline (user: ${uid})`);
        }
      }
    }
  },
);

// ═══════════════════════════════════════════════════════
// 2. onTaskStatusChange — RTDB 트리거
//    경로: users/{uid}/devices/{deviceId}/tasks/{taskId}/s
// ═══════════════════════════════════════════════════════

export const onTaskStatusChange = onValueWritten(
  {
    ref: "users/{uid}/devices/{deviceId}/tasks/{taskId}/s",
    region: "asia-northeast3",
  },
  async (event) => {
    const before = event.data.before.val() as string | null;
    const after = event.data.after.val() as string | null;

    // 변경 없으면 무시
    if (before === after) return;
    // 삭제된 경우 무시
    if (after === null) return;

    const uid = event.params.uid;
    const deviceId = event.params.deviceId;
    const taskId = event.params.taskId;

    // 완료(c) 또는 프리징(f) 상태일 때만 푸시
    if (after !== "c" && after !== "f") return;

    // 태스크 라벨 조회
    const labelSnap = await db
      .ref(`users/${uid}/devices/${deviceId}/tasks/${taskId}/l`)
      .once("value");
    const label = (labelSnap.val() as string) || taskId;

    const tokens = await getFcmTokens(uid);
    await sendDataMessage(uid, tokens, {
      type: after === "c" ? "task_completed" : "task_frozen",
      deviceId,
      taskId,
      label,
    });

    console.log(
      `Task ${taskId} → ${after} (user: ${uid}, device: ${deviceId})`,
    );
  },
);
