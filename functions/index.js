/**
 * ProgressEye Cloud Functions
 *
 * RTDB 트리거: 새 알림이 users/{uid}/alerts/{alertId}에 기록되면
 * 해당 유저의 FCM 토큰으로 데이터 메시지를 전송한다.
 */

const { initializeApp } = require("firebase-admin/app");
const { getAuth } = require("firebase-admin/auth");
const { getDatabase } = require("firebase-admin/database");
const { getFirestore } = require("firebase-admin/firestore");
const { getFunctions } = require("firebase-admin/functions");
const { getMessaging } = require("firebase-admin/messaging");
const crypto = require("crypto");
const { onRequest } = require("firebase-functions/v2/https");
const { onDocumentWritten } = require("firebase-functions/v2/firestore");
const { onValueCreated } = require("firebase-functions/v2/database");
const { onSchedule } = require("firebase-functions/v2/scheduler");
const { onTaskDispatched } = require("firebase-functions/v2/tasks");
const { logger } = require("firebase-functions");

initializeApp();

const CLEANUP_CONCURRENCY = 10;
const CLEANUP_REGION = "us-central1";
const CLEANUP_QUEUE_NAME = "processWithdrawalCleanup";
const TOMBSTONE_QUEUE_NAME = "processWithdrawnTombstoneCleanup";
const FIRESTORE_DB_ID = "progress";
const TOMBSTONE_BACKFILL_BATCH_SIZE = 200;

