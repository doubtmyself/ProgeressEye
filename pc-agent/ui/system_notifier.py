"""Windows system notification helper (winotify Toast 기반)."""

from __future__ import annotations

import pathlib
import sys

from utils.logger import log  # pyright: ignore[reportImplicitRelativeImport]


def _icon_path() -> str:
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        base = pathlib.Path(sys.executable).parent
    else:
        base = pathlib.Path(__file__).resolve().parents[1]
    for name in ("app-icon.ico", "app-icon.png"):
        p = base / "resources" / name
        if p.exists():
            return str(p)
    return ""


class SystemNotifier:
    """Shows Windows Toast notifications without a tray icon."""

    def notify(self, title: str, message: str, timeout_ms: int = 6000) -> None:
        if sys.platform != "win32":
            return
        try:
            from winotify import Notification  # pyright: ignore[reportMissingImports]

            toast = Notification(
                app_id="ProgressEye",
                title=title,
                msg=message,
                duration="short" if timeout_ms <= 7000 else "long",
                icon=_icon_path(),
            )
            toast.show()
        except Exception as exc:
            log.debug("Toast 알림 실패: %s", exc)
