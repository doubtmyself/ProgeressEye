"""Firebase Realtime Database 기반 디바이스 관리 모듈."""

from __future__ import annotations

import platform
import time

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
            "status": "online",
            "lastSeen": now,
            "appVersion": "1.0.0",
            "createdAt": now,
        }
        self._db.patch(self._path, payload)

    def update_status(self, status: str = "online") -> None:
        """상태와 마지막 접속 시각을 갱신한다."""
        self._db.patch(
            self._path,
            {
                "status": status,
                "lastSeen": int(time.time() * 1000),
            },
        )

    def set_offline(self) -> None:
        """오프라인 상태를 기록한다."""
        self.update_status("offline")

    def heartbeat(self) -> None:
        """마지막 접속 시각만 갱신한다."""
        self._db.patch(self._path, {"lastSeen": int(time.time() * 1000)})

    @property
    def _path(self) -> str:
        return f"users/{self._uid}/devices/{self._device_id}"