function toMsNumber(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

function computeEmailKey(email) {
  const normalized = String(email || "").trim().toLowerCase();
  if (!normalized) {
    return "";
  }
  return crypto.createHash("sha256").update(normalized, "utf8").digest("hex");
}

async function verifyBearerUser(req) {
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

function resolveEmail(decodedToken, requestBody) {
  const bodyEmail = String((requestBody && requestBody.email) || "")
    .trim()
    .toLowerCase();
  if (bodyEmail) {
    return bodyEmail;
  }
  return String(decodedToken.email || "").trim().toLowerCase();
}

function createForceLogoutPayload() {
  return {
    ts: Math.floor(Date.now() / 1000),
    cmdId: crypto.randomUUID(),
  };
}

async function enqueueQueueTask(queueName, payload, targetTimeMs, taskId) {
  const queue = getFunctions().taskQueue(queueName);
  const targetMs = toMsNumber(targetTimeMs) || Date.now();
  const delaySeconds = Math.max(0, Math.ceil((targetMs - Date.now()) / 1000));

  try {
    await queue.enqueue(payload, {
      id: taskId,
      scheduleDelaySeconds: delaySeconds,
      dispatchDeadlineSeconds: 300,
    });
  } catch (err) {
    const errText = String(err || "");
    if (
      errText.includes("ALREADY_EXISTS") ||
      errText.toLowerCase().includes("already exists")
    ) {
      logger.info("Task already exists, skip duplicate enqueue", {
        queueName,
        taskId,
      });
      return;
    }
    throw err;
  }
}

async function enqueueWithdrawalCleanupTask(uid, deleteAt) {
  const taskId = `withdrawal-cleanup-${uid}-${deleteAt}`;
  await enqueueQueueTask(CLEANUP_QUEUE_NAME, { uid, deleteAt }, deleteAt, taskId);
}

async function enqueueTombstoneCleanupTask(uid, rejoinAllowedAt) {
  const taskId = `withdrawn-tombstone-${uid}-${rejoinAllowedAt}`;
  await enqueueQueueTask(
    TOMBSTONE_QUEUE_NAME,
    { uid, rejoinAllowedAt },
    rejoinAllowedAt,
    taskId
  );
}

/**
 * users/{uid}/alerts/{alertId}에 새 노드가 생성되면 FCM 전송.
 *
 * 알림 데이터 형식:
 *   { type, title, body, deviceId, ts }
 *
 * FCM 데이터 메시지 형식 (notification이 아닌 data-only):
 *   { type, title, body, deviceId, ts, alertId }
 */
exports.onAlertCreated = onValueCreated(
  {
    ref: "/users/{uid}/alerts/{alertId}",
    region: "us-central1",
  },
  async (event) => {
    const uid = event.params.uid;
    const alertId = event.params.alertId;
    const alertData = event.data.val();

    if (!alertData || !alertData.type || !alertData.body) {
      logger.warn("Invalid alert data", { uid, alertId, alertData });
      return null;
    }

    logger.info("New alert", {
      uid,
      alertId,
      type: alertData.type,
    });

    // 유저의 FCM 토큰 조회
    const db = getDatabase();
    const tokensSnapshot = await db
      .ref(`users/${uid}/fcmTokens`)
      .once("value");

    if (!tokensSnapshot.exists()) {
      logger.info("No FCM tokens for user", { uid });
      return null;
    }

    const tokens = [];
    tokensSnapshot.forEach((child) => {
      const tokenData = child.val();
      if (tokenData && tokenData.token) {
        tokens.push({ key: child.key, token: tokenData.token });
      }
    });

    if (tokens.length === 0) {
      logger.info("No valid FCM tokens", { uid });
      return null;
    }

    // FCM 데이터 메시지 구성 (notification 필드 없음 — 앱에서 직접 처리)
    const fcmData = {
      type: alertData.type,
      title: alertData.title || "ProgressEye",
      body: alertData.body,
      deviceId: alertData.deviceId || "",
      ts: String(alertData.ts || Date.now()),
      alertId: alertId,
    };

    // 각 토큰에 전송
    const messaging = getMessaging();
    const staleTokenKeys = [];

    const sendPromises = tokens.map(async ({ key, token }) => {
      try {
        await messaging.send({
          token: token,
          notification: {
            title: fcmData.title,
            body: fcmData.body,
          },
          data: fcmData,
        });
        logger.info("FCM sent", { token: token.slice(-8) });
      } catch (err) {
        if (
          err.code === "messaging/registration-token-not-registered" ||
          err.code === "messaging/invalid-registration-token"
        ) {
          logger.warn("Stale FCM token, marking for removal", {
            key,
            token: token.slice(-8),
          });
          staleTokenKeys.push(key);
        } else {
          logger.error("FCM send error", { key, error: err.message });
        }
      }
    });

    await Promise.all(sendPromises);

    // 만료된 토큰 정리
    if (staleTokenKeys.length > 0) {
      const updates = {};
      staleTokenKeys.forEach((key) => {
        updates[`users/${uid}/fcmTokens/${key}`] = null;
      });
      await db.ref().update(updates);
      logger.info("Removed stale tokens", {
        count: staleTokenKeys.length,
      });
    }

    return null;
  }
);

/**
 * 탈퇴 요청 정책 쓰기를 서버에서 일원화한다.
 * - users/{uid} 정책 필드 기록
 * - withdrawnUsers/{uid}, withdrawnEmails/{emailKey} tombstone 기록
 * - RTDB forceLogout 명령 발행
 */
exports.requestWithdrawal = onRequest(
  {
    region: CLEANUP_REGION,
    cors: true,
  },
  async (req, res) => {
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
      const deleteAt = now + 7 * 24 * 60 * 60 * 1000;
      const rejoinAllowedAt = now + 30 * 24 * 60 * 60 * 1000;
      const emailLower = resolveEmail(decoded, req.body || {});
      const emailKey = computeEmailKey(emailLower);

      const db = getFirestore(FIRESTORE_DB_ID);
      const rtdb = getDatabase();

      await db
        .collection("users")
        .doc(uid)
        .set(
          {
            withdrawalStatus: "pending",
            deleteAt,
            rejoinAllowedAt,
            ...(emailLower ? { emailLower } : {}),
            ...(emailKey ? { withdrawalEmailKey: emailKey } : {}),
          },
          { merge: true }
        );

      await db
        .collection("withdrawnUsers")
        .doc(uid)
        .set(
          {
            rejoinAllowedAt,
            ...(emailKey ? { emailKey } : {}),
          },
          { merge: true }
        );

      if (emailKey) {
        await db
          .collection("withdrawnEmails")
          .doc(emailKey)
          .set(
            {
              rejoinAllowedAt,
              uid,
            },
            { merge: true }
          );
      }

      await rtdb.ref(`users/${uid}/commands/forceLogout`).set(createForceLogoutPayload());

      res.status(200).json({ ok: true, deleteAt, rejoinAllowedAt });
    } catch (err) {
      logger.error("requestWithdrawal failed", { error: String(err) });
      res.status(500).json({ ok: false, error: "internal_error" });
    }
  }
);

/**
 * 탈퇴 취소 정책 쓰기를 서버에서 일원화한다.
 * - users/{uid} active 복원
 * - withdrawnUsers/withdrawnEmails tombstone 삭제
 */
exports.cancelWithdrawal = onRequest(
  {
    region: CLEANUP_REGION,
    cors: true,
  },
  async (req, res) => {
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
      const userData = userSnap.exists ? userSnap.data() || {} : {};
      const emailLower = String(
        userData.emailLower || resolveEmail(decoded, req.body || {}) || ""
      )
        .trim()
        .toLowerCase();
      const emailKey = String(userData.withdrawalEmailKey || computeEmailKey(emailLower));

      await userRef.set(
        {
          withdrawalStatus: "active",
          deleteAt: null,
          rejoinAllowedAt: null,
          withdrawalEmailKey: null,
        },
        { merge: true }
      );

      await db.collection("withdrawnUsers").doc(uid).delete();

      if (emailKey) {
        await db.collection("withdrawnEmails").doc(emailKey).delete();
      }

      try {
        await rtdb.ref(`users/${uid}/commands/forceLogout`).remove();
      } catch (err) {
        logger.warn("cancelWithdrawal forceLogout cleanup failed", {
          uid,
          error: String(err),
        });
      }

      res.status(200).json({ ok: true });
    } catch (err) {
      logger.error("cancelWithdrawal failed", { error: String(err) });
      res.status(500).json({ ok: false, error: "internal_error" });
    }
  }
);

