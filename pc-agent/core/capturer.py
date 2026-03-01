"""화면 캡처 엔진.

mss 라이브러리를 사용하여 지정 영역 또는 전체 화면을 캡처한다.
"""

import threading
from typing import Any

import mss
import mss.tools
from PIL import Image

from utils.logger import log


class CaptureError(Exception):
    """캡처 관련 에러."""


class ScreenCapturer:
    """mss 기반 화면 캡처 엔진.
    mss GDI 핸들은 thread-local이므로 스레드별 인스턴스를 관리한다.
    """

    def __init__(self) -> None:
        self._local = threading.local()

    def _get_sct(self) -> Any:
        """현재 스레드의 mss 인스턴스를 반환한다 (thread-local lazy init)."""
        if not hasattr(self._local, "sct") or self._local.sct is None:
            self._local.sct = mss.mss()
        return self._local.sct

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

            # 절대 물리 좌표가 있으면 우선 사용 (모니터 인덱스 드리프트 방지)
            if "abs_x" in region and "abs_y" in region:
                monitor_area = {
                    "left": int(region["abs_x"]),
                    "top": int(region["abs_y"]),
                    "width": int(region["width"]),
                    "height": int(region["height"]),
                }
                cx = monitor_area["left"] + monitor_area["width"] // 2
                cy = monitor_area["top"] + monitor_area["height"] // 2
                for i, mon in enumerate(monitors[1:], 1):
                    if (
                        mon["left"] <= cx < mon["left"] + mon["width"]
                        and mon["top"] <= cy < mon["top"] + mon["height"]
                    ):
                        monitor_idx = i
                        break
            else:
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
                    "left": int(region["x"] + offset_x),
                    "top": int(region["y"] + offset_y),
                    "width": int(region["width"]),
                    "height": int(region["height"]),
                }

            screenshot = sct.grab(monitor_area)
            # mss → PIL Image (BGRA → RGB)
            img = Image.frombytes(
                "RGB",
                (screenshot.width, screenshot.height),
                screenshot.rgb,
            )

            log.debug(
                "캡처 완료: %dx%d @ (%d, %d) monitor=%d abs=(%d,%d)",
                region["width"],
                region["height"],
                region["x"],
                region["y"],
                monitor_idx,
                monitor_area["left"],
                monitor_area["top"],
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
        """현재 스레드의 mss 리소스를 해제한다."""
        if hasattr(self._local, "sct") and self._local.sct is not None:
            try:
                self._local.sct.close()
            except (AttributeError, OSError):
                pass  # 이미 해제되었거나 다른 스레드에서 호출됨
            self._local.sct = None
