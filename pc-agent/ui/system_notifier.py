"""Windows system notification helper."""

from __future__ import annotations

import pathlib
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from utils.logger import log


class SystemNotifier:
    """Shows Windows notifications using QSystemTrayIcon."""

    def __init__(self, app: QApplication) -> None:
        self._tray: QSystemTrayIcon | None = None
        if sys.platform != "win32":
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.info("시스템 트레이를 사용할 수 없어 시스템 알림을 비활성화합니다")
            return

        if getattr(sys, "frozen", False) or "__compiled__" in globals():
            icon_base = pathlib.Path(sys.executable).parent
        else:
            icon_base = pathlib.Path(__file__).resolve().parents[1]

        icon = app.windowIcon()
        for icon_path in (
            icon_base / "resources" / "app-icon.ico",
            icon_base / "resources" / "app-icon.png",
        ):
            if icon_path.exists():
                icon = QIcon(str(icon_path))
                break

        tray = QSystemTrayIcon(icon, app)
        tray.setToolTip("ProgressEye")
        tray.show()
        self._tray = tray

    def notify(self, title: str, message: str, timeout_ms: int = 6000) -> None:
        """Shows a system notification if available."""
        if not self._tray:
            return
        self._tray.showMessage(
            title,
            message,
            QSystemTrayIcon.MessageIcon.Information,
            timeout_ms,
        )