/**
 * users/{uid} 탈퇴 상태 전환 감지 -> 탈퇴 데이터 삭제 작업을 Cloud Tasks에 예약.
 */
exports.onUserWithdrawalChanged = onDocumentWritten(
  {
    document: "users/{uid}",
    region: CLEANUP_REGION,
    database: "progress",
  },
  async (event) => {
    const uid = event.params.uid;
    const beforeExists = Boolean(event.data.before && event.data.before.exists);
    const afterExists = Boolean(event.data.after && event.data.after.exists);

    if (!afterExists) {
      return null;
    }

    const beforeData = beforeExists ? event.data.before.data() || {} : {};
    const afterData = event.data.after.data() || {};

    const beforeStatus = beforeData.withdrawalStatus || "";
    const afterStatus = afterData.withdrawalStatus || "";
    const beforeDeleteAt = toMsNumber(beforeData.deleteAt);
    const afterDeleteAt = toMsNumber(afterData.deleteAt);

    if (afterStatus !== "pending" || !afterDeleteAt) {
      return null;
    }

    if (beforeStatus === "pending" && beforeDeleteAt === afterDeleteAt) {
      return null;
    }

    await enqueueWithdrawalCleanupTask(uid, afterDeleteAt);
    logger.info("Withdrawal cleanup task enqueued", {
      uid,
      deleteAt: afterDeleteAt,
    });
    return null;
  }
);

/**
 * withdrawnUsers/{uid} 변경 감지 -> tombstone 정리 작업을 Cloud Tasks에 예약.
 *
 * 디버그/레거시 경로에서 users 문서 변경 없이 withdrawnUsers만 갱신되는 경우를 커버한다.
 */
