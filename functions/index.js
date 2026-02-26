/**
 * ProgressEye Cloud Functions
 *
 * RTDB 트리거: 새 알림이 users/{uid}/alerts/{alertId}에 기록되면
 * 해당 유저의 FCM 토큰으로 데이터 메시지를 전송한다.
 */

const { initializeApp } = require("firebase-admin/app");
const { getDatabase } = require("firebase-admin/database");
const { getMessaging } = require("firebase-admin/messaging");
const { onValueCreated } = require("firebase-functions/v2/database");
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
