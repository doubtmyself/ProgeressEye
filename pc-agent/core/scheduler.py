"""캡처 주기 스케줄러.

등록된 영역을 주기적으로 캡처하여 콜백 함수를 호출한다.
"""

import threading
from typing import Any, Callable

from PIL import Image

from core.capturer import ScreenCapturer, CaptureError
from utils.logger import log


# 콜백 타입: (region_id, captured_image) → None
CaptureCallback = Callable[[str, Image.Image], None]
CycleCompleteCallback = Callable[[], None]


class CaptureScheduler:
    """주기적 캡처 스케줄러.

    등록된 영역들을 일정 주기로 캡처하고,
    콜백을 통해 결과를 전달한다.
    """

    def __init__(
        self,
        on_capture: CaptureCallback,
        capturer: ScreenCapturer | None = None,
        on_cycle_complete: CycleCompleteCallback | None = None,
    ) -> None:
        """
        Args:
            on_capture: 캡쳐 완료 시 호출되는 콜백 (region_id, image).
            capturer: 화면 캡쳐 엔진 (None이면 새로 생성).
            on_cycle_complete: 한 사이클 완료 후 호출되는 콜백.
        """
        self._on_capture = on_capture
        self._on_cycle_complete = on_cycle_complete
        self._capturer = capturer or ScreenCapturer()
        self._regions: dict[str, dict[str, Any]] = {}
        self._interval: int = 30
        self._running = False
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def start(
        self,
        regions: list[dict[str, Any]],
        interval_seconds: int = 30,
    ) -> None:
        """주기적 캡처를 시작한다.

        Args:
            regions: 캡처 영역 목록 (각 영역에 "id" 키 필수).
            interval_seconds: 캡처 주기 (초).
        """
        with self._lock:
            if self._running:
                log.warning("스케줄러 이미 실행 중")
                return

            self._regions = {r["id"]: r for r in regions}
            self._interval = interval_seconds
            self._running = True

        log.info(
            "스케줄러 시작: %d개 영역, %d초 주기",
            len(self._regions),
            self._interval,
        )
        self._schedule_next()

    def stop(self) -> None:
        """주기적 캡처를 중지한다."""
        with self._lock:
            self._running = False
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

        log.info("스케줄러 중지")

    def update_interval(self, interval_seconds: int) -> None:
        """캡처 주기를 변경한다.

        Args:
            interval_seconds: 새 캡처 주기 (초).
        """
        with self._lock:
            self._interval = interval_seconds
        log.info("캡처 주기 변경: %d초", interval_seconds)

    def add_region(self, region: dict[str, Any]) -> None:
        """모니터링 영역을 추가한다.

        Args:
            region: 영역 정보 ("id" 키 필수).
        """
        region_id = region["id"]
        with self._lock:
            self._regions[region_id] = region
        log.info("영역 추가: %s", region_id)

    def remove_region(self, region_id: str) -> None:
        """모니터링 영역을 제거한다.

        Args:
            region_id: 제거할 영역 ID.
        """
        with self._lock:
            if region_id in self._regions:
                del self._regions[region_id]
                log.info("영역 제거: %s", region_id)

    @property
    def is_running(self) -> bool:
        """스케줄러 실행 상태."""
        return self._running

    @property
    def region_count(self) -> int:
        """등록된 영역 수."""
        return len(self._regions)

    def _schedule_next(self) -> None:
        """다음 캡처 사이클을 예약한다."""
        with self._lock:
            if not self._running:
                return
            self._timer = threading.Timer(self._interval, self._run_cycle)
            self._timer.daemon = True
            self._timer.start()

    def _run_cycle(self) -> None:
        """한 번의 캡처 사이클을 실행한다."""
        with self._lock:
            if not self._running:
                return
            regions = dict(self._regions)

        for region_id, region in regions.items():
            try:
                image = self._capturer.capture(region)
                self._on_capture(region_id, image)
            except CaptureError as e:
                log.error("캡처 실패 [%s]: %s", region_id, e)
            except Exception as e:
                log.error("캡처 콜백 오류 [%s]: %s", region_id, e)

        # 사이클 완료 콜백
        if self._on_cycle_complete is not None:
            try:
                self._on_cycle_complete()
            except Exception as e:
                log.error("사이클 콜백 오류: %s", e)

        # 다음 사이클 예약
        self._schedule_next()

    def run_once(self) -> None:
        """한 번만 모든 영역을 캡처한다 (테스트용)."""
        with self._lock:
            regions = dict(self._regions)

        for region_id, region in regions.items():
            try:
                image = self._capturer.capture(region)
                self._on_capture(region_id, image)
            except CaptureError as e:
                log.error("캡처 실패 [%s]: %s", region_id, e)
