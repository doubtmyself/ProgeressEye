/**
 * ProgressEye Cloud Functions
 *
 * RTDB 트리거: 새 알림이 users/{uid}/alerts/{alertId}에 기록되면
 * 해당 유저의 FCM 토큰으로 데이터 메시지를 전송한다.
 */

import { initializeApp } from "firebase-admin/app";
import { getAuth } from "firebase-admin/auth";
import { getDatabase } from "firebase-admin/database";
import { getFirestore } from "firebase-admin/firestore";
import { getFunctions } from "firebase-admin/functions";
import { getMessaging } from "firebase-admin/messaging";
import * as crypto from "crypto";
import { onRequest, Request } from "firebase-functions/v2/https";
import { onDocumentWritten } from "firebase-functions/v2/firestore";
import { onValueCreated, onValueWritten } from "firebase-functions/v2/database";
import { onSchedule } from "firebase-functions/v2/scheduler";
import { onTaskDispatched, Request as TaskRequest } from "firebase-functions/v2/tasks";
import { logger } from "firebase-functions";
import type { DecodedIdToken } from "firebase-admin/auth";
import type { Response } from "express";

initializeApp();

// ─── Constants ────────────────────────────────────────────────────────────────

const CLEANUP_CONCURRENCY = 10;
const CLEANUP_REGION = "us-central1";
const CLEANUP_QUEUE_NAME = "processWithdrawalCleanup";
const TOMBSTONE_QUEUE_NAME = "processWithdrawnTombstoneCleanup";
const FIRESTORE_DB_ID = "progress";
const TOMBSTONE_BACKFILL_BATCH_SIZE = 200;

// 탈퇴 유예 기간 및 재가입 제한 기간 (ms)
const GRACE_PERIOD_MS = 7 * 24 * 60 * 60 * 1000;   // 7일
const REJOIN_BLOCK_MS = 30 * 24 * 60 * 60 * 1000;  // 30일

// Cloud Task 디스패치 데드라인 (초)
const TASK_DISPATCH_DEADLINE_SECONDS = 300;

// ─── Types ────────────────────────────────────────────────────────────────────

interface AlertData {
  type: string;
  title?: string;
  body: string;
  deviceId?: string;
  ts?: number;
}

interface FcmTokenEntry {
  token: string;
}

interface WithdrawalCleanupPayload {
  uid: string;
  deleteAt: number;
}

