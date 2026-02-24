"""화면 캡처 엔진.

mss 라이브러리를 사용하여 지정 영역 또는 전체 화면을 캡처한다.
"""

from typing import Any

import mss
import mss.tools
from PIL import Image

from utils.logger import log


class CaptureError(Exception):
    """캡처 관련 에러."""


class ScreenCapturer:
    """mss 기반 화면 캡처 엔진.

    지정 영역 또는 전체 화면을 캡처하여 PIL Image로 반환한다.
    """

    def __init__(self) -> None:
        self._sct: mss.mss | None = None

    def _get_sct(self) -> mss.mss:
        """mss 인스턴스를 반환한다 (lazy init)."""
        if self._sct is None:
            self._sct = mss.mss()
        return self._sct

    def capture(self, region: dict[str, Any]) -> Image.Image:
        """지정 영역을 캡처한다.

        Args:
            region: 캡처 영역 정보.
                - x: 좌측 좌표
                - y: 상단 좌표
                - width: 너비
                - height: 높이
                - monitor: 모니터 인덱스 (0=전체, 1=첫번째, ...)

        Returns:
            캡처된 PIL 이미지 (RGB).

        Raises:
            CaptureError: 캡처 실패 시.
        """
        try:
            sct = self._get_sct()
            monitors = sct.monitors

            monitor_idx = region.get("monitor", 0)
            if monitor_idx >= len(monitors):
                log.warning(
                    "모니터 %d 없음 (총 %d개) — 기본 모니터 사용",
                    monitor_idx,
                    len(monitors) - 1,
                )
                monitor_idx = 0

            # mss는 절대 좌표를 사용
            # monitor_idx > 0이면 해당 모니터의 좌상단 오프셋 적용
            if monitor_idx > 0:
                mon = monitors[monitor_idx]
                offset_x = mon["left"]
                offset_y = mon["top"]
            else:
                offset_x = 0
                offset_y = 0

            monitor_area = {
                "left": region["x"] + offset_x,
                "top": region["y"] + offset_y,
                "width": region["width"],
                "height": region["height"],
            }

            screenshot = sct.grab(monitor_area)
            # mss → PIL Image (BGRA → RGB)
            img = Image.frombytes(
                "RGB",
                (screenshot.width, screenshot.height),
                screenshot.rgb,
            )

            log.debug(
                "캡처 완료: %dx%d @ (%d, %d)",
                region["width"],
                region["height"],
                region["x"],
                region["y"],
            )
            return img

        except Exception as e:
            raise CaptureError(f"화면 캡처 실패: {e}") from e

    def capture_full_screen(self, monitor: int = 0) -> Image.Image:
        """전체 화면을 캡처한다.

        Args:
            monitor: 모니터 인덱스 (0=모든 모니터 합친 전체, 1=첫번째, ...).

        Returns:
            캡처된 PIL 이미지 (RGB).
        """
        sct = self._get_sct()
        monitors = sct.monitors

        if monitor >= len(monitors):
            log.warning("모니터 %d 없음 — 전체 화면 캡처", monitor)
            monitor = 0

        mon = monitors[monitor]
        screenshot = sct.grab(mon)
        img = Image.frombytes(
            "RGB",
            (screenshot.width, screenshot.height),
            screenshot.rgb,
        )

        log.debug("전체 화면 캡처: %dx%d", img.width, img.height)
        return img

    def get_monitors(self) -> list[dict[str, int]]:
        """사용 가능한 모니터 목록을 반환한다.

        Returns:
            모니터 정보 리스트 [{"left", "top", "width", "height"}, ...].
            인덱스 0은 전체 가상 화면, 1부터 개별 모니터.
        """
        sct = self._get_sct()
        return list(sct.monitors)

    def close(self) -> None:
        """mss 리소스를 해제한다."""
        if self._sct is not None:
            try:
                self._sct.close()
            except (AttributeError, OSError):
                pass  # 다른 스레드에서 호출 시 thread-local 핸들 없음
            self._sct = None
