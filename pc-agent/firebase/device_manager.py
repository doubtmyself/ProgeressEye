"""Firebase Realtime Database 기반 디바이스 관리 모듈."""

from __future__ import annotations

import platform
import hashlib
import time
import uuid
from typing import Any

from .realtime_db import RealtimeDB
from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]

APP_VERSION = "1.0.9"  # NOTE: 버전 변경 시 여기만 수정 (main.py에서 import)


class DeviceManager:
    """PC 기기 등록/상태 갱신을 담당한다."""

    def __init__(self, db: RealtimeDB, uid: str, device_id: str) -> None:
        self._db = db
        self._uid = uid
        self._device_id = device_id
        self._name: str = platform.node()

    @property
    def name(self) -> str:
        return self._name

    @staticmethod
    def _email_key(email: str) -> str:
        normalized = email.strip().lower()
        if not normalized:
            return ""
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _withdrawal_api_url(project_id: str, action: str) -> str:
        return f"https://us-central1-{project_id}.cloudfunctions.net/{action}"

    def _call_withdrawal_api(
        self,
        action: str,
        project_id: str,
        email: str = "",
    ) -> None:
        import requests as _requests

        token = self._db.get_id_token()
        if not token:
            raise RuntimeError("id_token unavailable")

        url = self._withdrawal_api_url(project_id, action)
        resp = _requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"email": email.strip().lower()},
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"{action} failed: {resp.status_code} {resp.text[:200]}")

    def register(self, device_name: str = "") -> None:
        """기기를 등록하고 online 상태를 기록한다."""
        now = int(time.time() * 1000)
        self._name = device_name or platform.node()
        payload = {
            "name": self._name,
            "platform": platform.platform(),
            "appVersion": APP_VERSION,
            "createdAt": now,
        }
        self._db.patch(self._path, payload)
        # 접속 상태 + 하트비트 별도 경로 초기화
        self._db.patch(
            f"users/{self._uid}/deviceStatus",
            {self._device_id: "online"},
        )
        self._db.patch(
            f"users/{self._uid}/heartbeat",
            {self._device_id: now},
        )

    def update_status(self, status: str = "online") -> None:
        """접속 상태를 갱신한다 (deviceStatus 별도 경로)."""
        self._db.patch(
            f"users/{self._uid}/deviceStatus",
            {self._device_id: status},
        )

    def set_monitoring(self, active: bool) -> None:
        """모니터링 상태를 기록한다 (deviceStatus 경로 확장).

        deviceStatus 값:
          "monitoring" — 온라인 + 모니터링 중
          "online"     — 온라인 + 대기
          "offline"    — 오프라인
          "sleep"      — 절전 모드
        """
        self.update_status("monitoring" if active else "online")

    def set_sleep(self) -> None:
        """PC 절전모드 진입 상태를 기록한다."""
        self.update_status("sleep")

    def push_alert(self, alert_type: str, title: str, body: str) -> None:
        """알림을 RTDB에 기록한다 (모바일 FCM 트리거용).

        Args:
            alert_type: "completion" | "stall" | "image_change"
            title: 알림 제목
            body: 알림 본문
        """
        alert_id = uuid.uuid4().hex[:12]
        payload = {
            "type": alert_type,
            "title": title,
            "body": body,
            "deviceId": self._device_id,
            "ts": int(time.time() * 1000),
        }
        try:
            self._db.put(
                f"users/{self._uid}/alerts/{alert_id}",
                payload,
            )
        except Exception as exc:
            log.warning("push_alert 실패 [%s]: %s", alert_type, exc)

    def set_offline(self) -> None:
        """오프라인 상태를 기록한다.

        heartbeat를 먼저 0으로 설정한 뒤 status를 쓴다.
        Cloud Function이 "offline" 전환 감지 시 heartbeat=0을 보고
        정상 종료로 판단하여 FCM을 보내지 않도록 하기 위함.
        """
        try:
            self._db.patch(
                f"users/{self._uid}/heartbeat",
                {self._device_id: 0},
            )
        except Exception as exc:
            log.debug("set_offline heartbeat 실패: %s", exc)
        self.update_status("offline")

    def heartbeat(self) -> None:
        """하트비트 전용 경로에 lastSeen만 갱신한다.

        devices 서브트리 밖의 별도 경로를 사용하여
        메인 리스너 트리거를 방지한다.
        """
        self._db.patch(
            f"users/{self._uid}/heartbeat",
            {self._device_id: int(time.time() * 1000)},
        )

    def sync_tasks(self, task_updates: dict[str, dict[str, Any]]) -> None:
        """Multi-path update로 작업 데이터를 전송한다 (하트비트는 별도 경로).

        Args:
            task_updates: {region_id: {"p": progress, "s": status_code}} 형식.
        """
        payload: dict[str, Any] = {}
        for region_id, data in task_updates.items():
            for key, value in data.items():
                payload[f"tasks/{region_id}/{key}"] = value
        self._db.patch(self._path, payload)

    def sync_stats(self, stats: dict[str, object]) -> None:
        """하드웨어 stats를 RTDB에 기록한다.

        Args:
            stats: {"cpu": float, "gpu": float}
        """
        if not stats:
            return
        self._db.patch(f"{self._path}/stats", stats)

    def delete_task(self, region_id: str) -> None:
        """특정 작업 데이터를 삭제한다."""
        self._db.delete(f"{self._path}/tasks/{region_id}")

    def set_task_label(self, region_id: str, label: str) -> None:
        """작업 라벨을 설정한다 (등록/수정 시에만 호출)."""
        self._db.patch(f"{self._path}/tasks/{region_id}", {"l": label})

    @property
    def _path(self) -> str:
        return f"users/{self._uid}/devices/{self._device_id}"

    @property
    def _user_path(self) -> str:
        return f"users/{self._uid}"

    def get_user_plan(self, project_id: str = "progresseye-49244") -> str:
        """Firestore에서 유저 플랜을 조회한다. (기본값: free)

        Firestore document: users/{uid} → field: plan
        인증 필요 (owner만 읽기 가능).
        """
        import requests as _requests

        token = self._db.get_id_token()
        if not token:
            return "free"
        url = (
            f"https://firestore.googleapis.com/v1/"
            f"projects/{project_id}/databases/progress/documents/users/{self._uid}"
        )
        try:
            resp = _requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            if resp.status_code != 200:
                return "free"
            fields = resp.json().get("fields", {})
            return fields.get("plan", {}).get("stringValue", "free")
        except Exception as exc:
            log.debug("get_user_plan 조회 실패: %s", exc)
            return "free"

    def get_global_adfree_policy(self, project_id: str = "progresseye-49244") -> bool:
        """Firestore appConfig/policies 문서에서 adFreeModeGlobal 값을 반환한다.

        true이면 모든 유저가 광고 없이 사용 가능하므로 Free 플랜도 다중 기기 허용.
        조회 실패 시 false를 반환한다.
        """
        import requests as _requests

        token = self._db.get_id_token()
        if not token:
            return False
        url = (
            f"https://firestore.googleapis.com/v1/"
            f"projects/{project_id}/databases/progress/documents/appConfig/policies"
        )
        try:
            resp = _requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            if resp.status_code != 200:
                return False
            fields = resp.json().get("fields", {})
            return bool(fields.get("adFreeModeGlobal", {}).get("booleanValue", False))
            # return False
        except Exception as exc:
            log.debug("get_global_adfree_policy 조회 실패: %s", exc)
            return False

    def ensure_free_user_registered(
        self, project_id: str = "progresseye-49244"
    ) -> None:
        """Firestore users/{uid} 문서가 없으면 free 플랜 문서를 생성한다.

        앱이 draft/초기 상태일 때 free 유저가 Firestore에 누락되는 케이스를 방지한다.
        이미 문서가 존재하면 덮어쓰지 않는다.
        """
        import requests as _requests

        token = self._db.get_id_token()
        if not token:
            return

        now = int(time.time() * 1000)
        url = (
            f"https://firestore.googleapis.com/v1/"
            f"projects/{project_id}/databases/progress/documents/users/{self._uid}"
            f"?currentDocument.exists=false"
        )
        body = {
            "fields": {
                "plan": {"stringValue": "free"},
                "uid": {"stringValue": self._uid},
                "createdAt": {"integerValue": str(now)},
                "updatedAt": {"integerValue": str(now)},
            }
        }

        try:
            resp = _requests.patch(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=5,
            )
            if resp.status_code in (200, 201):
                log.info("Firestore free 유저 문서 생성: %s", self._uid)
                return

            # 문서가 이미 존재하면 정상 케이스로 간주
            if resp.status_code in (400, 409, 412):
                log.debug(
                    "Firestore 유저 문서 이미 존재/선행조건 불일치: %s", self._uid
                )
                return

            log.warning(
                "Firestore free 유저 등록 실패: status=%d body=%s",
                resp.status_code,
                resp.text[:300],
            )
        except Exception as exc:
            log.warning("Firestore free 유저 등록 예외: %s", exc)

    def delete_firestore_user_doc(self, project_id: str = "progresseye-49244") -> None:
        """Firestore users/{uid} 문서를 삭제한다.

        계정 탈퇴 시 데이터 정리를 위해 사용한다.
        """
        import requests as _requests

        token = self._db.get_id_token()
        if not token:
            return

        url = (
            f"https://firestore.googleapis.com/v1/"
            f"projects/{project_id}/databases/progress/documents/users/{self._uid}"
        )
        try:
            resp = _requests.delete(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            if resp.status_code in (200, 204, 404):
                return
            log.warning(
                "Firestore 유저 문서 삭제 실패: status=%d body=%s",
                resp.status_code,
                resp.text[:300],
            )
        except Exception as exc:
            log.warning("Firestore 유저 문서 삭제 예외: %s", exc)

    def request_account_withdrawal(
        self,
        project_id: str = "progresseye-49244",
        grace_days: int = 7,
        rejoin_days: int = 30,
        email: str = "",
    ) -> None:
        """회원탈퇴 요청을 Firestore에 기록한다.

        즉시 삭제하지 않고 탈퇴 유예기간(grace_days) 후 데이터 삭제 대상이 되며,
        rejoin_days 동안 재가입 제한을 적용한다.
        """
        _ = grace_days
        _ = rejoin_days
        self._call_withdrawal_api(
            action="requestWithdrawal",
            project_id=project_id,
            email=email,
        )

    def send_force_logout_command(self) -> None:
        """모든 연결 기기에 강제 로그아웃 명령을 브로드캐스트한다."""
        payload = {
            "ts": int(time.time()),
            "cmdId": str(uuid.uuid4()),
        }
        self._db.put(f"users/{self._uid}/commands/forceLogout", payload)

    def get_withdrawal_state(
        self,
        project_id: str = "progresseye-49244",
        email: str = "",
    ) -> dict[str, int | str | bool]:
        """회원탈퇴 상태를 조회한다.

        Returns keys:
          - pending: bool
          - deleteAt: int
          - rejoinAllowedAt: int
        """
        import requests as _requests

        token = self._db.get_id_token()
        if not token:
            return {"pending": False, "deleteAt": 0, "rejoinAllowedAt": 0}

        headers = {"Authorization": f"Bearer {token}"}
        base = (
            f"https://firestore.googleapis.com/v1/projects/{project_id}"
            f"/databases/progress/documents"
        )

        pending = False
        delete_at = 0
        rejoin_allowed_at = 0

        for path in (f"users/{self._uid}", f"withdrawnUsers/{self._uid}"):
            try:
                resp = _requests.get(f"{base}/{path}", headers=headers, timeout=5)
                if resp.status_code != 200:
                    continue
                fields = resp.json().get("fields", {})
                if path.startswith("users/"):
                    status = fields.get("withdrawalStatus", {}).get("stringValue")
                    if status == "pending":
                        pending = True
                    raw_delete = fields.get("deleteAt", {}).get("integerValue")
                    if raw_delete is not None:
                        delete_at = max(delete_at, int(raw_delete))
                raw_rejoin = fields.get("rejoinAllowedAt", {}).get("integerValue")
                if raw_rejoin is not None:
                    rejoin_allowed_at = max(rejoin_allowed_at, int(raw_rejoin))
            except Exception as exc:
                log.debug("withdrawal state 조회 실패(%s): %s", path, exc)

        email_key = self._email_key(email)
        if email_key:
            email_tomb_path = f"withdrawnEmails/{email_key}"
            try:
                resp = _requests.get(
                    f"{base}/{email_tomb_path}", headers=headers, timeout=5
                )
                if resp.status_code == 200:
                    fields = resp.json().get("fields", {})
                    raw_rejoin = fields.get("rejoinAllowedAt", {}).get("integerValue")
                    if raw_rejoin is not None:
                        rejoin_allowed_at = max(rejoin_allowed_at, int(raw_rejoin))
            except Exception as exc:
                log.debug("withdrawal state 조회 실패(%s): %s", email_tomb_path, exc)

        return {
            "pending": pending,
            "deleteAt": delete_at,
            "rejoinAllowedAt": rejoin_allowed_at,
        }

    def cancel_account_withdrawal(
        self,
        project_id: str = "progresseye-49244",
        email: str = "",
    ) -> None:
        """탈퇴 유예(pending) 상태를 취소한다."""
        self._call_withdrawal_api(
            action="cancelWithdrawal",
            project_id=project_id,
            email=email,
        )

    def debug_mark_withdrawal_expired(
        self,
        project_id: str = "progresseye-49244",
        grace_days: int = 7,
        rejoin_days: int = 30,
        email: str = "",
    ) -> None:
        """디버그: 탈퇴 후 grace_days가 지난 상태(삭제 기한 만료)를 강제로 만든다."""
        now = int(time.time() * 1000)
        requested_at = now - grace_days * 24 * 60 * 60 * 1000
        delete_at = now - 60 * 1000  # 1분 전 = 이미 만료
        rejoin_allowed_at = requested_at + rejoin_days * 24 * 60 * 60 * 1000
        if rejoin_allowed_at <= now:
            rejoin_allowed_at = now + 24 * 60 * 60 * 1000  # 아직 재가입 금지 유지
        self._debug_patch_withdrawal_tombstones(
            project_id=project_id,
            delete_at=delete_at,
            rejoin_allowed_at=rejoin_allowed_at,
            email=email,
        )

    def debug_mark_rejoin_expired(
        self,
        project_id: str = "progresseye-49244",
        rejoin_days: int = 30,
        email: str = "",
    ) -> None:
        """디버그: 탈퇴 후 rejoin_days가 지난 상태(재가입 금지 만료)를 강제로 만든다."""
        now = int(time.time() * 1000)
        requested_at = now - (rejoin_days + 1) * 24 * 60 * 60 * 1000
        delete_at = requested_at + 7 * 24 * 60 * 60 * 1000
        rejoin_allowed_at = requested_at + rejoin_days * 24 * 60 * 60 * 1000  # 이미 과거
        self._debug_patch_withdrawal_tombstones(
            project_id=project_id,
            delete_at=delete_at,
            rejoin_allowed_at=rejoin_allowed_at,
            email=email,
        )

    def _debug_patch_withdrawal_tombstones(
        self,
        project_id: str,
        delete_at: int,
        rejoin_allowed_at: int,
        email: str,
    ) -> None:
        """디버그 전용: 탈퇴 관련 Firestore 문서 3개를 PATCH로 일괄 업데이트한다."""
        import requests as _requests

        token = self._db.get_id_token()
        if not token:
            raise RuntimeError("id_token unavailable")

        email_lower = email.strip().lower()
        email_key = self._email_key(email_lower)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/progress/documents"

        # users/{uid}
        user_body: dict = {
            "fields": {
                "withdrawalStatus": {"stringValue": "pending"},
                "deleteAt": {"integerValue": str(delete_at)},
                "rejoinAllowedAt": {"integerValue": str(rejoin_allowed_at)},
            }
        }
        user_mask = ["withdrawalStatus", "deleteAt", "rejoinAllowedAt"]
        if email_lower:
            user_body["fields"]["emailLower"] = {"stringValue": email_lower}
            user_mask.append("emailLower")
        if email_key:
            user_body["fields"]["withdrawalEmailKey"] = {"stringValue": email_key}
            user_mask.append("withdrawalEmailKey")
        self._firestore_patch(
            _requests, f"{base_url}/users/{self._uid}",
            headers, user_body, user_mask, "users doc",
        )

        # withdrawnUsers/{uid}
        tomb_body: dict = {"fields": {"rejoinAllowedAt": {"integerValue": str(rejoin_allowed_at)}}}
        tomb_mask = ["rejoinAllowedAt"]
        if email_key:
            tomb_body["fields"]["emailKey"] = {"stringValue": email_key}
            tomb_mask.append("emailKey")
        self._firestore_patch(
            _requests, f"{base_url}/withdrawnUsers/{self._uid}",
            headers, tomb_body, tomb_mask, "withdrawnUsers doc",
        )

        # withdrawnEmails/{emailKey}
        if email_key:
            email_body = {
                "fields": {
                    "rejoinAllowedAt": {"integerValue": str(rejoin_allowed_at)},
                    "uid": {"stringValue": self._uid},
                }
            }
            self._firestore_patch(
                _requests, f"{base_url}/withdrawnEmails/{email_key}",
                headers, email_body, ["rejoinAllowedAt", "uid"], "withdrawnEmails doc",
            )

    @staticmethod
    def _firestore_patch(
        requests_mod: object,
        url: str,
        headers: dict,
        body: dict,
        mask: list[str],
        label: str,
    ) -> None:
        """Firestore REST PATCH 요청을 실행하고, 실패 시 RuntimeError를 발생시킨다."""
        resp = requests_mod.patch(  # type: ignore[attr-defined]
            url,
            headers=headers,
            params={"updateMask.fieldPaths": mask},
            json=body,
            timeout=5,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"{label} update failed: {resp.status_code} {resp.text[:200]}")

    def get_active_device(self) -> str | None:
        """현재 활성 디바이스 ID를 조회한다."""
        data = self._db.get(f"{self._user_path}/activeDevice")
        return data if isinstance(data, str) else None

    def set_active_device(self) -> None:
        """이 디바이스를 활성 디바이스로 설정한다."""
        self._db.patch(self._user_path, {"activeDevice": self._device_id})

    def clear_active_device(self) -> None:
        """활성 디바이스를 해제한다 (로그아웃 시)."""
        self._db.patch(self._user_path, {"activeDevice": None})

    def is_other_device_online(self, other_device_id: str) -> bool:
        """다른 디바이스가 온라인인지 확인한다 (5분 이내 heartbeat)."""
        data = self._db.get(f"users/{self._uid}/heartbeat/{other_device_id}")
        if not isinstance(data, (int, float)):
            return False
        elapsed = time.time() * 1000 - data
        return elapsed < 5 * 60 * 1000  # 5분


def get_min_pc_version(project_id: str = "progresseye-49244") -> str | None:
    """Firestore에서 최소 PC 버전을 조회한다 (인증 불필요).

    Firestore document: appConfig/pc  → field: minVersion
    """
    import requests as _requests

    url = (
        f"https://firestore.googleapis.com/v1/"
        f"projects/{project_id}/databases/progress/documents/appConfig/pc"
    )
    try:
        resp = _requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None
        fields = resp.json().get("fields", {})
        return fields.get("minVersion", {}).get("stringValue")
    except Exception as exc:
        log.debug("get_min_pc_version 조회 실패: %s", exc)
        return None
