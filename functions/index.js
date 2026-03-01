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
const { getMessaging } = require("firebase-admin/messaging");
const { onValueCreated } = require("firebase-functions/v2/database");
const { onSchedule } = require("firebase-functions/v2/scheduler");
const { logger } = require("firebase-functions");

initializeApp();

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
 * 회원탈퇴 유예 정책 정리 배치 (매일 1회)
 * - users/{uid}.withdrawalStatus == "pending" && deleteAt <= now: 데이터 삭제
 * - withdrawnUsers/{uid}.rejoinAllowedAt <= now: 재가입 제한 tombstone 삭제
 */
exports.cleanupWithdrawnUsers = onSchedule(
  {
    schedule: "every day 03:00",
    region: "us-central1",
    timeZone: "Asia/Seoul",
  },
  async () => {
    const now = Date.now();
    const db = getFirestore();
    const rtdb = getDatabase();
    const auth = getAuth();

    // 1) 유예기간 만료 사용자 데이터 삭제
    const pendingSnap = await db
      .collection("users")
      .where("withdrawalStatus", "==", "pending")
      .where("deleteAt", "<=", now)
      .get();

    let deletedCount = 0;
    for (const doc of pendingSnap.docs) {
      const uid = doc.id;
      const data = doc.data() || {};
      const rejoinAllowedAt = Number(data.rejoinAllowedAt || now);

      try {
        await rtdb.ref(`users/${uid}`).remove();
      } catch (err) {
        logger.warn("RTDB user remove failed", { uid, error: String(err) });
      }

      try {
        await doc.ref.delete();
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
              uid,
              status: "deleted_data",
              deletedAt: now,
              rejoinAllowedAt,
            },
            { merge: true }
          );
      } catch (err) {
        logger.warn("withdrawnUsers tombstone upsert failed", {
          uid,
          error: String(err),
        });
      }

      try {
        await auth.deleteUser(uid);
      } catch (err) {
        logger.warn("Auth user delete failed", { uid, error: String(err) });
      }

      deletedCount += 1;
    }

    // 2) 재가입 제한 기간이 지난 tombstone 정리
    const expiredTombSnap = await db
      .collection("withdrawnUsers")
      .where("rejoinAllowedAt", "<=", now)
      .get();

    let purgedTombCount = 0;
    for (const doc of expiredTombSnap.docs) {
      try {
        await doc.ref.delete();
        purgedTombCount += 1;
      } catch (err) {
        logger.warn("withdrawnUsers tombstone delete failed", {
          uid: doc.id,
          error: String(err),
        });
      }
    }

    logger.info("cleanupWithdrawnUsers completed", {
      pendingDeleted: deletedCount,
      tombstonesPurged: purgedTombCount,
      now,
    });
    return null;
  }
);