exports.onWithdrawnUserChanged = onDocumentWritten(
  {
    document: "withdrawnUsers/{uid}",
    region: CLEANUP_REGION,
    database: FIRESTORE_DB_ID,
  },
  async (event) => {
    const uid = event.params.uid;
    const afterExists = Boolean(event.data.after && event.data.after.exists);
    if (!afterExists) {
      return null;
    }

    const afterData = event.data.after.data() || {};
    const rejoinAllowedAt = toMsNumber(afterData.rejoinAllowedAt);
    if (!rejoinAllowedAt) {
      return null;
    }

    await enqueueTombstoneCleanupTask(uid, rejoinAllowedAt);
    logger.info("Tombstone cleanup task enqueued from withdrawnUsers change", {
      uid,
      rejoinAllowedAt,
    });
    return null;
  }
);

/**
 * 탈퇴 유예 만료 사용자 삭제 작업.
 * - users/{uid}가 아직 pending이고 deleteAt이 만료됐을 때만 삭제 진행
 * - 작업 완료 후 withdrawnUsers tombstone 정리 작업을 별도 예약
 */
exports.processWithdrawalCleanup = onTaskDispatched(
  {
    region: CLEANUP_REGION,
    retryConfig: {
      maxAttempts: 10,
      minBackoffSeconds: 30,
      maxBackoffSeconds: 3600,
      maxDoublings: 5,
    },
    rateLimits: {
      maxConcurrentDispatches: CLEANUP_CONCURRENCY,
      maxDispatchesPerSecond: 5,
    },
  },
  async (request) => {
    const now = Date.now();
    const uid = request.data && request.data.uid;

    if (!uid || typeof uid !== "string") {
      logger.warn("Invalid cleanup task payload", { data: request.data || null });
      return null;
    }

    const db = getFirestore(FIRESTORE_DB_ID);
    const rtdb = getDatabase();
    const auth = getAuth();
    const userRef = db.collection("users").doc(uid);
    const userSnap = await userRef.get();

    if (!userSnap.exists) {
      logger.info("Cleanup skipped: users doc not found", { uid });
      return null;
    }

    const data = userSnap.data() || {};
    const withdrawalStatus = data.withdrawalStatus || "";
    const deleteAt = toMsNumber(data.deleteAt);
    const rejoinAllowedAt = toMsNumber(data.rejoinAllowedAt) || now;
    const emailLower = String(data.emailLower || data.email || "").trim().toLowerCase();
    const emailKey = String(data.withdrawalEmailKey || computeEmailKey(emailLower));

    if (withdrawalStatus !== "pending") {
      logger.info("Cleanup skipped: status is not pending", {
        uid,
        withdrawalStatus,
      });
      return null;
    }

    if (!deleteAt) {
      logger.warn("Cleanup skipped: invalid deleteAt", { uid, deleteAt: data.deleteAt });
      return null;
    }

    if (deleteAt > now) {
      await enqueueWithdrawalCleanupTask(uid, deleteAt);
      logger.info("Cleanup rescheduled: deleteAt not reached", { uid, deleteAt });
      return null;
    }

    try {
      await rtdb.ref(`users/${uid}`).remove();
    } catch (err) {
      logger.warn("RTDB user remove failed", { uid, error: String(err) });
    }

    try {
      await userRef.delete();
    } catch (err) {
      logger.warn("Firestore users doc delete failed", {
        uid,
        error: String(err),
      });
    }

    try {
      await db
        .collection("withdrawnUsers")
        .doc(uid)
        .set(
          {
            deletedAt: now,
            rejoinAllowedAt,
            ...(emailKey ? { emailKey } : {}),
          },
          { merge: true }
        );
    } catch (err) {
      logger.warn("withdrawnUsers tombstone upsert failed", {
        uid,
        error: String(err),
      });
    }

    if (emailKey) {
      try {
        await db
          .collection("withdrawnEmails")
          .doc(emailKey)
          .set(
            {
              rejoinAllowedAt,
              uid,
            },
            { merge: true }
          );
      } catch (err) {
        logger.warn("withdrawnEmails upsert failed", {
          uid,
          emailKey,
          error: String(err),
        });
      }
    }

    try {
      await auth.deleteUser(uid);
    } catch (err) {
      const code = err && typeof err === "object" ? err.code : undefined;
      if (code !== "auth/user-not-found") {
        logger.warn("Auth user delete failed", { uid, error: String(err) });
      }
    }

    await enqueueTombstoneCleanupTask(uid, rejoinAllowedAt);
    logger.info("Withdrawal cleanup completed", {
      uid,
      rejoinAllowedAt,
      scheduledTombstoneCleanup: true,
    });
    return null;
  }
);

