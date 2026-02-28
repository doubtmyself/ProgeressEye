"""ProgressEye 설정 관리.

JSON 파일 기반 설정 읽기/쓰기.
경로: %APPDATA%/ProgressEye/config.json
"""

import json
import copy
import os
from pathlib import Path
from typing import Any

from utils.logger import log


DEFAULT_CONFIG: dict[str, Any] = {
    "version": 2,
    "auth": {
        "uid": "",
        "email": "",
        "device_id": "",
        "device_name": "",
    },
    "capture": {
        "interval_seconds": 30,
        "regions": [],
    },
    "analysis": {
        "confidence_threshold": 0.8,
    },
    "freeze_detection": {
        "enabled": True,
        "timeout_minutes": 5,
    },
    "startup": {
        "auto_start": False,
        "start_minimized": True,
    },
    "language": "en",
}


class Config:
    """앱 설정 관리자.

    JSON 파일에서 설정을 로드하고 저장한다.
    설정이 없으면 기본값으로 생성한다.
    """

    def __init__(self) -> None:
        self._dir = Path.home() / "AppData" / "Local" / "ProgressEye"
        self._path = self._dir / "config.json"
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """설정 파일을 로드한다. 없으면 기본값으로 생성."""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                log.info("설정 파일 로드: %s", self._path)
            except (json.JSONDecodeError, OSError) as e:
                log.warning("설정 파일 읽기 실패, 기본값 사용: %s", e)
                self._data = copy.deepcopy(DEFAULT_CONFIG)
                self._save()
        else:
            log.info("설정 파일 없음 — 기본값으로 생성")
            self._data = copy.deepcopy(DEFAULT_CONFIG)
            self._save()

    def _save(self) -> None:
        """설정을 JSON 파일에 원자적으로 저장한다 (tmp → fsync → replace)."""
        self._dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".json.tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(str(tmp_path), str(self._path))
        except OSError as e:
            log.warning("설정 파일 원자적 저장 실패, 직접 쓰기 시도: %s", e)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        log.debug("설정 파일 저장: %s", self._path)

    def get(self, key: str, default: Any = None) -> Any:
        """점(.) 구분 키로 설정 값을 가져온다.

        예: config.get('capture.interval_seconds')
        """
        keys = key.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, key: str, value: Any) -> None:
        """점(.) 구분 키로 설정 값을 저장한다."""
        keys = key.split(".")
        target = self._data
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
        self._save()

    @property
    def data(self) -> dict[str, Any]:
        """전체 설정 데이터 딕셔너리를 반환한다."""
        return self._data

    @property
    def regions(self) -> list[dict[str, Any]]:
        """캡처 영역 목록을 반환한다."""
        return self.get("capture.regions", [])

    def add_region(self, region: dict[str, Any]) -> None:
        """캡처 영역을 추가한다. enabled 기본값 True."""
        region.setdefault("enabled", True)
        region.setdefault("alert_threshold", 100)
        regions = self.regions
        regions.append(region)
        self.set("capture.regions", regions)

    def update_region(self, region_id: str, updates: dict[str, Any]) -> None:
        """특정 영역 설정을 업데이트한다."""
        regions = self.regions
        for i, r in enumerate(regions):
            if r.get("id") == region_id:
                regions[i].update(updates)
                break
        self.set("capture.regions", regions)

    def remove_region(self, region_id: str) -> None:
        """특정 영역을 제거한다."""
        regions = [r for r in self.regions if r.get("id") != region_id]
        self.set("capture.regions", regions)
