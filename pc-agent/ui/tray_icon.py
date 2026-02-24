"""시스템 트레이 아이콘 모듈.

pystray 기반으로 시스템 트레이에 상주하며
기본 메뉴를 제공한다.
"""

import threading
from typing import Callable

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem, Menu

from utils.logger import log


class TrayIcon:
    """시스템 트레이 아이콘.

    pystray를 사용하여 시스템 트레이에 아이콘을 표시하고
    컨텍스트 메뉴를 제공한다.
    """

    def __init__(
        self,
        on_select_area: Callable[[], None] | None = None,
        on_toggle_monitoring: Callable[[], None] | None = None,
        on_show_window: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self.on_select_area = on_select_area
        self.on_toggle_monitoring = on_toggle_monitoring
        self.on_show_window = on_show_window
        self.on_quit = on_quit

        self._monitoring = False
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """트레이 아이콘을 시작한다 (별도 스레드)."""
        if self._icon is not None:
            return

        icon_image = self._create_default_icon()
        self._icon = pystray.Icon(
            name="ProgressEye",
            icon=icon_image,
            title="ProgressEye",
            menu=self._build_menu(),
        )

        self._thread = threading.Thread(
            target=self._icon.run,
            daemon=True,
            name="tray-icon",
        )
        self._thread.start()
        log.info("트레이 아이콘 시작")

    def stop(self) -> None:
        """트레이 아이콘을 중지한다."""
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
        log.info("트레이 아이콘 중지")

    def update_tooltip(self, text: str) -> None:
        """트레이 아이콘 툴팁을 업데이트한다."""
        if self._icon is not None:
            self._icon.title = text

    def set_monitoring(self, active: bool) -> None:
        """모니터링 상태를 변경한다."""
        self._monitoring = active
        if self._icon is not None:
            self._icon.menu = self._build_menu()
            self._icon.update_menu()

    def _build_menu(self) -> Menu:
        """컨텍스트 메뉴를 빌드한다."""
        monitoring_label = "모니터링 정지" if self._monitoring else "모니터링 시작"

        return Menu(
            MenuItem("ProgressEye", None, enabled=False),
            Menu.SEPARATOR,
            MenuItem("영역 선택", self._on_select_area),
            MenuItem(monitoring_label, self._on_toggle_monitoring),
            Menu.SEPARATOR,
            MenuItem("메인 창 열기", self._on_show_window),
            Menu.SEPARATOR,
            MenuItem("종료", self._on_quit_clicked),
        )

    def _on_select_area(self, icon, item) -> None:
        if self.on_select_area:
            self.on_select_area()

    def _on_toggle_monitoring(self, icon, item) -> None:
        if self.on_toggle_monitoring:
            self.on_toggle_monitoring()

    def _on_show_window(self, icon, item) -> None:
        if self.on_show_window:
            self.on_show_window()

    def _on_quit_clicked(self, icon, item) -> None:
        if self.on_quit:
            self.on_quit()
        self.stop()

    @staticmethod
    def _create_default_icon() -> Image.Image:
        """기본 트레이 아이콘을 프로그래매틱하게 생성한다.

        초록색 배경에 흰색 'P' 문자.
        """
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 원형 배경
        draw.ellipse(
            [4, 4, size - 4, size - 4],
            fill=(66, 133, 244, 255),  # Google Blue
        )

        # 'P' 문자 (간단한 형태)
        draw.text(
            (size // 2 - 8, size // 2 - 12),
            "P",
            fill=(255, 255, 255, 255),
        )

        return img
