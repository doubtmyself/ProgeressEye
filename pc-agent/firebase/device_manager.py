"""Firebase Realtime Database 기반 디바이스 관리 모듈."""

from __future__ import annotations

import platform
import time
import uuid
from typing import Any

from .realtime_db import RealtimeDB


class DeviceManager:
    """PC 기기 등록/상태 갱신을 담당한다."""

    def __init__(self, db: RealtimeDB, uid: str, device_id: str) -> None:
        self._db = db
        self._uid = uid
        self._device_id = device_id

    def register(self, device_name: str = "") -> None:
        """기기를 등록하고 online 상태를 기록한다."""
        now = int(time.time() * 1000)
        payload = {
            "name": device_name or platform.node(),
            "platform": platform.platform(),
            "appVersion": "1.0.0",
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
        """
        self.update_status("monitoring" if active else "online")

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
        except Exception:
            pass  # 알림 실패는 무시 (모니터링 중단 방지)

    def set_offline(self) -> None:
        """오프라인 상태를 기록한다."""
        self.update_status("offline")
        # 하트비트 경로도 0으로 설정하여 오프라인 신호
        try:
            self._db.patch(
                f"users/{self._uid}/heartbeat",
                {self._device_id: 0},
            )
        except Exception:
            pass

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
        """Multi-path update로 작업 데이터 + 하트비트를 한 번에 전송한다.

        Args:
            task_updates: {region_id: {"p": progress, "s": status_code}} 형식.
        """
        payload: dict[str, Any] = {}
        for region_id, data in task_updates.items():
            for key, value in data.items():
                payload[f"tasks/{region_id}/{key}"] = value
        self._db.patch(self._path, payload)

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

    def get_user_plan(self) -> str:
        """유저 플랜을 조회한다. (기본값: free)"""
        data = self._db.get(f"{self._user_path}/plan")
        return data if isinstance(data, str) else "free"

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