interface TombstoneCleanupPayload {
  uid: string;
  rejoinAllowedAt: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function toMsNumber(value: unknown): number | null {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

function computeEmailKey(email: string): string {
  const normalized = String(email || "").trim().toLowerCase();
  if (!normalized) {
    return "";
  }
  return crypto.createHash("sha256").update(normalized, "utf8").digest("hex");
}

async function verifyBearerUser(req: Request): Promise<DecodedIdToken | null> {
  const header = String(req.get("authorization") || "");
  if (!header.startsWith("Bearer ")) {
    return null;
  }
  const idToken = header.slice("Bearer ".length).trim();
  if (!idToken) {
    return null;
  }
  return getAuth().verifyIdToken(idToken);
}

function resolveEmail(decodedToken: DecodedIdToken, requestBody: Record<string, unknown>): string {
  const bodyEmail = String((requestBody && requestBody.email) || "")
    .trim()
    .toLowerCase();
  if (bodyEmail) {
    return bodyEmail;
  }
  return String(decodedToken.email || "").trim().toLowerCase();
}

function createForceLogoutPayload(): { ts: number; cmdId: string } {
  return {
    ts: Math.floor(Date.now() / 1000),
    cmdId: crypto.randomUUID(),
  };
}

async function enqueueQueueTask(
  queueName: string,
  payload: Record<string, unknown>,
  targetTimeMs: unknown,
  taskId: string,
): Promise<void> {
  const queue = getFunctions().taskQueue(queueName);
  const targetMs = toMsNumber(targetTimeMs) || Date.now();
  const delaySeconds = Math.max(0, Math.ceil((targetMs - Date.now()) / 1000));

  try {
    await queue.enqueue(payload, {
      id: taskId,
      scheduleDelaySeconds: delaySeconds,
      dispatchDeadlineSeconds: TASK_DISPATCH_DEADLINE_SECONDS,
    });
  } catch (err) {
    const errText = String(err || "");
    // Cloud Tasks는 동일 taskId가 이미 존재하면 ALREADY_EXISTS 에러를 반환한다.
    // 중복 예약은 정상 케이스이므로 조용히 무시한다.
    if (
      errText.includes("ALREADY_EXISTS") ||
      errText.toLowerCase().includes("already exists")
    ) {
      logger.info("Task already exists, skip duplicate enqueue", { queueName, taskId });
      return;
    }
    throw err;
  }
}

async function enqueueWithdrawalCleanupTask(uid: string, deleteAt: number): Promise<void> {
  const taskId = `withdrawal-cleanup-${uid}-${deleteAt}`;
  await enqueueQueueTask(CLEANUP_QUEUE_NAME, { uid, deleteAt }, deleteAt, taskId);
}

async function enqueueTombstoneCleanupTask(uid: string, rejoinAllowedAt: number): Promise<void> {
  const taskId = `withdrawn-tombstone-${uid}-${rejoinAllowedAt}`;
  await enqueueQueueTask(TOMBSTONE_QUEUE_NAME, { uid, rejoinAllowedAt }, rejoinAllowedAt, taskId);
}

// ─── Cloud Functions ──────────────────────────────────────────────────────────

/**
 * users/{uid}/alerts/{alertId}에 새 노드가 생성되면 FCM 전송.
 *
 * 알림 데이터 형식:
 *   { type, title, body, deviceId, ts }
 *
 * FCM 데이터 메시지 형식 (notification이 아닌 data-only):
 *   { type, title, body, deviceId, ts, alertId }
 */
export const onAlertCreated = onValueCreated(
  { ref: "/users/{uid}/alerts/{alertId}", region: "us-central1" },
  async (event) => {
    const uid = event.params.uid;
    const alertId = event.params.alertId;
    const alertData = event.data.val() as AlertData | null;

    if (!alertData || !alertData.type || !alertData.body) {
      logger.warn("Invalid alert data", { uid, alertId, alertData });
      return null;
    }

    logger.info("New alert", { uid, alertId, type: alertData.type });

    const db = getDatabase();
    const tokensSnapshot = await db.ref(`users/${uid}/fcmTokens`).once("value");

    if (!tokensSnapshot.exists()) {
      logger.info("No FCM tokens for user", { uid });
      return null;
    }

    const tokens: Array<{ key: string; token: string }> = [];
    tokensSnapshot.forEach((child) => {
      const tokenData = child.val() as FcmTokenEntry | null;
      if (tokenData && tokenData.token) {
        tokens.push({ key: child.key!, token: tokenData.token });
      }
    });

    if (tokens.length === 0) {
      logger.info("No valid FCM tokens", { uid });
      return null;
    }

    const fcmData: Record<string, string> = {
      type: alertData.type,
      title: alertData.title || "ProgressEye",
      body: alertData.body,
      deviceId: alertData.deviceId || "",
      ts: String(alertData.ts || Date.now()),
      alertId,
    };

    const messaging = getMessaging();
    const staleTokenKeys: string[] = [];

    await Promise.all(
      tokens.map(async ({ key, token }) => {
        try {
          await messaging.send({
            token,
            notification: { title: fcmData.title, body: fcmData.body },
            data: fcmData,
          });
          logger.info("FCM sent", { token: token.slice(-8) });
        } catch (err: unknown) {
          const code = (err as { code?: string }).code;
          if (
            code === "messaging/registration-token-not-registered" ||
            code === "messaging/invalid-registration-token"
          ) {
            logger.warn("Stale FCM token, marking for removal", { key, token: token.slice(-8) });
            staleTokenKeys.push(key);
          } else {
            logger.error("FCM send error", { key, error: String(err) });
          }
        }
      }),
    );

    if (staleTokenKeys.length > 0) {
      const updates: Record<string, null> = {};
      staleTokenKeys.forEach((key) => {
        updates[`users/${uid}/fcmTokens/${key}`] = null;
      });
      await db.ref().update(updates);
      logger.info("Removed stale tokens", { count: staleTokenKeys.length });
    }

    return null;
  },
);

/**
 * users/{uid}/deviceStatus/{deviceId} 가 "offline"으로 전환되면 FCM 알림을 보낸다.
 *
 * 커버 케이스:
 *  - PC 크래시: Android heartbeat 만료 감지 → deviceStatus 쓰기 → 트리거
 *  - PC 정상 종료: PC set_offline() → deviceStatus 쓰기 → 트리거
 */
export const onDeviceStatusOffline = onValueWritten(
  { ref: "/users/{uid}/deviceStatus/{deviceId}", region: "us-central1" },
  async (event) => {
    const uid = event.params.uid;
    const deviceId = event.params.deviceId;
    const before = event.data.before?.val() as string | null;
    const after = event.data.after?.val() as string | null;

    // "offline"으로 전환될 때만 처리 (이미 offline이면 skip)
    if (after !== "offline" || before === "offline") return null;

    logger.info("Device went offline", { uid, deviceId, before });

    const db = getDatabase();

    // 기기 이름 조회
    const nameSnap = await db.ref(`users/${uid}/devices/${deviceId}/name`).once("value");
    const deviceName = (nameSnap.val() as string | null) || deviceId;

    // alert 작성 → onAlertCreated → FCM
    const alertId = crypto.randomUUID().replace(/-/g, "").slice(0, 12);
    await db.ref(`users/${uid}/alerts/${alertId}`).set({
      type: "device_offline",
      title: deviceName,
      body: "PC 에이전트가 오프라인 상태입니다",
      deviceId,
      ts: Date.now(),
    });

    logger.info("Device offline alert written", { uid, deviceId, deviceName, alertId });
    return null;
  },
);

/**
 * 탈퇴 요청 정책 쓰기를 서버에서 일원화한다.
 * - users/{uid} 정책 필드 기록
 * - withdrawnUsers/{uid}, withdrawnEmails/{emailKey} tombstone 기록
 * - RTDB forceLogout 명령 발행
 */
export const requestWithdrawal = onRequest(
  { region: CLEANUP_REGION, cors: true },
  async (req: Request, res: Response) => {
    if (req.method !== "POST") {
      res.status(405).json({ ok: false, error: "method_not_allowed" });
      return;
    }

    try {
      const decoded = await verifyBearerUser(req);
      if (!decoded || !decoded.uid) {
        res.status(401).json({ ok: false, error: "unauthorized" });
        return;
      }

      const uid = decoded.uid;
      const now = Date.now();
      const deleteAt = now + GRACE_PERIOD_MS;
      const rejoinAllowedAt = now + REJOIN_BLOCK_MS;
      const emailLower = resolveEmail(decoded, (req.body as Record<string, unknown>) || {});
      const emailKey = computeEmailKey(emailLower);

      const db = getFirestore(FIRESTORE_DB_ID);
      const rtdb = getDatabase();

      await db.collection("users").doc(uid).set(
        {
          withdrawalStatus: "pending",
          deleteAt,
          rejoinAllowedAt,
          ...(emailLower ? { emailLower } : {}),
          ...(emailKey ? { withdrawalEmailKey: emailKey } : {}),
        },
        { merge: true },
      );

      await db.collection("withdrawnUsers").doc(uid).set(
        { rejoinAllowedAt, ...(emailKey ? { emailKey } : {}) },
        { merge: true },
      );

      if (emailKey) {
        await db.collection("withdrawnEmails").doc(emailKey).set(
          { rejoinAllowedAt, uid },
          { merge: true },
        );
      }

      await rtdb.ref(`users/${uid}/commands/forceLogout`).set(createForceLogoutPayload());

      res.status(200).json({ ok: true, deleteAt, rejoinAllowedAt });
    } catch (err) {
      logger.error("requestWithdrawal failed", { error: String(err) });
      res.status(500).json({ ok: false, error: "internal_error" });
    }
  },
);

/**
 * 탈퇴 취소 정책 쓰기를 서버에서 일원화한다.
 * - users/{uid} active 복원
 * - withdrawnUsers/withdrawnEmails tombstone 삭제
 */
export const cancelWithdrawal = onRequest(
  { region: CLEANUP_REGION, cors: true },
  async (req: Request, res: Response) => {
    if (req.method !== "POST") {
      res.status(405).json({ ok: false, error: "method_not_allowed" });
      return;
    }

    try {
      const decoded = await verifyBearerUser(req);
      if (!decoded || !decoded.uid) {
        res.status(401).json({ ok: false, error: "unauthorized" });
        return;
      }

      const uid = decoded.uid;
      const db = getFirestore(FIRESTORE_DB_ID);
      const rtdb = getDatabase();
      const userRef = db.collection("users").doc(uid);
      const userSnap = await userRef.get();
      const userData = userSnap.exists ? userSnap.data() ?? {} : {};
      const emailLower = String(
        userData["emailLower"] || resolveEmail(decoded, (req.body as Record<string, unknown>) || {}) || "",
      ).trim().toLowerCase();
      const emailKey = String(userData["withdrawalEmailKey"] || computeEmailKey(emailLower));

      await userRef.set(
        { withdrawalStatus: "active", deleteAt: null, rejoinAllowedAt: null, withdrawalEmailKey: null },
        { merge: true },
      );

      await db.collection("withdrawnUsers").doc(uid).delete();

      if (emailKey) {
        await db.collection("withdrawnEmails").doc(emailKey).delete();
      }

      try {
        await rtdb.ref(`users/${uid}/commands/forceLogout`).remove();
      } catch (err) {
        logger.warn("cancelWithdrawal forceLogout cleanup failed", { uid, error: String(err) });
      }

      res.status(200).json({ ok: true });
    } catch (err) {
      logger.error("cancelWithdrawal failed", { error: String(err) });
      res.status(500).json({ ok: false, error: "internal_error" });
    }
  },
);

/**
 * users/{uid} 탈퇴 상태 전환 감지 → 탈퇴 데이터 삭제 작업을 Cloud Tasks에 예약.
 */
export const onUserWithdrawalChanged = onDocumentWritten(
  { document: "users/{uid}", region: CLEANUP_REGION, database: "progress" },
  async (event) => {
    const uid = event.params.uid;
    if (!event.data) return null;
    const beforeExists = Boolean(event.data.before && event.data.before.exists);
    const afterExists = Boolean(event.data.after && event.data.after.exists);

    if (!afterExists) return null;

    const beforeData = beforeExists ? event.data.before.data() ?? {} : {};
    const afterData = event.data.after.data() ?? {};

    const beforeStatus = (beforeData["withdrawalStatus"] as string) || "";
    const afterStatus = (afterData["withdrawalStatus"] as string) || "";
    const beforeDeleteAt = toMsNumber(beforeData["deleteAt"]);
    const afterDeleteAt = toMsNumber(afterData["deleteAt"]);

    if (afterStatus !== "pending" || !afterDeleteAt) return null;
    if (beforeStatus === "pending" && beforeDeleteAt === afterDeleteAt) return null;

    await enqueueWithdrawalCleanupTask(uid, afterDeleteAt);
    logger.info("Withdrawal cleanup task enqueued", { uid, deleteAt: afterDeleteAt });
    return null;
  },
);

/**
 * withdrawnUsers/{uid} 변경 감지 → tombstone 정리 작업을 Cloud Tasks에 예약.
 *
 * 디버그/레거시 경로에서 users 문서 변경 없이 withdrawnUsers만 갱신되는 경우를 커버한다.
 */
export const onWithdrawnUserChanged = onDocumentWritten(
  { document: "withdrawnUsers/{uid}", region: CLEANUP_REGION, database: FIRESTORE_DB_ID },
  async (event) => {
    const uid = event.params.uid;
    if (!event.data) return null;
    const afterExists = Boolean(event.data.after && event.data.after.exists);
    if (!afterExists) return null;

    const afterData = event.data.after.data() ?? {};
    const rejoinAllowedAt = toMsNumber(afterData["rejoinAllowedAt"]);
    if (!rejoinAllowedAt) return null;

    await enqueueTombstoneCleanupTask(uid, rejoinAllowedAt);
    logger.info("Tombstone cleanup task enqueued from withdrawnUsers change", { uid, rejoinAllowedAt });
    return null;
  },
);

/**
 * 탈퇴 유예 만료 사용자 삭제 작업.
 * - users/{uid}가 아직 pending이고 deleteAt이 만료됐을 때만 삭제 진행
 * - 작업 완료 후 withdrawnUsers tombstone 정리 작업을 별도 예약
 */
export const processWithdrawalCleanup = onTaskDispatched<WithdrawalCleanupPayload>(
  {
    region: CLEANUP_REGION,
    retryConfig: { maxAttempts: 10, minBackoffSeconds: 30, maxBackoffSeconds: 3600, maxDoublings: 5 },
    rateLimits: { maxConcurrentDispatches: CLEANUP_CONCURRENCY, maxDispatchesPerSecond: 5 },
  },
  async (request: TaskRequest<WithdrawalCleanupPayload>) => {
    const now = Date.now();
    const uid = request.data?.uid;

    if (!uid || typeof uid !== "string") {
      logger.warn("Invalid cleanup task payload", { data: request.data ?? null });
      return;
    }

    const db = getFirestore(FIRESTORE_DB_ID);
    const rtdb = getDatabase();
    const auth = getAuth();
    const userRef = db.collection("users").doc(uid);
    const userSnap = await userRef.get();

    if (!userSnap.exists) {
      logger.info("Cleanup skipped: users doc not found", { uid });
      return;
    }

    const data = userSnap.data() ?? {};
    const withdrawalStatus = (data["withdrawalStatus"] as string) || "";
    const deleteAt = toMsNumber(data["deleteAt"]);
    const rejoinAllowedAt = toMsNumber(data["rejoinAllowedAt"]) || now;
    const emailLower = String(data["emailLower"] || data["email"] || "").trim().toLowerCase();
    const emailKey = String(data["withdrawalEmailKey"] || computeEmailKey(emailLower));

    if (withdrawalStatus !== "pending") {
      logger.info("Cleanup skipped: status is not pending", { uid, withdrawalStatus });
      return;
    }

    if (!deleteAt) {
      logger.warn("Cleanup skipped: invalid deleteAt", { uid, deleteAt: data["deleteAt"] });
      return;
    }

    if (deleteAt > now) {
      await enqueueWithdrawalCleanupTask(uid, deleteAt);
      logger.info("Cleanup rescheduled: deleteAt not reached", { uid, deleteAt });
      return;
    }

    try {
      await rtdb.ref(`users/${uid}`).remove();
    } catch (err) {
      logger.warn("RTDB user remove failed", { uid, error: String(err) });
    }

    try {
      await userRef.delete();
    } catch (err) {
      logger.warn("Firestore users doc delete failed", { uid, error: String(err) });
    }

    try {
      await db.collection("withdrawnUsers").doc(uid).set(
        { deletedAt: now, rejoinAllowedAt, ...(emailKey ? { emailKey } : {}) },
        { merge: true },
      );
    } catch (err) {
      logger.warn("withdrawnUsers tombstone upsert failed", { uid, error: String(err) });
    }

    if (emailKey) {
      try {
        await db.collection("withdrawnEmails").doc(emailKey).set(
          { rejoinAllowedAt, uid },
          { merge: true },
        );
      } catch (err) {
        logger.warn("withdrawnEmails upsert failed", { uid, emailKey, error: String(err) });
      }
    }

    try {
      await auth.deleteUser(uid);
    } catch (err) {
      const code = (err as { code?: string }).code;
      if (code !== "auth/user-not-found") {
        logger.warn("Auth user delete failed", { uid, error: String(err) });
      }
    }

    await enqueueTombstoneCleanupTask(uid, rejoinAllowedAt);
    logger.info("Withdrawal cleanup completed", { uid, rejoinAllowedAt, scheduledTombstoneCleanup: true });
  },
);

/**
 * 재가입 제한 기간 만료 시 withdrawnUsers tombstone 삭제.
 */
export const processWithdrawnTombstoneCleanup = onTaskDispatched<TombstoneCleanupPayload>(
  {
    region: CLEANUP_REGION,
    retryConfig: { maxAttempts: 10, minBackoffSeconds: 60, maxBackoffSeconds: 3600, maxDoublings: 5 },
    rateLimits: { maxConcurrentDispatches: CLEANUP_CONCURRENCY, maxDispatchesPerSecond: 5 },
  },
  async (request: TaskRequest<TombstoneCleanupPayload>) => {
    const now = Date.now();
    const uid = request.data?.uid;

    if (!uid || typeof uid !== "string") {
      logger.warn("Invalid tombstone cleanup payload", { data: request.data ?? null });
      return;
    }

    const db = getFirestore(FIRESTORE_DB_ID);
    const tombRef = db.collection("withdrawnUsers").doc(uid);
    const tombSnap = await tombRef.get();

    if (!tombSnap.exists) {
      logger.info("Tombstone cleanup skipped: doc not found", { uid });
      return;
    }

    const tombData = tombSnap.data() ?? {};
    const rejoinAllowedAt = toMsNumber(tombData["rejoinAllowedAt"]);
    const emailKey = String(tombData["emailKey"] || "").trim();

    if (!rejoinAllowedAt) {
      logger.warn("Tombstone cleanup skipped: invalid rejoinAllowedAt", {
        uid,
        rejoinAllowedAt: tombData["rejoinAllowedAt"],
      });
      return;
    }

    if (rejoinAllowedAt > now) {
      await enqueueTombstoneCleanupTask(uid, rejoinAllowedAt);
      logger.info("Tombstone cleanup rescheduled", { uid, rejoinAllowedAt });
      return;
    }

    await tombRef.delete();
    if (emailKey) {
      try {
        await db.collection("withdrawnEmails").doc(emailKey).delete();
      } catch (err) {
        logger.warn("withdrawnEmails delete failed", { uid, emailKey, error: String(err) });
      }
    }
    logger.info("Tombstone cleanup completed", { uid });
  },
);

/**
 * 누락된 withdrawnUsers tombstone 백필 예약 스케줄러.
 *
 * 이벤트 트리거 누락/배포 공백 기간에 쌓인 만료 tombstone을 주기적으로 재수집한다.
 */
export const backfillWithdrawnTombstoneCleanup = onSchedule(
  { schedule: "every 24 hours", region: CLEANUP_REGION, timeZone: "Asia/Seoul", maxInstances: 1 },
  async () => {
    const now = Date.now();
    const db = getFirestore(FIRESTORE_DB_ID);

    const dueTombs = await db
      .collection("withdrawnUsers")
      .where("rejoinAllowedAt", "<=", now)
      .limit(TOMBSTONE_BACKFILL_BATCH_SIZE)
      .get();

    let enqueued = 0;
    for (const doc of dueTombs.docs) {
      const data = doc.data() ?? {};
      const rejoinAllowedAt = toMsNumber(data["rejoinAllowedAt"]) || now;
      await enqueueTombstoneCleanupTask(doc.id, rejoinAllowedAt);
      enqueued += 1;
    }

    logger.info("backfillWithdrawnTombstoneCleanup completed", {
      scanned: dueTombs.size,
      enqueued,
      hasMore: dueTombs.size === TOMBSTONE_BACKFILL_BATCH_SIZE,
      now,
    });
  },
);