/**
 * 재가입 제한 기간 만료 시 withdrawnUsers tombstone 삭제.
 */
exports.processWithdrawnTombstoneCleanup = onTaskDispatched(
  {
    region: CLEANUP_REGION,
    retryConfig: {
      maxAttempts: 10,
      minBackoffSeconds: 60,
      maxBackoffSeconds: 3600,
      maxDoublings: 5,
    },
    rateLimits: {
      maxConcurrentDispatches: CLEANUP_CONCURRENCY,
      maxDispatchesPerSecond: 5,
    },
  },
  async (request) => {
    const now = Date.now();
    const uid = request.data && request.data.uid;

    if (!uid || typeof uid !== "string") {
      logger.warn("Invalid tombstone cleanup payload", { data: request.data || null });
      return null;
    }

    const db = getFirestore(FIRESTORE_DB_ID);
    const tombRef = db.collection("withdrawnUsers").doc(uid);
    const tombSnap = await tombRef.get();

    if (!tombSnap.exists) {
      logger.info("Tombstone cleanup skipped: doc not found", { uid });
      return null;
    }

    const tombData = tombSnap.data() || {};
    const rejoinAllowedAt = toMsNumber(tombData.rejoinAllowedAt);
    const emailKey = String(tombData.emailKey || "").trim();

    if (!rejoinAllowedAt) {
      logger.warn("Tombstone cleanup skipped: invalid rejoinAllowedAt", {
        uid,
        rejoinAllowedAt: tombData.rejoinAllowedAt,
      });
      return null;
    }

    if (rejoinAllowedAt > now) {
      await enqueueTombstoneCleanupTask(uid, rejoinAllowedAt);
      logger.info("Tombstone cleanup rescheduled", { uid, rejoinAllowedAt });
      return null;
    }

    await tombRef.delete();
    if (emailKey) {
      try {
        await db.collection("withdrawnEmails").doc(emailKey).delete();
      } catch (err) {
        logger.warn("withdrawnEmails delete failed", {
          uid,
          emailKey,
          error: String(err),
        });
      }
    }
    logger.info("Tombstone cleanup completed", { uid });
    return null;
  }
);

/**
 * 누락된 withdrawnUsers tombstone 백필 예약 스케줄러.
 *
 * 이벤트 트리거 누락/배포 공백 기간에 쌓인 만료 tombstone을 주기적으로 재수집한다.
 */
exports.backfillWithdrawnTombstoneCleanup = onSchedule(
  {
    schedule: "every 24 hours",
    region: CLEANUP_REGION,
    timeZone: "Asia/Seoul",
    maxInstances: 1,
  },
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
      const data = doc.data() || {};
      const rejoinAllowedAt = toMsNumber(data.rejoinAllowedAt) || now;
      await enqueueTombstoneCleanupTask(doc.id, rejoinAllowedAt);
      enqueued += 1;
    }

    logger.info("backfillWithdrawnTombstoneCleanup completed", {
      scanned: dueTombs.size,
      enqueued,
      hasMore: dueTombs.size === TOMBSTONE_BACKFILL_BATCH_SIZE,
      now,
    });

    return null;
  }
);
